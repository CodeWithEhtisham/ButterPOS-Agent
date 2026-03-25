"""KB article management + version control."""


class KBService:
    """Manages knowledge base articles with versioning and bilingual content."""

    async def create_article(self, data: dict) -> dict:
        raise NotImplementedError

    async def update_article(self, article_id: int, data: dict) -> dict:
        raise NotImplementedError

    async def get_article(self, article_id: int) -> dict:
        raise NotImplementedError

    async def search_articles(self, query: str, category: str | None = None) -> list[dict]:
        raise NotImplementedError

    async def rollback_version(self, article_id: int, version: int) -> dict:
        raise NotImplementedError
