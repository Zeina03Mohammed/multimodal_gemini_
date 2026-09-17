"""
App entry point. Run with:
    uvicorn app.main:app --reload

`uvicorn` is the actual web server (it listens on a network port and speaks
HTTP). FastAPI is just the framework that decides WHAT to do with each
request - uvicorn is what makes it reachable at all.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import generate, rag

app = FastAPI(
    title="Multimodal Content Generator",
    description="Generate text, ground it with your own documents (RAG), and (soon) understand images/audio.",
    version="0.1.0",
)

# Allow the Flutter web app (served from a different origin/port during
# development) to call this API from the browser. Locked to localhost since
# this is a dev setup, not a public deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plug each router's endpoints into the main app.
app.include_router(generate.router)
app.include_router(rag.router)


@app.get("/health")
def health_check():
    """Simple endpoint to confirm the server is alive - useful for
    deployment platforms and for you to sanity-check locally."""
    return {"status": "ok"}
