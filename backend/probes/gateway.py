from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.schemas import Principal
from config.settings import settings
from models.probe import ProbeRun, ProbeTemplateVersion
from probes.catalog import ProbeCatalogError, probe_catalog
from probes.redaction import redact_output
from probes.schemas import EvidenceEnvelope, ProbeRequest, ProbeResult
from probes.ssh_transport import HostKeyRejected, ssh_probe_transport


logger = logging.getLogger(__name__)


class ProbeRejected(RuntimeError):
    pass


class ProbeGateway:
    @contextmanager
    def _advisory_slot(self, db: Session, device_id: int) -> Iterator[None]:
        connection = db.connection()
        device_key = 810_000_000 + device_id
        device_locked = bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": device_key}).scalar())
        if not device_locked:
            raise ProbeRejected("device_probe_already_running")
        slot_key: int | None = None
        try:
            for slot in range(settings.probe_global_concurrency):
                candidate = 820_000_000 + slot
                if connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": candidate}).scalar():
                    slot_key = candidate
                    break
            if slot_key is None:
                raise ProbeRejected("probe_capacity_exhausted")
            yield
        finally:
            if slot_key is not None:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": slot_key})
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": device_key})

    def run(self, db: Session, request: ProbeRequest, principal: Principal | None = None) -> ProbeResult:
        try:
            target = ssh_probe_transport.resolve_target(db, request.credential_id, request.netbox_device_id)
            definition, commands = probe_catalog.render(request.probe_id, target.platform, request.parameters)
        except (ValueError, HostKeyRejected, ProbeCatalogError) as exc:
            return self._record_rejection(db, request, str(exc), principal)

        self._persist_template_version(db, definition)
        run = ProbeRun(
            probe_id=definition.probe_id,
            template_version=definition.version,
            netbox_device_id=request.netbox_device_id,
            credential_id=request.credential_id,
            requested_by_user_id=principal.user_id if principal else None,
            requested_by_session_id=principal.session_id if principal else None,
            status="running",
            request_parameters=request.parameters,
            rendered_commands=commands,
            evidence={},
        )
        db.add(run)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ProbeRejected("device_probe_already_running") from exc
        db.refresh(run)

        try:
            with self._advisory_slot(db, request.netbox_device_id):
                raw_outputs = ssh_probe_transport.execute(target, commands, settings.probe_command_timeout_seconds)
            outputs = []
            redactions = 0
            truncated = False
            for item in raw_outputs:
                output, count, was_truncated = redact_output(
                    str(item.get("output") or ""), max_bytes=settings.probe_max_output_bytes
                )
                error, error_count, error_truncated = redact_output(
                    str(item.get("stderr") or ""), max_bytes=settings.probe_max_output_bytes
                )
                outputs.append({**item, "output": output, "stderr": error})
                redactions += count + error_count
                truncated = truncated or was_truncated or error_truncated
            envelope = EvidenceEnvelope(
                probe_id=definition.probe_id,
                template_version=definition.version,
                netbox_device_id=request.netbox_device_id,
                collected_at=datetime.now(timezone.utc),
                outputs=outputs,
                redactions=redactions,
                truncated=truncated,
            )
            run.status = "succeeded"
            run.evidence = envelope.model_dump(mode="json")
            run.finished_at = func.now()
            self._audit(db, run, "success", principal)
            db.commit()
            return ProbeResult(run_id=int(run.id), status="succeeded", evidence=envelope)
        except Exception as exc:
            logger.warning("probe failed probe_id=%s run_id=%s error_type=%s", request.probe_id, run.id, type(exc).__name__)
            run.status = "failed"
            run.error_code = self._error_code(exc)
            run.error_detail = str(exc)[:2000]
            run.finished_at = func.now()
            self._audit(db, run, "failed", principal)
            db.commit()
            return ProbeResult(run_id=int(run.id), status="failed", error_code=run.error_code)

    def _record_rejection(
        self, db: Session, request: ProbeRequest, reason: str, principal: Principal | None
    ) -> ProbeResult:
        run = ProbeRun(
            probe_id=request.probe_id,
            template_version=probe_catalog.version,
            netbox_device_id=request.netbox_device_id,
            credential_id=request.credential_id,
            requested_by_user_id=principal.user_id if principal else None,
            requested_by_session_id=principal.session_id if principal else None,
            status="rejected",
            request_parameters=request.parameters,
            rendered_commands=[],
            evidence={},
            error_code=reason[:80],
            finished_at=func.now(),
        )
        db.add(run)
        db.flush()
        self._audit(db, run, "rejected", principal)
        db.commit()
        return ProbeResult(run_id=int(run.id), status="rejected", error_code=run.error_code)

    @staticmethod
    def _persist_template_version(db: Session, definition) -> None:
        exists = db.query(ProbeTemplateVersion.id).filter(
            ProbeTemplateVersion.probe_id == definition.probe_id,
            ProbeTemplateVersion.version == definition.version,
        ).first()
        if exists is None:
            db.add(
                ProbeTemplateVersion(
                    probe_id=definition.probe_id,
                    version=definition.version,
                    catalog_hash=definition.catalog_hash,
                    definition={
                        "platforms": definition.platforms,
                        "parameters": definition.parameters,
                    },
                    active=True,
                )
            )
            db.flush()

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if isinstance(exc, HostKeyRejected):
            return "host_key_rejected"
        if isinstance(exc, ProbeRejected):
            return str(exc)[:80]
        return type(exc).__name__[:80]

    @staticmethod
    def _audit(db: Session, run: ProbeRun, outcome: str, principal: Principal | None) -> None:
        security_audit_service.append(
            db,
            event_type="probe.run",
            outcome=outcome,
            actor_user_id=principal.user_id if principal else None,
            actor_session_id=principal.session_id if principal else None,
            target_type="probe_run",
            target_id=str(run.id),
            details={
                "probe_id": run.probe_id,
                "netbox_device_id": run.netbox_device_id,
                "template_version": run.template_version,
                "error_code": run.error_code,
            },
        )


probe_gateway = ProbeGateway()
