# app/observability.py
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()

        # ✅ Safe: only read session if SessionMiddleware already attached it
        sess = request.scope.get("session")  # may be None on early errors
        user_id = sess.get("user_id") if sess else None

        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logging.getLogger("pa.req").info(
            "%s %s -> %s in %.1fms user=%s",
            request.method,
            request.url.path,
            response.status_code,
            ms,
            user_id,
        )
        return response
