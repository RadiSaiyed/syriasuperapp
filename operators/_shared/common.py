from __future__ import annotations

import os
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        try:
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Referrer-Policy", "no-referrer")
            resp.headers.setdefault(
                "Permissions-Policy",
                "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
            )
            if request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
                resp.headers.setdefault("Cache-Control", "no-store")
            else:
                resp.headers.setdefault("Cache-Control", "no-cache, max-age=0")
        except Exception:
            pass
        return resp


def init_tracing(app: FastAPI, *, default_name: str) -> None:
    try:
        if getattr(app.state, "_otel_init", False):
            return
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if not endpoint:
            app.state._otel_init = True
            return
        service_name = os.getenv("OTEL_SERVICE_NAME", default_name)
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            "service.name": service_name,
            "deployment.environment": os.getenv("ENV", "dev"),
        })
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        app.state._otel_init = True
    except Exception:
        app.state._otel_init = True

