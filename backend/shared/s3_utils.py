"""S3 工具函数，封装文件上传、下载、预签名 URL 生成和路径构建。"""

import os
import boto3
from botocore.exceptions import ClientError


def _get_client():
    """获取 S3 client（便于测试时替换）。"""
    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url)


def _get_bucket():
    """获取默认 S3 桶名。"""
    return os.environ["IMAGE_BUCKET"]


# ---------------------------------------------------------------------------
# 路径构建函数
# ---------------------------------------------------------------------------

def build_s3_path(task_id: str, filename: str) -> str:
    """构建图片输入路径。

    Args:
        task_id: 任务 ID
        filename: 文件名（如 video_id.jpg）

    Returns:
        S3 key，格式为 tasks/{task_id}/input/{filename}
    """
    return f"tasks/{task_id}/input/{filename}"


def build_input_path(task_id: str, filename: str) -> str:
    """构建输入目录下的文件路径（与 build_s3_path 等价）。"""
    return f"tasks/{task_id}/input/{filename}"


def build_output_path(task_id: str, filename: str) -> str:
    """构建输出目录下的文件路径。

    Args:
        task_id: 任务 ID
        filename: 文件名（如 results.json）

    Returns:
        S3 key，格式为 tasks/{task_id}/output/{filename}
    """
    return f"tasks/{task_id}/output/{filename}"


def build_batch_input_path(task_id: str) -> str:
    """构建批量推理 JSONL 输入路径。

    Returns:
        S3 key，格式为 tasks/{task_id}/input/batch_input.jsonl
    """
    return f"tasks/{task_id}/input/batch_input.jsonl"


def build_results_path(task_id: str) -> str:
    """构建结果 JSON 文件路径。

    Returns:
        S3 key，格式为 tasks/{task_id}/output/results.json
    """
    return f"tasks/{task_id}/output/results.json"


# ---------------------------------------------------------------------------
# S3 操作函数
# ---------------------------------------------------------------------------

def upload_file(bucket: str | None, key: str, body: bytes | str) -> None:
    """上传文件内容到 S3。

    Args:
        bucket: S3 桶名，None 时使用环境变量 IMAGE_BUCKET
        key: S3 对象键
        body: 文件内容（bytes 或 str）
    """
    client = _get_client()
    bucket = bucket or _get_bucket()
    if isinstance(body, str):
        body = body.encode("utf-8")
    client.put_object(Bucket=bucket, Key=key, Body=body)


def download_file(bucket: str | None, key: str) -> bytes:
    """从 S3 下载文件内容。

    Args:
        bucket: S3 桶名，None 时使用环境变量 IMAGE_BUCKET
        key: S3 对象键

    Returns:
        文件内容 bytes

    Raises:
        ClientError: S3 操作失败时抛出
    """
    client = _get_client()
    bucket = bucket or _get_bucket()
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def generate_presigned_url(bucket: str | None, key: str, expiration: int = 3600) -> str:
    """生成 S3 预签名下载 URL。

    Args:
        bucket: S3 桶名，None 时使用环境变量 IMAGE_BUCKET
        key: S3 对象键
        expiration: URL 有效期（秒），默认 3600

    Returns:
        预签名 URL 字符串
    """
    client = _get_client()
    bucket = bucket or _get_bucket()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiration,
    )


def list_objects(bucket: str | None, prefix: str) -> list[str]:
    """列出 S3 指定前缀下的所有对象键。

    Args:
        bucket: S3 桶名，None 时使用环境变量 IMAGE_BUCKET
        prefix: S3 前缀

    Returns:
        对象键列表
    """
    client = _get_client()
    bucket = bucket or _get_bucket()
    keys = []
    params = {"Bucket": bucket, "Prefix": prefix}

    while True:
        response = client.list_objects_v2(**params)
        for obj in response.get("Contents", []):
            keys.append(obj["Key"])
        if not response.get("IsTruncated"):
            break
        params["ContinuationToken"] = response["NextContinuationToken"]

    return keys
