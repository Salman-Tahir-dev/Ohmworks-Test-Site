"""Security middleware and limits for Ohmworks per AGENTS.md Section 9:
- Cap request size (64KB)
- Per-session rate limiting (applied strictly to /api/chat at 120 req/min)
- Enforce bounds
"""

import time
from typing import Dict, Tuple
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

MAX_REQUEST_SIZE = 64 * 1024  # 64 KB cap
RATE_LIMIT_WINDOW = 60.0      # 1 minute window
MAX_REQUESTS_PER_WINDOW = 120 # 120 requests per minute on /api/chat per owner approval


class RateLimiter:
    def __init__(self):
        # Maps session_key -> list of request timestamps
        self.requests: Dict[str, list] = {}

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        timestamps = self.requests.get(key, [])
        valid_timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        
        if len(valid_timestamps) >= MAX_REQUESTS_PER_WINDOW:
            self.requests[key] = valid_timestamps
            retry_after = int(RATE_LIMIT_WINDOW - (now - valid_timestamps[0])) + 1
            return False, retry_after

        valid_timestamps.append(now)
        self.requests[key] = valid_timestamps
        return True, 0

    def clear(self):
        self.requests.clear()


rate_limiter = RateLimiter()


class RequestLimitsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Request Size Cap (64KB for all incoming requests)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > MAX_REQUEST_SIZE:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Payload Too Large: Exceeds request size cap of {MAX_REQUEST_SIZE} bytes."}
                    )
            except ValueError:
                pass

        # 2. Per-session Rate Limiting: Applied strictly to /api/chat only
        if request.url.path == "/api/chat":
            session_key = request.cookies.get("ohmworks_user", request.client.host if request.client else "unknown")
            allowed, retry_after = rate_limiter.is_allowed(session_key)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Too Many Requests: Rate limit exceeded. Try again in {retry_after} seconds."},
                    headers={"Retry-After": str(retry_after)}
                )

        response = await call_next(request)
        return response
