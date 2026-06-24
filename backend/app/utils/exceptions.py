from typing import Any


class AppError(Exception):
    """An expected business error safe to expose through the common API contract."""

    def __init__(self, status_code: int, message: str, data: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.data = data
        super().__init__(message)
