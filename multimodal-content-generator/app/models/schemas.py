"""
Pydantic "schemas" = the shape of data flowing in/out of our API.

Why: without this, a request body is just an untyped blob of JSON and you
find out something is missing/wrong deep inside your function, at runtime,
maybe in production. With Pydantic, FastAPI checks the shape BEFORE your
function even runs, and auto-generates docs describing exactly what's
expected.
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="What you want Gemini to write about")
    system: str | None = Field(
        default=None,
        description="Optional 'persona' instruction, e.g. 'You are a witty copywriter.'",
    )


class GenerateResponse(BaseModel):
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class DocumentUploadResponse(DocumentInfo):
    pass


class RagQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question to answer using your uploaded documents")
    top_k: int = Field(default=4, ge=1, le=20, description="How many chunks to retrieve as context")


class RagSource(BaseModel):
    filename: str
    text: str
    distance: float = Field(description="Vector distance to the query - lower means more relevant")


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RagSource]
