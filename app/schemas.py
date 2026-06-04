"""Pydantic models — API 的 request / response 形狀。

跟 ORM models（app/models.py）分開：ORM 是 DB 表的 mapping，
這裡是對外的 API 契約。response 用的 schema 開 from_attributes，
FastAPI 才能直接吃 ORM 物件做序列化。
"""

from pydantic import BaseModel, ConfigDict, Field


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str


class Post(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    content: str
    likes: int = 0


class MessageIn(BaseModel):
    sender_id: int
    recipient_id: int
    content: str = Field(min_length=1, max_length=500)


class MessageOut(MessageIn):
    id: int
    status: str = "delivered"
