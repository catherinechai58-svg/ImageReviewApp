"""任务管理路由 — CRUD、执行、重做、日志、结果查询、下载。"""

import json
import os
import re
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Attr, Key
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.auth import verify_token
from backend.app.models_config import get_default_model_id, is_valid_model
from backend.app.response import success_response
from backend.app.worker import task_worker
from backend.shared import dynamodb
from backend.shared.errors import NotFoundError, ValidationError
from backend.shared.s3_utils import build_results_path, generate_presigned_url

router = APIRouter()

_TASKS_TABLE = os.environ.get("TASKS_TABLE", "Tasks")
_TASK_RESULTS_TABLE = os.environ.get("TASK_RESULTS_TABLE", "TaskResults")
_TASK_LOGS_TABLE = os.environ.get("TASK_LOGS_TABLE", "TaskLogs")
_PROMPT_TEMPLATES_TABLE = os.environ.get("PROMPT_TEMPLATES_TABLE", "PromptTemplates")

_VALID_RUN_MODES = {"batch", "realtime"}
_EXECUTE_ALLOWED_STATUSES = {"pending", "failed", "partial_completed"}
_RETRY_ALLOWED_STATUSES = {"completed", "partial_completed"}

_CHANNEL_URL_RE = re.compile(r"https?://(?:www\.)?youtube\.com/channel/([a-zA-Z0-9_-]+)")
_HANDLE_URL_RE = re.compile(r"https?://(?:www\.)?youtube\.com/@([a-zA-Z0-9_.-]+)")

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_channel_id(raw: str) -> str:
    """解析频道 URL 或 ID。"""
    raw = raw.strip()
    if not raw:
        return raw
    m = _CHANNEL_URL_RE.match(raw)
    if m:
        return m.group(1)
    m = _HANDLE_URL_RE.match(raw)
    if m:
        return f"@{m.group(1)}"
    return raw


class CreateTaskRequest(BaseModel):
    name: str = ""
    description: str = ""
    channel_ids: list[str] | str = []
    template_id: str = ""
    run_mode: str = ""
    model_id: str = ""
    created_by: str = ""


@router.post("", status_code=201)
async def create_task(body: CreateTaskRequest, user: dict = Depends(verify_token)):
    """POST /tasks — 创建任务。"""
    missing = []
    if not body.name:
        missing.append({"field": "name", "message": "任务名称不能为空"})
    if not body.channel_ids:
        missing.append({"field": "channel_ids", "message": "频道列表不能为空"})
    if not body.template_id:
        missing.append({"field": "template_id", "message": "提示词模板 ID 不能为空"})
    if not body.run_mode:
        missing.append({"field": "run_mode", "message": "运行模式不能为空"})
    if missing:
        raise ValidationError("请求参数不完整", details=missing)

    if body.run_mode not in _VALID_RUN_MODES:
        raise ValidationError(
            f"运行模式不合法，仅支持: {', '.join(sorted(_VALID_RUN_MODES))}",
            details=[{"field": "run_mode", "message": f"不支持的运行模式: {body.run_mode}"}],
        )

    # 模型 ID：未指定时使用默认值，指定时验证合法性
    model_id = body.model_id or get_default_model_id()
    if not is_valid_model(model_id):
        raise ValidationError(
            f"不支持的模型: {model_id}",
            details=[{"field": "model_id", "message": f"模型 {model_id} 不在可选列表中"}],
        )

    template = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": body.template_id})
    if not template:
        raise ValidationError("提示词模板不存在",
                              details=[{"field": "template_id", "message": f"模板 {body.template_id} 不存在"}])

    raw_channels = body.channel_ids if isinstance(body.channel_ids, list) else [body.channel_ids]
    channel_ids = [_parse_channel_id(ch) for ch in raw_channels]
    channel_ids = [ch for ch in channel_ids if ch]
    if not channel_ids:
        raise ValidationError("解析后频道列表为空",
                              details=[{"field": "channel_ids", "message": "未能解析出有效的频道 ID"}])

    now = _now_iso()
    task_id = str(uuid.uuid4())
    item = {
        "task_id": task_id, "name": body.name, "description": body.description,
        "channel_ids": channel_ids, "template_id": body.template_id,
        "run_mode": body.run_mode, "model_id": model_id, "status": "pending",
        "total_images": 0, "success_count": 0, "failure_count": 0,
        "sfn_execution_arn": "", "created_by": body.created_by,
        "created_at": now, "updated_at": now,
    }
    dynamodb.put_item(_TASKS_TABLE, item)
    return {"data": item, "message": "任务创建成功"}


@router.get("")
async def list_tasks(user: dict = Depends(verify_token)):
    """GET /tasks — 任务列表。"""
    items = dynamodb.scan_all(_TASKS_TABLE)
    result = [
        {"task_id": it["task_id"], "name": it.get("name", ""),
         "status": it.get("status", ""), "created_at": it.get("created_at", ""),
         "updated_at": it.get("updated_at", "")}
        for it in items
    ]
    return {"data": result, "message": "查询成功"}


@router.get("/{task_id}")
async def get_task(task_id: str, user: dict = Depends(verify_token)):
    """GET /tasks/{id} — 任务详情。"""
    item = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not item:
        raise NotFoundError(f"任务 {task_id} 不存在")
    return {"data": item, "message": "查询成功"}


@router.post("/{task_id}/execute", status_code=202)
async def execute_task(task_id: str, user: dict = Depends(verify_token)):
    """POST /tasks/{id}/execute — 触发完整工作流。"""
    task = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    status = task.get("status", "")
    if status not in _EXECUTE_ALLOWED_STATUSES:
        raise ValidationError(
            f"当前状态 '{status}' 不允许执行，仅 {', '.join(sorted(_EXECUTE_ALLOWED_STATUSES))} 状态可执行"
        )

    template = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": task.get("template_id", "")})
    if not template:
        raise ValidationError(f"关联的提示词模板 {task.get('template_id', '')} 不存在")

    payload = {
        "task_id": task_id, "channel_ids": task.get("channel_ids", []),
        "template_id": task.get("template_id", ""), "run_mode": task.get("run_mode", "batch"),
        "model_id": task.get("model_id", get_default_model_id()),
        "system_prompt": template.get("system_prompt", ""),
        "user_prompt": template.get("user_prompt", ""),
    }

    now = _now_iso()
    dynamodb.update_item(
        _TASKS_TABLE, key={"task_id": task_id},
        update_expression="SET #s = :status, updated_at = :now",
        expression_values={":status": "fetching", ":now": now},
        expression_names={"#s": "status"},
    )

    task_worker.submit_execute(task_id, payload)
    return {"data": {"task_id": task_id}, "message": "任务已提交执行"}


@router.post("/{task_id}/retry", status_code=202)
async def retry_task(task_id: str, user: dict = Depends(verify_token)):
    """POST /tasks/{id}/retry — 重做失败图片。"""
    task = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    status = task.get("status", "")
    if status not in _RETRY_ALLOWED_STATUSES:
        raise ValidationError(
            f"当前状态 '{status}' 不允许重做，仅 {', '.join(sorted(_RETRY_ALLOWED_STATUSES))} 状态可重做"
        )

    failed_results = dynamodb.query_all_pages(
        _TASK_RESULTS_TABLE,
        key_condition=Key("task_id").eq(task_id),
        index_name="TaskStatusIndex",
        filter_expression=Attr("status").eq("failed"),
    )
    if not failed_results:
        return {"data": {"task_id": task_id, "failed_count": 0}, "message": "没有失败的图片需要重做"}

    template = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": task.get("template_id", "")})
    if not template:
        raise ValidationError(f"关联的提示词模板 {task.get('template_id', '')} 不存在")

    failed_images = [
        {"image_name": r.get("image_name", ""), "s3_key": r.get("s3_key", ""),
         "video_id": r.get("video_id", ""), "channel_id": r.get("channel_id", ""),
         "channel_name": r.get("channel_name", "")}
        for r in failed_results
    ]

    payload = {
        "task_id": task_id, "run_mode": task.get("run_mode", "batch"),
        "model_id": task.get("model_id", get_default_model_id()),
        "system_prompt": template.get("system_prompt", ""),
        "user_prompt": template.get("user_prompt", ""),
        "failed_images": failed_images,
    }

    now = _now_iso()
    dynamodb.update_item(
        _TASKS_TABLE, key={"task_id": task_id},
        update_expression="SET #s = :status, updated_at = :now",
        expression_values={":status": "recognizing", ":now": now},
        expression_names={"#s": "status"},
    )

    task_worker.submit_retry(task_id, payload)
    return {"data": {"task_id": task_id, "failed_count": len(failed_images)}, "message": "重做任务已提交"}


@router.get("/{task_id}/logs")
async def get_task_logs(task_id: str, user: dict = Depends(verify_token)):
    """GET /tasks/{id}/logs — 查询任务日志。"""
    logs = dynamodb.query_all_pages(
        table_name=_TASK_LOGS_TABLE,
        key_condition=Key("task_id").eq(task_id),
        scan_forward=True,
    )
    return {"data": logs, "message": "查询成功"}


@router.get("/{task_id}/results")
async def get_task_results(
    task_id: str,
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    last_evaluated_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    review_result: str | None = Query(default=None),
    user: dict = Depends(verify_token),
):
    """GET /tasks/{id}/results — 分页查询结果。"""
    last_key = None
    if last_evaluated_key:
        try:
            last_key = json.loads(last_evaluated_key)
        except (json.JSONDecodeError, TypeError):
            raise ValidationError("last_evaluated_key 必须为有效的 JSON 字符串")

    # 选择最优索引和构建查询
    filter_expr = None
    index_name = None
    key_cond = Key("task_id").eq(task_id)

    if status and not review_result:
        index_name = "TaskStatusIndex"
        key_cond = Key("task_id").eq(task_id) & Key("status").eq(status)
    elif review_result and not status:
        index_name = "TaskReviewIndex"
        key_cond = Key("task_id").eq(task_id) & Key("review_result").eq(review_result)
    else:
        if status:
            filter_expr = Attr("status").eq(status)
        if review_result:
            cond = Attr("review_result").eq(review_result)
            filter_expr = (filter_expr & cond) if filter_expr else cond

    result = dynamodb.query(
        table_name=_TASK_RESULTS_TABLE,
        key_condition=key_cond,
        index_name=index_name,
        filter_expression=filter_expr,
        limit=page_size,
        exclusive_start_key=last_key,
    )

    data = {"items": result["Items"], "count": len(result["Items"])}
    if "LastEvaluatedKey" in result:
        data["last_evaluated_key"] = result["LastEvaluatedKey"]
    return {"data": data, "message": "查询成功"}


@router.get("/{task_id}/results/download")
async def download_results(task_id: str, user: dict = Depends(verify_token)):
    """GET /tasks/{id}/results/download — 生成预签名下载 URL。"""
    s3_key = build_results_path(task_id)
    url = generate_presigned_url(bucket=None, key=s3_key)
    return {"data": {"download_url": url, "s3_key": s3_key}, "message": "查询成功"}
