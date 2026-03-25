from pydantic import BaseModel
from typing import Optional, Generic, TypeVar

T = TypeVar("T")


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
