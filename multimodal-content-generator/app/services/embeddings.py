"""
Wraps Gemini's embedding model.

An "embedding" is just a list of numbers (a vector) that represents the
meaning of a piece of text - similar text produces similar vectors. RAG uses
this to find which stored document chunks are relevant to a question,
without either one containing the other's exact words.

Gemini's embedding model wants a `task_type` hint: documents you're storing
for later search should use RETRIEVAL_DOCUMENT, and the question you're
searching with should use RETRIEVAL_QUERY. Using the matching type measurably
improves retrieval quality - it's not just a formality.
"""

from google import genai
from google.genai import errors, types

from app.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)

_EMBEDDING_MODEL = "gemini-embedding-001"

# Gemini's BatchEmbedContents endpoint rejects requests with more than 100
# contents, so larger inputs must be split into batches of at most this size.
_MAX_BATCH_SIZE = 100


def _embed(contents: list[str], task_type: str) -> list[list[float]]:
    try:
        embeddings: list[list[float]] = []
        for i in range(0, len(contents), _MAX_BATCH_SIZE):
            batch = contents[i : i + _MAX_BATCH_SIZE]
            response = _client.models.embed_content(
                model=_EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            embeddings.extend(e.values for e in response.embeddings)
        return embeddings

    # Same error-handling shape as gemini_client.generate_text - the router
    # layer only knows how to turn a RuntimeError into an HTTP response.
    except errors.ClientError as e:
        if e.code == 401 or e.code == 403:
            raise RuntimeError("Invalid Gemini API key - check your .env file.")
        if e.code == 429:
            raise RuntimeError("Rate limited by Gemini - try again in a moment.")
        raise RuntimeError(f"Gemini API error ({e.code}): {e.message}")
    except errors.ServerError as e:
        raise RuntimeError(f"Gemini API error ({e.code}): {e.message}")
    except errors.APIError as e:
        raise RuntimeError(f"Could not reach Gemini's servers: {e}")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed chunks that will be stored and searched later."""
    return _embed(texts, task_type="RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """Embed a user's question before searching stored chunks with it."""
    return _embed([text], task_type="RETRIEVAL_QUERY")[0]
