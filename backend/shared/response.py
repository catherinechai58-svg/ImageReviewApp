"""统一响应构建函数和 Lambda handler 错误处理装饰器。"""

import json
import functools
import traceback
import re

from backend.shared.errors import AppError


def success_response(data=None, message: str = "操作成功", status_code: int = 200) -> dict:
    """构建成功响应。"""
    body = {"message": message}
    if data is not None:
        body["data"] = data
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def error_response(code: str, message: str, status_code: int = 400, details: list | None = None) -> dict:
    """构建错误响应。"""
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": error}, ensure_ascii=False),
    }


# 用于检测内部细节泄露的模式
_INTERNAL_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r'File ".*\.py"', re.IGNORECASE),
    re.compile(r"/[a-zA-Z_][\w/]*\.py", re.IGNORECASE),
    re.compile(r"\\[a-zA-Z_][\w\\]*\.py", re.IGNORECASE),
    re.compile(r"\b\w+Table\b"),
    re.compile(r"\barn:aws:", re.IGNORECASE),
]


def _contains_internal_details(text: str) -> bool:
    """检查文本是否包含内部实现细节。"""
    return any(p.search(text) for p in _INTERNAL_PATTERNS)


def lambda_handler(func):
    """Lambda handler 错误处理装饰器。

    捕获异常并返回对应 HTTP 状态码：
    - AppError 子类 → 对应 status_code
    - 其他异常 → 500，返回通用错误信息，不暴露内部细节
    """

    @functools.wraps(func)
    def wrapper(event, context):
        try:
            return func(event, context)
        except AppError as e:
            # 确保即使是应用层错误也不泄露内部细节
            message = e.message
            if _contains_internal_details(message):
                message = "请求处理失败"
            details = e.details
            if details:
                details = [
                    {k: v for k, v in d.items() if not (isinstance(v, str) and _contains_internal_details(v))}
                    for d in details
                ]
            return error_response(
                code=e.code,
                message=message,
                status_code=e.status_code,
                details=details,
            )
        except Exception:
            # 500 错误：只返回通用信息，不暴露任何内部细节
            traceback.print_exc()  # 仅输出到 CloudWatch 日志
            return error_response(
                code="INTERNAL_ERROR",
                message="服务器内部错误",
                status_code=500,
            )

    return wrapper
