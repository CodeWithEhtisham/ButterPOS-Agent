from pydantic import BaseModel, EmailStr


class TokenRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: int
    email: str
    name: str
    role: str
    restaurant_id: int
    branch_id: int | None = None
