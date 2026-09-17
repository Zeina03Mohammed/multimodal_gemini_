"""
The /generate endpoint - plain text content generation.

A "router" in FastAPI is just a bundle of related endpoints (here: only one,
but soon we'll have routers for rag.py, vision.py, audio.py, all wired
together in main.py). Keeping them in separate files is what lets a project
grow without turning into one giant unreadable file.
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import GenerateRequest, GenerateResponse
from app.services import gemini_client

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        response = gemini_client.generate_text(
            prompt=request.prompt,
            system=request.system,
        )
    except RuntimeError as e:
        # Convert our service-layer error into a proper HTTP error response
        # (status 502 = "Bad Gateway", i.e. "the upstream service failed").
        raise HTTPException(status_code=502, detail=str(e))

    return GenerateResponse(
        content=gemini_client.extract_text(response),
        model=response.model_version,
        input_tokens=response.usage_metadata.prompt_token_count,
        output_tokens=response.usage_metadata.candidates_token_count,
    )
