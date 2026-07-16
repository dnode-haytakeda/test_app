from pydantic import BaseModel, EmailStr, Field

BEARER_AUTH_SCHEME = "Bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = Field(default=BEARER_AUTH_SCHEME)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=256,
        description="Minimum 8 characters; no further policy is enforced.",
    )
    full_name: str | None = Field(default=None, max_length=255)