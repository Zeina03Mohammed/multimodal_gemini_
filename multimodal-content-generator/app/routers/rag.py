"""
RAG (Retrieval-Augmented Generation) endpoints.

The idea: instead of asking Gemini a question and hoping it already knows
the answer, we first search our own uploaded documents for the most
relevant chunks, then hand those chunks to Gemini alongside the question.
This "grounds" the answer in content we control, and lets Gemini answer
questions about documents it was never trained on.

Pipeline:
    upload  -> extract text -> chunk -> embed -> store in Chroma
    query   -> embed question -> retrieve top-k similar chunks -> ask Gemini
"""

import io

from fastapi import APIRouter, HTTPException, UploadFile
from pypdf import PdfReader

from app.models.schemas import (
    DocumentInfo,
    DocumentUploadResponse,
    RagQueryRequest,
    RagQueryResponse,
    RagSource,
)
from app.services import embeddings, gemini_client, vector_store
from app.services.chunking import chunk_text

router = APIRouter(prefix="/rag", tags=["rag"])

_SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf")


def _extract_text(filename: str, content: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="ignore")


@router.post("/documents", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile) -> DocumentUploadResponse:
    if not file.filename or not file.filename.lower().endswith(_SUPPORTED_EXTENSIONS):
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Use one of: {_SUPPORTED_EXTENSIONS}")

    text = _extract_text(file.filename, file.file.read())
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not extract any text from this file.")

    try:
        vectors = embeddings.embed_documents(chunks)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    document_id = vector_store.add_document(filename=file.filename, chunks=chunks, embeddings=vectors)

    return DocumentUploadResponse(document_id=document_id, filename=file.filename, chunk_count=len(chunks))


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents() -> list[DocumentInfo]:
    return [DocumentInfo(**doc) for doc in vector_store.list_documents()]


@router.delete("/documents/{document_id}")
def delete_document(document_id: str) -> dict:
    if not vector_store.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": document_id}


_RAG_SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided context excerpts. "
    "If the context doesn't contain the answer, say so plainly instead of guessing."
)


@router.post("/query", response_model=RagQueryResponse)
def query(request: RagQueryRequest) -> RagQueryResponse:
    try:
        query_vector = embeddings.embed_query(request.question)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    matches = vector_store.query(query_vector, top_k=request.top_k)

    if not matches:
        raise HTTPException(status_code=400, detail="No documents have been uploaded yet.")

    context = "\n\n---\n\n".join(f"[{m['filename']}]\n{m['text']}" for m in matches)
    prompt = f"Context:\n{context}\n\nQuestion: {request.question}"

    try:
        response = gemini_client.generate_text(prompt=prompt, system=_RAG_SYSTEM_PROMPT)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return RagQueryResponse(
        answer=gemini_client.extract_text(response),
        sources=[RagSource(filename=m["filename"], text=m["text"], distance=m["distance"]) for m in matches],
    )
