import logging
import logging.config
from typing import Any

import structlog

_SENSITIVE_SUBSTRINGS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "private_key",
)

_MASK = "***"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(s in lowered for s in _SENSITIVE_SUBSTRINGS)


def _mask_value(value: Any) -> Any:
    """dict や list の内部にある機密値を再帰的にマスクする。"""
    if isinstance(value, dict):
        return {
            k: (_MASK if _is_sensitive_key(str(k)) else _mask_value(v)) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        masked = [_mask_value(v) for v in value]
        return type(value)(masked) if isinstance(value, tuple) else masked
    return value


def _mask_sensitive_data(
    _logger: Any,
    _method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """ログイベント中の機密値 (ネストされたものを含む) をマスクする。"""
    return {
        k: (_MASK if _is_sensitive_key(str(k)) else _mask_value(v)) for k, v in event_dict.items()
    }

def _inject_trace_context(
    _logger: Any,
    _method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """アクティブな OpenTelemetry span から ``trace_id`` / ``span_id`` を注入する。"""
    try:
        from opentelemetry import trace
    except ImportError:
        return event_dict

    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx is None or not ctx.is_valid:
        return event_dict
    event_dict.setdefault("trace_id", format(ctx.trace_id, "032x"))
    event_dict.setdefault("span_id", format(ctx.span_id, "016x"))
    return event_dict

def setup_logging(log_level: str, app_env: str) -> None:
    """JSON レンダリングと Uvicorn 連携を備えた structlog を構成する。"""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _inject_trace_context,
        _mask_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer()
            if app_env == "development"
            else structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)
        uv_logger.propagate = False