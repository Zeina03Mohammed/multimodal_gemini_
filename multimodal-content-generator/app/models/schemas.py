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
    as_image: bool = Field(
        default=False,
        description="If true, generate an image grounded in the retrieved context instead of a text answer",
    )


class RagSource(BaseModel):
    filename: str
    text: str
    distance: float = Field(description="Vector distance to the query - lower means more relevant")


class RagQueryResponse(BaseModel):
    answer: str | None = None
    image_base64: str | None = Field(default=None, description="Base64-encoded image, present only when as_image was true")
    image_mime_type: str | None = None
    sources: list[RagSource]


class ChatMessage(BaseModel):
    role: str = Field(description="'user' or 'model'")
    text: str | None = None
    image_base64: str | None = None
    image_mime_type: str | None = None
    sources: list[RagSource] = Field(default_factory=list)
    created_at: str | None = None


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    created_at: str


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessage]


class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatSendResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
