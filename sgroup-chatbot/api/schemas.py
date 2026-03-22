from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    agent_used: str
    session_id: str


class LongMemoryUpsertRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    preferences: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    memory_summary: str = ""
