class AcademicError(Exception):
    """An expected operational failure, safe to display without a traceback."""


class ApiError(AcademicError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class Cancelled(AcademicError):
    def __init__(self, message: str = "Stopped by user.", exit_code: int = 130):
        super().__init__(message)
        self.exit_code = exit_code
