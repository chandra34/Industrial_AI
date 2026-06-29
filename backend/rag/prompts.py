from backend.rag.retrieval import RetrievedChunk

SYSTEM_PROMPT = """You are a careful RAG assistant.
Use only the provided context when possible.
If the answer cannot be grounded in the context, say you do not know and explain what is missing.
Be concise, accurate, and helpful.
"""


def build_messages(question: str, chunks: list[RetrievedChunk], max_chars: int) -> list[dict[str, str]]:
    segments: list[str] = []
    current_length = 0
    for chunk in chunks:
        segment = (
            f"[Source: {chunk.source_filename} | Page {chunk.page_number} | "
            f"Chunk {chunk.chunk_index} | Score {chunk.score:.4f}]\n"
            f"{chunk.chunk_text.strip()}"
        )
        if current_length + len(segment) > max_chars:
            break
        segments.append(segment)
        current_length += len(segment)

    context = "\n\n".join(segments).strip()
    user_prompt = (
        "Answer the question using the context below. "
        "If the context is insufficient, say so clearly.\n\n"
        f"Context:\n{context or 'No relevant context found.'}\n\n"
        f"Question: {question}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
