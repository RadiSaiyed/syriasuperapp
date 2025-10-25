import json
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("jobs.request")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        start = time.time()
        response: Response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        response.headers["X-Request-ID"] = req_id
        try:
            log = {
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
            logger.info(json.dumps(log))
        except Exception:
            pass
        return response

