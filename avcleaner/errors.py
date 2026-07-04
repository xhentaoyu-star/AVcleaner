from __future__ import annotations


class AppError(Exception):
    def __init__(self, error_code: str, status_code: int = 400, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message or error_code
