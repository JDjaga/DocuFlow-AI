"""Small reusable response schemas shared by several routers."""
from pydantic import BaseModel


class Message(BaseModel):
    """Simple `{ "detail": "..." }` response used for confirmations."""
    detail: str


class PageMeta(BaseModel):
    """Pagination metadata returned with every list endpoint."""
    total: int
    page: int
    page_size: int
    pages: int
