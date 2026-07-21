/** バックエンドのエラーコード列挙 (app/core/errors.py::ErrorCode と同期)。 */
export type ApiErrorCode =
    | "VALIDATION_ERROR"
    | "NOT_FOUND"
    | "UNAUTHORIZED"
    | "FORBIDDEN"
    | "CONFLICT"
    | "RATE_LIMITED"
    | "PAYLOAD_TOO_LARGE"
    | "SERVICE_UNAVAILABLE"
    | "INTERNAL_ERROR";

export interface FieldError {
    field: string;
    message: string;
}

export interface ApiErrorBody {
    detail: string;
    error_code: ApiErrorCode | string;
    request_id: string | null;
    errors: FieldError[] | null;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    limit: number;
    offset: number;
}
