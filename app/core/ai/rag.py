"""RAG pipeline — embed → search → inject → generate."""


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline using Qdrant + OpenAI."""

    async def query(self, question: str, context: dict | None = None) -> dict:
        raise NotImplementedError

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError
