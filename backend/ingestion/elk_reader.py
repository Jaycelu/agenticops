from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dateutil import parser as date_parser

from ingestion.schemas import ELKDocument, ELKPage
from models.ingestion import IngestionCheckpoint
from models.log_scope import LogScope
from services.integration_config_service import integration_config_service
from config.settings import settings


class ELKReaderError(RuntimeError):
    pass


class ELKReader:
    async def read_page(
        self,
        scope: LogScope,
        checkpoint: IngestionCheckpoint,
        *,
        page_size: int,
    ) -> ELKPage:
        config = integration_config_service.get_elk_runtime_config()
        if not config.get("enabled") or not config.get("url"):
            raise ELKReaderError("elk_not_configured")
        metadata = dict(scope.scope_metadata or {})
        mode = str(metadata.get("reader_mode") or "proxy")
        if mode == "native":
            documents, total = await self._native(config, scope, checkpoint, page_size)
        elif mode == "proxy":
            documents, total = await self._proxy(config, scope, checkpoint, page_size)
        else:
            raise ELKReaderError("unsupported_reader_mode")
        self._validate_order(documents, checkpoint)
        return ELKPage(documents=documents, has_more=len(documents) == page_size, total=total)

    async def _native(self, config, scope, checkpoint, page_size) -> tuple[list[ELKDocument], int | None]:
        metadata = dict(scope.scope_metadata or {})
        index = str(metadata.get("index_pattern") or "").strip()
        timestamp_field = str(metadata.get("timestamp_field") or "@timestamp")
        if not index:
            raise ELKReaderError("native reader requires scope_metadata.index_pattern")
        body: dict[str, Any] = {
            "size": page_size,
            "sort": [{timestamp_field: "asc"}, {"_id": "asc"}],
            "query": {
                "bool": {
                    "must": [{"query_string": {"query": scope.query_filter or "*"}}],
                }
            },
        }
        if not checkpoint.cursor_timestamp:
            body["query"]["bool"]["filter"] = [
                {"range": {timestamp_field: {"gte": (datetime.now(timezone.utc) - timedelta(hours=settings.elk_initial_lookback_hours)).isoformat()}}}
            ]
        if checkpoint.cursor_timestamp and checkpoint.cursor_document_id:
            body["search_after"] = [checkpoint.cursor_timestamp.isoformat(), checkpoint.cursor_document_id]
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(
                f"{str(config['url']).rstrip('/')}/{index}/_search",
                auth=(config.get("username") or "", config.get("password") or ""),
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
        hits = list((payload.get("hits") or {}).get("hits") or [])
        documents = [self._native_document(hit, timestamp_field) for hit in hits]
        total_raw = (payload.get("hits") or {}).get("total")
        total = int(total_raw.get("value")) if isinstance(total_raw, dict) else int(total_raw) if total_raw else None
        return documents, total

    async def _proxy(self, config, scope, checkpoint, page_size) -> tuple[list[ELKDocument], int | None]:
        params: dict[str, Any] = {
            "domain": "ops",
            "query": scope.query_filter,
            "category": "search",
            "size": str(page_size),
            "sort": "timestamp:asc,_id:asc",
            "time_range": f"-{settings.elk_initial_lookback_hours}h,now",
        }
        if checkpoint.cursor_timestamp and checkpoint.cursor_document_id:
            params["search_after"] = f"{checkpoint.cursor_timestamp.isoformat()},{checkpoint.cursor_document_id}"
            params["time_range"] = f"{checkpoint.cursor_timestamp.isoformat()},now"
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.get(
                config["url"],
                auth=(config.get("username") or "", config.get("password") or ""),
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
        rows = list((((payload.get("results") or {}).get("sheets") or {}).get("rows")) or payload.get("data") or [])
        documents = [self._proxy_document(row) for row in rows]
        total_raw = (payload.get("results") or {}).get("total_hits", payload.get("total"))
        return documents, int(total_raw) if total_raw is not None else None

    def _native_document(self, hit: dict[str, Any], timestamp_field: str) -> ELKDocument:
        source = dict(hit.get("_source") or {})
        return self._document(
            document_id=str(hit.get("_id") or ""),
            timestamp=source.get(timestamp_field) or (hit.get("sort") or [None])[0],
            message=source.get("message") or source.get("raw_message") or "",
            device=source.get("device_ip") or source.get("host") or source.get("hostname") or "unknown",
            severity=source.get("severity") or source.get("level") or "unknown",
            metadata={"index": hit.get("_index")},
        )

    def _proxy_document(self, row: dict[str, Any]) -> ELKDocument:
        document_id = row.get("_id") or row.get("id") or row.get("document_id")
        if not document_id:
            raise ELKReaderError("proxy rows must expose a stable document id")
        return self._document(
            document_id=str(document_id),
            timestamp=row.get("@timestamp") or row.get("timestamp"),
            message=row.get("message") or row.get("raw_message") or "",
            device=row.get("device_ip") or row.get("hostname") or row.get("host") or "unknown",
            severity=row.get("severity") or row.get("level") or "unknown",
            metadata={"source": "proxy"},
        )

    def _document(self, *, document_id, timestamp, message, device, severity, metadata) -> ELKDocument:
        if not document_id:
            raise ELKReaderError("document id is required")
        parsed_timestamp = self._timestamp(timestamp)
        return ELKDocument(
            document_id=document_id,
            timestamp=parsed_timestamp,
            message=str(message)[:65536],
            device_key=str(device)[:255] or "unknown",
            severity=str(severity).lower()[:30],
            metadata=metadata,
        )

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            numeric = float(value)
            parsed = datetime.fromtimestamp(numeric / 1000 if numeric > 10_000_000_000 else numeric, tz=timezone.utc)
        elif value:
            parsed = date_parser.isoparse(str(value))
        else:
            raise ELKReaderError("document timestamp is required")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _validate_order(documents: list[ELKDocument], checkpoint: IngestionCheckpoint) -> None:
        previous = (
            (checkpoint.cursor_timestamp, checkpoint.cursor_document_id)
            if checkpoint.cursor_timestamp and checkpoint.cursor_document_id
            else None
        )
        seen: set[tuple[datetime, str]] = set()
        for document in documents:
            cursor = (document.timestamp, document.document_id)
            if cursor in seen or (previous and cursor <= previous):
                raise ELKReaderError("ELK page is not strictly sorted by timestamp and document id")
            seen.add(cursor)
            previous = cursor


elk_reader = ELKReader()
