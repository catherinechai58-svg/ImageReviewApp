"""任务管理路由 — CRUD、执行、重做、日志、结果查询、下载。"""

import csv
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Attr, Key
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
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
_RETRY_ALLOWED_STATUSES = {"completed", "partial_completed", "failed"}

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
    template_ids: list[str] = []
    run_mode: str = ""
    model_id: str = ""
    date_from: str = ""
    date_to: str = ""


@router.post("", status_code=201)
async def create_task(body: CreateTaskRequest, user: dict = Depends(verify_token)):
    """POST /tasks — 创建任务。"""
    missing = []
    if not body.name:
        missing.append({"field": "name", "message": "任务名称不能为空"})
    if not body.channel_ids:
        missing.append({"field": "channel_ids", "message": "频道列表不能为空"})
    # 兼容 template_ids（多选）和 template_id（单选）
    effective_template_ids = body.template_ids or ([body.template_id] if body.template_id else [])
    if not effective_template_ids:
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

    template = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": effective_template_ids[0]})
    if not template:
        raise ValidationError("提示词模板不存在",
                              details=[{"field": "template_id", "message": f"模板 {effective_template_ids[0]} 不存在"}])

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
        "channel_ids": channel_ids,
        "template_id": effective_template_ids[0],
        "template_ids": effective_template_ids,
        "run_mode": body.run_mode, "model_id": model_id, "status": "pending",
        "date_from": body.date_from, "date_to": body.date_to,
        "total_images": 0, "success_count": 0, "failure_count": 0,
        "sfn_execution_arn": "", "created_by": user.get("username", ""),
        "created_at": now, "updated_at": now,
    }
    dynamodb.put_item(_TASKS_TABLE, item)
    return {"data": item, "message": "任务创建成功"}


@router.get("")
async def list_tasks(user: dict = Depends(verify_token)):
    """GET /tasks — 任务列表（只返回自己创建的）。"""
    username = user.get("username", "")
    items = dynamodb.scan_all(_TASKS_TABLE)
    mine = [it for it in items if it.get("created_by", "") == username]
    result = [
        {"task_id": it["task_id"], "name": it.get("name", ""),
         "template_id": it.get("template_id", ""),
         "status": it.get("status", ""), "created_at": it.get("created_at", ""),
         "updated_at": it.get("updated_at", "")}
        for it in mine
    ]
    return {"data": result, "message": "查询成功"}


@router.get("/{task_id}")
async def get_task(task_id: str, user: dict = Depends(verify_token)):
    """GET /tasks/{id} — 任务详情。"""
    item = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not item:
        raise NotFoundError(f"任务 {task_id} 不存在")
    return {"data": item, "message": "查询成功"}


_EDIT_ALLOWED_STATUSES = {"pending", "failed", "partial_completed", "completed"}


class UpdateTaskRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    channel_ids: list[str] | str | None = None
    template_id: str | None = None
    template_ids: list[str] | None = None
    run_mode: str | None = None
    model_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None


@router.put("/{task_id}")
async def update_task(task_id: str, body: UpdateTaskRequest, user: dict = Depends(verify_token)):
    """PUT /tasks/{id} — 编辑任务（仅 pending/failed/partial_completed/completed 状态可编辑）。"""
    task = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    status = task.get("status", "")
    if status not in _EDIT_ALLOWED_STATUSES:
        raise ValidationError(
            f"当前状态 '{status}' 不允许编辑，仅 {', '.join(sorted(_EDIT_ALLOWED_STATUSES))} 状态可编辑"
        )

    updates = {}
    if body.name is not None:
        if not body.name.strip():
            raise ValidationError("任务名称不能为空")
        updates["name"] = body.name.strip()
    if body.description is not None:
        updates["description"] = body.description.strip()
    if body.channel_ids is not None:
        raw = body.channel_ids if isinstance(body.channel_ids, list) else [body.channel_ids]
        parsed = [_parse_channel_id(ch) for ch in raw]
        parsed = [ch for ch in parsed if ch]
        if not parsed:
            raise ValidationError("解析后频道列表为空")
        updates["channel_ids"] = parsed
    if body.template_ids is not None:
        if not body.template_ids:
            raise ValidationError("提示词模板不能为空")
        tpl = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": body.template_ids[0]})
        if not tpl:
            raise ValidationError(f"模板 {body.template_ids[0]} 不存在")
        updates["template_ids"] = body.template_ids
        updates["template_id"] = body.template_ids[0]
    elif body.template_id is not None:
        tpl = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": body.template_id})
        if not tpl:
            raise ValidationError(f"模板 {body.template_id} 不存在")
        updates["template_id"] = body.template_id
        updates["template_ids"] = [body.template_id]
    if body.run_mode is not None:
        if body.run_mode not in _VALID_RUN_MODES:
            raise ValidationError(f"不支持的运行模式: {body.run_mode}")
        updates["run_mode"] = body.run_mode
    if body.model_id is not None:
        if not is_valid_model(body.model_id):
            raise ValidationError(f"不支持的模型: {body.model_id}")
        updates["model_id"] = body.model_id
    if body.date_from is not None:
        updates["date_from"] = body.date_from
    if body.date_to is not None:
        updates["date_to"] = body.date_to

    if not updates:
        return {"data": task, "message": "无更新内容"}

    # 编辑后重置状态为 pending，允许重新执行
    updates["status"] = "pending"
    updates["updated_at"] = _now_iso()

    set_parts = [f"#{k} = :{k}" for k in updates]
    expr_values = {f":{k}": v for k, v in updates.items()}
    expr_names = {f"#{k}": k for k in updates}

    dynamodb.update_item(
        _TASKS_TABLE, key={"task_id": task_id},
        update_expression="SET " + ", ".join(set_parts),
        expression_values=expr_values,
        expression_names=expr_names,
    )

    updated = {**task, **updates}
    return {"data": updated, "message": "任务更新成功"}


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
        "review_rules": template.get("review_rules", ""),
        "date_from": task.get("date_from", ""), "date_to": task.get("date_to", ""),
    }

    now = _now_iso()
    dynamodb.update_item(
        _TASKS_TABLE, key={"task_id": task_id},
        update_expression="SET #s = :status, updated_at = :now",
        expression_values={":status": "queued", ":now": now},
        expression_names={"#s": "status"},
    )

    task_worker.submit_execute(task_id, payload)
    if task_worker.is_at_capacity():
        return {"data": {"task_id": task_id}, "message": "任务已排队，等待执行"}
    return {"data": {"task_id": task_id}, "message": "任务已提交执行"}


@router.post("/{task_id}/retry", status_code=202)
async def retry_task(task_id: str, user: dict = Depends(verify_token)):
    """POST /tasks/{id}/retry — 智能重做（根据失败情况选择策略）。"""
    task = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    status = task.get("status", "")
    if status not in _RETRY_ALLOWED_STATUSES:
        raise ValidationError(
            f"当前状态 '{status}' 不允许重做，仅 {', '.join(sorted(_RETRY_ALLOWED_STATUSES))} 状态可重做"
        )

    from backend.shared.logger import write_task_log
    
    # 查询失败结果
    failed_results = dynamodb.query_all_pages(
        _TASK_RESULTS_TABLE,
        key_condition=Key("task_id").eq(task_id) & Key("status").eq("failed"),
        index_name="TaskStatusIndex",
    )
    
    # 查询所有结果
    all_results = dynamodb.query_all_pages(
        _TASK_RESULTS_TABLE,
        key_condition=Key("task_id").eq(task_id),
    )

    template = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": task.get("template_id", "")})
    if not template:
        raise ValidationError(f"关联的提示词模板 {task.get('template_id', '')} 不存在")

    # 情况1: 没有任何结果 → 从头开始
    if not all_results:
        write_task_log(task_id, "retry", "route", "info", "无结果记录，从头开始")
        payload = {
            "task_id": task_id, "channel_ids": task.get("channel_ids", []),
            "run_mode": task.get("run_mode", "batch"),
            "model_id": task.get("model_id", get_default_model_id()),
            "system_prompt": template.get("system_prompt", ""),
            "user_prompt": template.get("user_prompt", ""),
            "review_rules": template.get("review_rules", ""),
            "date_from": task.get("date_from", ""), "date_to": task.get("date_to", ""),
        }
        dynamodb.update_item(_TASKS_TABLE, key={"task_id": task_id},
            update_expression="SET #s = :status, updated_at = :now",
            expression_values={":status": "queued", ":now": _now_iso()},
            expression_names={"#s": "status"})
        task_worker.submit_execute(task_id, payload)
        return {"data": {"task_id": task_id}, "message": "重做任务已提交（完整流程）"}
    
    # 情况2: 图片未下载 → 从下载开始
    if not any(r.get("s3_key") for r in all_results):
        write_task_log(task_id, "retry", "route", "info", "图片未下载，从下载开始")
        images = [{"image_name": r.get("image_name", ""), "video_id": r.get("video_id", ""),
                   "channel_id": r.get("channel_id", ""), "channel_name": r.get("channel_name", ""),
                   "thumbnail_url": f"https://i.ytimg.com/vi/{r.get('video_id', '')}/mqdefault.jpg"}
                  for r in all_results if r.get("image_name")]
        payload = {
            "task_id": task_id, "images": images, "skip_channel_fetch": True,
            "run_mode": task.get("run_mode", "batch"),
            "model_id": task.get("model_id", get_default_model_id()),
            "system_prompt": template.get("system_prompt", ""),
            "user_prompt": template.get("user_prompt", ""),
            "review_rules": template.get("review_rules", ""),
            "date_from": task.get("date_from", ""), "date_to": task.get("date_to", ""),
        }
        dynamodb.update_item(_TASKS_TABLE, key={"task_id": task_id},
            update_expression="SET #s = :status, updated_at = :now",
            expression_values={":status": "queued", ":now": _now_iso()},
            expression_names={"#s": "status"})
        task_worker.submit_execute(task_id, payload)
        return {"data": {"task_id": task_id}, "message": f"重做任务已提交（从下载开始，{len(images)}张图片）"}
    
    # 情况3: 有失败结果 → 只重做失败的
    if failed_results:
        write_task_log(task_id, "retry", "route", "info", f"重做{len(failed_results)}个失败图片")
        failed_images = [{"image_name": r.get("image_name", ""), "s3_key": r.get("s3_key", ""),
                          "video_id": r.get("video_id", ""), "channel_id": r.get("channel_id", ""),
                          "channel_name": r.get("channel_name", "")} for r in failed_results]
        payload = {
            "task_id": task_id, "failed_images": failed_images,
            "run_mode": task.get("run_mode", "batch"),
            "model_id": task.get("model_id", get_default_model_id()),
            "system_prompt": template.get("system_prompt", ""),
            "user_prompt": template.get("user_prompt", ""),
            "review_rules": template.get("review_rules", ""),
            "date_from": task.get("date_from", ""), "date_to": task.get("date_to", ""),
        }
        dynamodb.update_item(_TASKS_TABLE, key={"task_id": task_id},
            update_expression="SET #s = :status, updated_at = :now",
            expression_values={":status": "queued", ":now": _now_iso()},
            expression_names={"#s": "status"})
        task_worker.submit_retry(task_id, payload)
        return {"data": {"task_id": task_id}, "message": f"重做任务已提交（{len(failed_images)}个失败图片）"}
    
    # 情况4: 全部成功
    return {"data": {"task_id": task_id}, "message": "所有图片都已成功，无需重做"}
    
    write_task_log(task_id, "retry_submit", "route", "success", "重做任务已提交到后台队列")
    return {"data": {"task_id": task_id, "failed_count": len(failed_images)}, "message": "重做任务已提交"}


@router.post("/{task_id}/retry-all", status_code=202)
async def retry_all_task(task_id: str, user: dict = Depends(verify_token)):
    """POST /tasks/{id}/retry-all — 强制重做全部图片。"""
    task = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    status = task.get("status", "")
    if status not in _RETRY_ALLOWED_STATUSES:
        raise ValidationError(
            f"当前状态 '{status}' 不允许重做，仅 {', '.join(sorted(_RETRY_ALLOWED_STATUSES))} 状态可重做"
        )

    from backend.shared.logger import write_task_log

    all_results = dynamodb.query_all_pages(
        _TASK_RESULTS_TABLE, key_condition=Key("task_id").eq(task_id),
    )
    if not all_results:
        raise ValidationError("没有任何结果记录，请先执行任务")

    template = dynamodb.get_item(_PROMPT_TEMPLATES_TABLE, {"template_id": task.get("template_id", "")})
    if not template:
        raise ValidationError(f"关联的提示词模板 {task.get('template_id', '')} 不存在")

    # 所有有 s3_key 的图片直接重做推理
    images_with_key = [r for r in all_results if r.get("s3_key")]
    if not images_with_key:
        raise ValidationError("图片未下载，请使用普通重做")

    write_task_log(task_id, "retry_all", "route", "info", f"强制重做全部 {len(images_with_key)} 张图片")

    payload = {
        "task_id": task_id, "failed_images": images_with_key,
        "run_mode": task.get("run_mode", "batch"),
        "model_id": task.get("model_id", get_default_model_id()),
        "system_prompt": template.get("system_prompt", ""),
        "user_prompt": template.get("user_prompt", ""),
        "review_rules": template.get("review_rules", ""),
        "date_from": task.get("date_from", ""), "date_to": task.get("date_to", ""),
    }
    dynamodb.update_item(_TASKS_TABLE, key={"task_id": task_id},
        update_expression="SET #s = :status, updated_at = :now",
        expression_values={":status": "queued", ":now": _now_iso()},
        expression_names={"#s": "status"})
    task_worker.submit_retry(task_id, payload)
    return {"data": {"task_id": task_id}, "message": f"强制重做已提交（全部 {len(images_with_key)} 张图片）"}


_DELETE_ALLOWED_STATUSES = {"pending", "completed", "failed", "partial_completed"}


@router.delete("/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(verify_token)):
    """DELETE /tasks/{id} — 删除任务及其结果和日志。"""
    task = dynamodb.get_item(_TASKS_TABLE, {"task_id": task_id})
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    status = task.get("status", "")
    if status not in _DELETE_ALLOWED_STATUSES:
        raise ValidationError(f"当前状态 '{status}' 不允许删除，运行中的任务无法删除")

    # 删除关联结果
    results = dynamodb.query_all_pages(_TASK_RESULTS_TABLE, key_condition=Key("task_id").eq(task_id))
    for r in results:
        dynamodb.delete_item(_TASK_RESULTS_TABLE, {"task_id": task_id, "image_name": r["image_name"]})

    # 删除关联日志
    logs = dynamodb.query_all_pages(_TASK_LOGS_TABLE, key_condition=Key("task_id").eq(task_id))
    for log in logs:
        dynamodb.delete_item(_TASK_LOGS_TABLE, {"task_id": task_id, "timestamp": log["timestamp"]})

    dynamodb.delete_item(_TASKS_TABLE, {"task_id": task_id})
    return {"message": "任务删除成功"}


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
    exclude_teen: bool = Query(default=False),
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

    response = {"data": result["Items"]}
    if exclude_teen:
        def _is_teen(item: dict) -> bool:
            rj = item.get("result_json") or {}
            detail = rj.get("review_detail", [{}])
            detail_obj = detail[0] if isinstance(detail, list) and detail else (detail if isinstance(detail, dict) else {})
            return detail_obj.get("age_group") == "teen"
        response["data"] = [r for r in result["Items"] if not _is_teen(r)]
    if "LastEvaluatedKey" in result:
        response["last_evaluated_key"] = result["LastEvaluatedKey"]
    return response


@router.get("/{task_id}/results/download")
async def download_results(task_id: str, user: dict = Depends(verify_token)):
    """GET /tasks/{id}/results/download — 生成 CSV 下载（排除 age_group=teen 的记录）。"""
    from backend.shared.dynamodb import query_all_pages
    from decimal import Decimal

    def _to_native(obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        elif isinstance(obj, dict):
            return {k: _to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_to_native(i) for i in obj]
        return obj

    all_rows = query_all_pages(
        table_name=_TASK_RESULTS_TABLE,
        key_condition=Key("task_id").eq(task_id),
    )

    # 过滤掉 age_group == "teen" 的记录
    filtered = []
    for r in all_rows:
        rj = _to_native(r.get("result_json") or {})
        detail = rj.get("review_detail", [{}])
        detail_obj = detail[0] if isinstance(detail, list) and detail else (detail if isinstance(detail, dict) else {})
        if detail_obj.get("age_group") == "teen":
            continue
        filtered.append((r, rj, detail_obj))

    # 收集所有 result_json 字段名作为动态列
    detail_keys: list[str] = []
    for _, _, detail_obj in filtered:
        for k in detail_obj.keys():
            if k not in detail_keys:
                detail_keys.append(k)

    base_cols = ["task_id", "video_id", "channel_id", "channel_name", "status", "review_result"]
    fieldnames = base_cols + detail_keys

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r, rj, detail_obj in filtered:
        row = {
            "task_id": r.get("task_id", ""),
            "video_id": r.get("video_id", ""),
            "channel_id": r.get("channel_id", ""),
            "channel_name": r.get("channel_name", ""),
            "status": r.get("status", ""),
            "review_result": r.get("review_result", ""),
        }
        row.update({k: detail_obj.get(k, "") for k in detail_keys})
        writer.writerow(row)

    output.seek(0)
    filename = f"results_{task_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
