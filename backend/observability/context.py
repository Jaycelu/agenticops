from __future__ import annotations

import contextvars


request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def request_id() -> str:
    return request_id_var.get()
