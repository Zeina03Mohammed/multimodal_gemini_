"""
Orchestrates one chat turn.

Given a conversation's history and a new user message, this hands Gemini two
tools - "search_documents" and "generate_image" - and lets Gemini decide for
itself, via function calling, whether the message needs one of them or can
just be answered directly. That's what makes the chat "do anything" without
the user having to flip a mode switch: ask a plain question and Gemini
replies in text; ask about an uploaded file and it calls search_documents;
ask for a picture and it calls generate_image.

We don't use the SDK's automatic function-calling loop because a tool result
here isn't always text a model should read back (an image is a payload for
the client, not something to paste into another Gemini call) - so each tool
is handled manually, once, per turn.
"""

import base64

from google.genai import types

from app.services import embeddings, gemini_client, vector_store

_SEARCH_DOCUMENTS = types.FunctionDeclaration(
    name="search_documents",
    description=(
        "Search the user's uploaded documents for passages relevant to a query. "
        "Use this whenever the user asks about the content of a file they uploaded, "
        "or asks a question that their documents might answer."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={"query": types.Schema(type="STRING", description="What to search for")},
        required=["query"],
    ),
)

_GENERATE_IMAGE = types.FunctionDeclaration(
    name="generate_image",
    description=(
        "Generate an image from a text description. Use this whenever the user asks "
        "you to draw, create, generate, sketch, illustrate, or make a picture, image, "
        "photo, logo, or diagram."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "prompt": types.Schema(
                type="STRING", description="A vivid, detailed description of the image to generate"
            )
        },
        required=["prompt"],
    ),
)

_TOOLS = [types.Tool(function_declarations=[_SEARCH_DOCUMENTS, _GENERATE_IMAGE])]

_SYSTEM_PROMPT = (
    "You are a helpful, general-purpose assistant. Chat naturally. Use the "
    "search_documents tool when the user's question might be answered by files "
    "they've uploaded, and the generate_image tool when they ask for a picture. "
    "Otherwise, just answer directly."
)

_RAG_ANSWER_SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided context excerpts from "
    "their uploaded documents. If the context doesn't contain the answer, say so "
    "plainly instead of guessing."
)


def _history_to_contents(history: list[dict]) -> list[types.Content]:
    contents = []
    for m in history:
        parts = []
        if m.get("text"):
            parts.append(types.Part.from_text(text=m["text"]))
        if m.get("image_base64"):
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(m["image_base64"]),
                    mime_type=m.get("image_mime_type") or "image/png",
                )
            )
        if parts:
            contents.append(types.Content(role="user" if m["role"] == "user" else "model", parts=parts))
    return contents


def _first_function_call(response: types.GenerateContentResponse) -> types.FunctionCall | None:
    if not response.candidates or not response.candidates[0].content.parts:
        return None
    for part in response.candidates[0].content.parts:
        if part.function_call is not None:
            return part.function_call
    return None


def _handle_search(query: str) -> dict:
    query_vector = embeddings.embed_query(query)
    matches = vector_store.query(query_vector, top_k=4)

    if not matches:
        return {"text": "You haven't uploaded any documents yet, so I can't search them.", "sources": []}

    context = "\n\n---\n\n".join(f"[{m['filename']}]\n{m['text']}" for m in matches)
    prompt = f"Context:\n{context}\n\nQuestion: {query}"
    response = gemini_client.generate_text(prompt=prompt, system=_RAG_ANSWER_SYSTEM_PROMPT)

    return {
        "text": gemini_client.extract_text(response),
        "sources": [{"filename": m["filename"], "text": m["text"], "distance": m["distance"]} for m in matches],
    }


def _handle_generate_image(prompt: str) -> dict:
    image_bytes, mime_type = gemini_client.generate_image(prompt)
    return {"image_base64": base64.b64encode(image_bytes).decode("ascii"), "image_mime_type": mime_type}


def send_message(history: list[dict], message: str) -> dict:
    """
    Run one chat turn and return the assistant's reply as a plain dict:
    {"text": str | None, "image_base64": str | None, "image_mime_type": str | None, "sources": list[dict]}
    """
    contents = _history_to_contents(history)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    response = gemini_client.generate_with_tools(contents, tools=_TOOLS, system=_SYSTEM_PROMPT)
    call = _first_function_call(response)

    reply = {"text": None, "image_base64": None, "image_mime_type": None, "sources": []}

    if call is None:
        reply["text"] = gemini_client.extract_text(response)
    elif call.name == "search_documents":
        reply.update(_handle_search(call.args["query"]))
    elif call.name == "generate_image":
        reply.update(_handle_generate_image(call.args["prompt"]))
    else:
        reply["text"] = gemini_client.extract_text(response)

    return reply
