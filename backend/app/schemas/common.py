from pydantic import BaseModel


class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    request_id: str | None = None
    errors: list[FieldError] | None = None