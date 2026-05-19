from fastapi import HTTPException, status


class VirtusException(HTTPException):
    """Base application exception."""


class NotFoundException(VirtusException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found.",
        )


class UnauthorizedException(VirtusException):
    def __init__(self, detail: str = "Not authenticated."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(VirtusException):
    def __init__(self, detail: str = "Permission denied."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictException(VirtusException):
    def __init__(self, detail: str = "Resource already exists."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BadRequestException(VirtusException):
    def __init__(self, detail: str = "Bad request."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
