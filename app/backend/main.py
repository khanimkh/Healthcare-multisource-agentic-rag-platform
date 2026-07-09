from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.backend.api.routes import router


app = FastAPI(
    title="AWS Healthcare Multi-Source Agentic RAG Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

FRONTEND_PATH = Path(__file__).parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return FRONTEND_PATH.read_text(encoding="utf-8")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
