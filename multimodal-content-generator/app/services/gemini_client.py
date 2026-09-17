"""
Thin wrapper around the Google Gen AI SDK (Gemini).

Why wrap it at all instead of calling `genai.Client()` inside every router?
Because every other feature we build (RAG, vision, audio) will also need to
"ask Gemini something." If each router made its own raw API call, we'd have
5 copies of the same error-handling code. Here, we write it once.
"""

from google import genai
from google.genai import errors, types

from app.config import settings

# Created once at import time and reused for every request - creating a
# new client per-request would be wasteful (it sets up connection pools).
_client = genai.Client(api_key=settings.gemini_api_key)


def generate_text(prompt: str, system: str | None = None, max_tokens: int = 1024) -> types.GenerateContentResponse:
    """
    Send a single prompt to Gemini and get back the full response object.

    We return the whole response (not just the text) because the caller
    might want token usage, model version, etc. - not just the words.
    """
    try:
        response = _client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return response

    # Most-specific exceptions first - each means something different and
    # deserves a different response to the user.
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


def extract_text(response: types.GenerateContentResponse) -> str:
    """Pull the plain text out of a response."""
    return response.text or ""
