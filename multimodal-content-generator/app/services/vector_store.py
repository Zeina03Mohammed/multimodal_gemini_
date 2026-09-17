"""
Wraps ChromaDB - the vector database that stores chunk embeddings and lets
us search them by similarity.

Why a vector database instead of just a Python list of (chunk, embedding)
pairs? At small scale a list would work, but Chroma also persists to disk
(so ingested documents survive a server restart) and indexes the vectors for
fast nearest-neighbor search, which a linear scan wouldn't give us for free.
"""

import uuid

import chromadb

from app.config import settings

_client = chromadb.PersistentClient(path=settings.chroma_db_path)
_collection = _client.get_or_create_collection("documents")


def add_document(filename: str, chunks: list[str], embeddings: list[list[float]]) -> str:
    """Store one document's chunks + embeddings under a new document id."""
    document_id = str(uuid.uuid4())
    chunk_ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    metadatas = [{"filename": filename, "document_id": document_id, "chunk_index": i} for i in range(len(chunks))]

    _collection.add(
        ids=chunk_ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return document_id


def query(query_embedding: list[float], top_k: int = 4) -> list[dict]:
    """Return the `top_k` chunks most similar to the given embedding."""
    if _collection.count() == 0:
        return []

    result = _collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, _collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    return [
        {"text": text, "filename": metadata["filename"], "distance": distance}
        for text, metadata, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def list_documents() -> list[dict]:
    """List distinct ingested documents with their chunk counts."""
    all_metadata = _collection.get(include=["metadatas"])["metadatas"]

    documents: dict[str, dict] = {}
    for metadata in all_metadata:
        doc_id = metadata["document_id"]
        if doc_id not in documents:
            documents[doc_id] = {"document_id": doc_id, "filename": metadata["filename"], "chunk_count": 0}
        documents[doc_id]["chunk_count"] += 1

    return list(documents.values())


def delete_document(document_id: str) -> bool:
    """Remove all chunks belonging to a document. Returns False if it didn't exist."""
    matches = _collection.get(where={"document_id": document_id})["ids"]
    if not matches:
        return False
    _collection.delete(ids=matches)
    return True
