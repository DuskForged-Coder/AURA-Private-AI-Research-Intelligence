from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QueryIn(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=6, ge=1, le=12)


class Citation(BaseModel):
    source_id: str
    filename: str
    chunk_id: str
    excerpt: str
    page_number: int | None
    score: float


class SearchOut(BaseModel):
    query: str
    results: list[Citation]


class AskIn(QueryIn):
    conversation_id: str | None = None


class AskOut(BaseModel):
    conversation_id: str
    answer: str
    abstained: bool
    citations: list[Citation]


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list[dict] | None
    created_at: datetime


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
