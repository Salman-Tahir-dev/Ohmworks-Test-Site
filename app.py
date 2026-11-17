"""Ohmworks: Deliberately vulnerable LLM test target for Aegis scanner.
Phase 1: Skeleton and design + Section 9 Security limits.
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.routes import router
from server.security import RequestLimitsMiddleware

app = FastAPI(
    title="Ohmworks",
    description="Deliberately vulnerable LLM test benchmark for Aegis scanner",
    version="1.0.0",
)

# Mandatory Section 9: Request size cap and per-session rate limits middleware
app.add_middleware(RequestLimitsMiddleware)

# Include main page and API router
app.include_router(router)

# Mount static asset folders
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/css", StaticFiles(directory=os.path.join(STATIC_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(STATIC_DIR, "js")), name="js")
app.mount("/fonts", StaticFiles(directory=os.path.join(STATIC_DIR, "fonts")), name="fonts")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    # Fixed technical decision: Bind to 127.0.0.1 only, port 8003
    uvicorn.run("app:app", host="127.0.0.1", port=8003, log_level="info", reload=True)
