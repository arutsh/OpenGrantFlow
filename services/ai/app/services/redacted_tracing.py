"""Tracer wrapper that records exceptions by type only, so error text can't leak content."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry.trace import Span, StatusCode, Tracer


class RedactedSpan:
    def __init__(self, span: Span):
        self._span = span

    def __getattr__(self, name: str) -> Any:
        return getattr(self._span, name)

    def record_exception(
        self,
        exception: BaseException,
        attributes: Any = None,
        timestamp: int | None = None,
        escaped: bool = False,
    ) -> None:
        # Validation errors quote the raw input (model output, question) in their message.
        self._span.add_event(
            "exception",
            {"exception.type": type(exception).__qualname__, "exception.escaped": escaped},
            timestamp,
        )


class RedactingTracer:
    def __init__(self, tracer: Tracer):
        self._tracer = tracer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tracer, name)

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        **kwargs: Any,
    ) -> Iterator[RedactedSpan]:
        with self._tracer.start_as_current_span(
            name, record_exception=False, set_status_on_exception=False, **kwargs
        ) as span:
            redacted = RedactedSpan(span)
            try:
                yield redacted
            except BaseException as exc:
                if record_exception:
                    redacted.record_exception(exc, escaped=True)
                if set_status_on_exception:
                    span.set_status(StatusCode.ERROR, type(exc).__qualname__)
                raise
