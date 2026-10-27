from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = "student"  # student | parent | faculty (admin cannot self-register)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    category: Optional[str] = "all"


class Source(BaseModel):
    id: int
    source: Optional[str]
    page: Optional[int]
    category: Optional[str]
    url: Optional[str] = None
    snippet: str


class ChatOut(BaseModel):
    answer: str
    sources: List[Source]


class HistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    sources: List[Source]
    created_at: datetime


class DocumentOut(BaseModel):
    id: int
    filename: str
    category: str
    chunks: int
    uploaded_at: datetime

    class Config:
        from_attributes = True
