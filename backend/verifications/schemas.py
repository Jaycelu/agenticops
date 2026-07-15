from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CheckDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1, max_length=120)
    kind: Literal["zabbix_alert_absent", "elk_count_reduced"]
    target: dict[str, Any]
    max_age_seconds: int = Field(default=300, ge=10, le=3600)
    max_ratio: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.kind == "zabbix_alert_absent" and not self.target.get("host"):
            raise ValueError("zabbix check requires target.host")
        if self.kind == "zabbix_alert_absent" and not (
            self.target.get("event_id") or self.target.get("name_contains")
        ):
            raise ValueError("zabbix check requires event_id or name_contains")
        if self.kind == "elk_count_reduced" and not self.target.get("query"):
            raise ValueError("ELK check requires target.query")
        return self


class VerificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[CheckDefinition] = Field(min_length=1, max_length=20)
    max_rounds: int = Field(default=3, ge=1, le=20)
    interval_seconds: int = Field(default=60, ge=10, le=3600)


class CheckResult(BaseModel):
    check_id: str
    verdict: Literal["verified", "pending", "regressed", "inconclusive"]
    baseline: dict[str, Any]
    observed: dict[str, Any]
    freshness_seconds: float
    reason: str
