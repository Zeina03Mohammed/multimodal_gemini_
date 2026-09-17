"""
Splits raw document text into overlapping chunks for embedding.

Why chunk at all instead of embedding a whole document as one vector? Two
reasons: (1) embedding models have an input size limit, and (2) a single
vector for an entire document blurs together all its topics, so retrieval
gets worse, not better. Small, focused chunks retrieve more precisely.

Why overlap chunks instead of cutting them back-to-back? A sentence that
happens to fall right on a chunk boundary would otherwise be split in half
and lose its meaning in both halves. Overlap keeps that context intact.
"""

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split on paragraph breaks first, then greedily pack paragraphs into
    chunks close to `chunk_size` characters. A paragraph longer than
    `chunk_size` on its own gets hard-split with overlap.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(paragraph, chunk_size, overlap))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > chunk_size:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
