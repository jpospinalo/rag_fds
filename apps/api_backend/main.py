import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# CORRECCIÓN: se eliminó la línea duplicada de imports
from api_backend.routers import documents, audit, metrics, batch
from api_backend.config import Config

# Agregar raíz del proyecto al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API_PREFIX = "/api"

app = FastAPI(
    title="RAG FDS/SGA API",
    description="API para consulta semántica y auditoría automática de Fichas de Datos de Seguridad",
    version="1.0.0",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(metrics.router, prefix=API_PREFIX)
app.include_router(batch.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["Estado"])
def health():
    return {"status": "ok", "service": "RAG FDS API", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("api_backend.main:app", host="0.0.0.0", port=8000, reload=True)