"""FastAPI 统一响应和异常处理 — 与现有 Lambda 响应格式完全一致。"""

import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.shared.errors import AppError


def success_response(data=None, message: str = "操作成功") -> dict:
    """构建成功响应体（与 Lambda 格式一致）。"""
    body = {"message": message}
    if data is not None:
        body["data"] = data
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """注册 FastAPI 全局异常处理器。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        error = {"code": exc.code, "message": exc.message}
        if exc.details:
            error["details"] = exc.details
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}},
        )
