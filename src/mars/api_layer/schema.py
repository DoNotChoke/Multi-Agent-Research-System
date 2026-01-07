from pydantic import BaseModel, Field

class Input(BaseModel):
    user_input: str = Field(str, description="user's query")