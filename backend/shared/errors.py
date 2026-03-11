"""自定义异常类型，用于 Lambda handler 统一错误处理。"""


class AppError(Exception):
    """应用层基础异常。"""

    def __init__(self, code: str, message: str, status_code: int = 400, details: list | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class ValidationError(AppError):
    """请求参数验证失败 → 400"""

    def __init__(self, message: str = "请求参数不合法", details: list | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details,
        )


class NotFoundError(AppError):
    """资源不存在 → 404"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=404,
        )


class ConflictError(AppError):
    """业务逻辑冲突 → 409"""

    def __init__(self, message: str = "操作冲突", details: list | None = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=409,
            details=details,
        )


class AuthenticationError(AppError):
    """认证失败 → 401"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(
            code="AUTHENTICATION_ERROR",
            message=message,
            status_code=401,
        )
