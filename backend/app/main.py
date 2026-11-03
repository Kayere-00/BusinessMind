"""BusinessMind AI — FastAPI application entrypoint."""
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, engine
from .routers import analytics, assistant, auth, datasets, reports, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("businessmind")
settings = get_settings()
settings.validate_production()

@asynccontextmanager
async def lifespan(app_: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("%s started (env=%s)", settings.APP_NAME, settings.ENV)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENV != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.ENV != "production" else None,
)

# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


_rate_windows: dict[str, deque] = defaultdict(deque)
AUTH_PREFIXES = ("/api/auth/login", "/api/auth/register")
_assistant_rate_windows: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def auth_rate_limit(request: Request, call_next):
    """Simple per-IP sliding-window limiter for credential endpoints."""
    if request.url.path in AUTH_PREFIXES:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = _rate_windows[ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.AUTH_RATE_LIMIT:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many attempts. Please wait a minute and try again."},
            )
        window.append(now)
    return await call_next(request)


@app.middleware("http")
async def assistant_rate_limit(request: Request, call_next):
    """Bound model and tool usage per client without logging user prompts."""
    if (
        request.method == "POST"
        and request.url.path.startswith("/api/assistant/conversations/")
        and request.url.path.endswith("/messages")
    ):
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = _assistant_rate_windows[ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= 30:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Assistant usage limit reached. Wait a minute and try again."},
            )
        window.append(now)
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},  # never leak internals
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(datasets.router)
app.include_router(analytics.router)
app.include_router(assistant.router)
app.include_router(reports.router)

# Serve the built React SPA (single-container Docker deployment).
_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="spa")
