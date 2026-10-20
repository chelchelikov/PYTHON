class ApiError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(ApiError):
    code = "VALIDATION_ERROR"


class RoomNotFoundError(ApiError):
    status_code = 404
    code = "ROOM_NOT_FOUND"


class ConflictError(ApiError):
    status_code = 409
    code = "CONFLICT"
