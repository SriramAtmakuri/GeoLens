from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db, close_db
from app.routes import documents, query, ingest, eval as eval_router

# OpenTelemetry — graceful degradation if Jaeger is unavailable
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from app.config import settings as _s

    _provider = TracerProvider()
    _exporter = OTLPSpanExporter(endpoint=_s.jaeger_endpoint, insecure=True)
    _provider.add_span_processor(BatchSpanProcessor(_exporter))
    trace.set_tracer_provider(_provider)
    _otel_ok = True
except Exception:
    _otel_ok = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        from app.services.embeddings import embed_text
        await embed_text("warmup")
    except Exception:
        pass
    yield
    await close_db()


app = FastAPI(title="GeoLens API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if _otel_ok:
    FastAPIInstrumentor.instrument_app(app)

app.include_router(documents.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(eval_router.router, prefix="/api")


@app.get("/api/health")
async def health():
    from app.db import get_pool
    pool = await get_pool()
    db_ok = pool is not None
    return {"status": "ok", "db": db_ok, "otel": _otel_ok}
