from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import accounts, api_keys, audit, auth, internal, users
from app.config import settings
from app.core.rate_limit import limiter

docs_enabled = settings.environment != "production"

app = FastAPI(
    title="Snov Account Manager",
    version="0.1.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(internal.router)
app.include_router(api_keys.router)
app.include_router(audit.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
