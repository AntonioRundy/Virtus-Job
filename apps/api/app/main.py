import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.routers import auth, devices, opportunities, users

_DEV_SECRET = "virtus-job-dev-secret-key-change-in-production-32chars"


def _validate_startup() -> None:
    errors: list[str] = []
    warnings: list[str] = []

    if not settings.SECRET_KEY:
        errors.append("SECRET_KEY está vazia — impossível assinar tokens JWT")
    elif settings.SECRET_KEY == _DEV_SECRET:
        if settings.is_production:
            errors.append("SECRET_KEY é a chave de desenvolvimento — proibido em produção")
        else:
            warnings.append("SECRET_KEY ainda é a chave dev padrão — rotacionar antes de ir a produção")

    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL está vazia — base de dados não configurada")

    if not settings.ANTHROPIC_API_KEY:
        warnings.append(
            "ANTHROPIC_API_KEY não está definida — pipeline AI desactivado, "
            "extracção degradada para fallback (confidence ~0.1)"
        )

    for w in warnings:
        print(f"[Virtus Job] AVISO: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"[Virtus Job] ERRO CRÍTICO: {e}", file=sys.stderr)
        raise RuntimeError(f"Arranque abortado: {len(errors)} erro(s) crítico(s) de configuração")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_startup()
    print(f"[Virtus Job] Starting {settings.ENVIRONMENT} server...")
    yield
    print("[Virtus Job] Shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API da plataforma Virtus Job — Oportunidades profissionais em Angola",
    version="0.1.0",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# ─── Middlewares ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─── Routers ─────────────────────────────────────────────
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(opportunities.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(devices.router, prefix=settings.API_V1_PREFIX)


# ─── Health & Root ───────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "service": settings.PROJECT_NAME}


@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }
