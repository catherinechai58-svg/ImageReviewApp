"""提示词模板 CRUD 路由 — 复用 prompt_handler.py 业务逻辑。"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth import verify_token
from backend.shared import dynamodb
from backend.shared.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter()

_TEMPLATES_TABLE = os.environ.get("PROMPT_TEMPLATES_TABLE", "PromptTemplates")
_HISTORY_TABLE = os.environ.get("PROMPT_TEMPLATE_HISTORY_TABLE", "PromptTemplateHistory")
_TASKS_TABLE = os.environ.get("TASKS_TABLE", "Tasks")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreatePromptRequest(BaseModel):
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    created_by: str = ""


class UpdatePromptRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    updated_by: str = ""


@router.post("", status_code=201)
async def create_prompt(body: CreatePromptRequest, user: dict = Depends(verify_token)):
    """POST /prompts — 创建模板。"""
    missing = []
    if not body.name:
        missing.append({"field": "name", "message": "名称不能为空"})
    if not body.system_prompt:
        missing.append({"field": "system_prompt", "message": "系统提示词不能为空"})
    if not body.user_prompt:
        missing.append({"field": "user_prompt", "message": "用户提示词不能为空"})
    if missing:
        raise ValidationError("请求参数不完整", details=missing)

    now = _now_iso()
    item = {
        "template_id": str(uuid.uuid4()),
        "name": body.name,
        "description": body.description,
        "system_prompt": body.system_prompt,
        "user_prompt": body.user_prompt,
        "version": 1,
        "created_by": body.created_by,
        "created_at": now,
        "updated_at": now,
    }
    dynamodb.put_item(_TEMPLATES_TABLE, item)
    return {"data": item, "message": "模板创建成功"}


@router.get("")
async def list_prompts(user: dict = Depends(verify_token)):
    """GET /prompts — 列表。"""
    items = dynamodb.scan_all(_TEMPLATES_TABLE)
    result = [
        {
            "template_id": it["template_id"],
            "name": it.get("name", ""),
            "description": it.get("description", ""),
            "created_at": it.get("created_at", ""),
        }
        for it in items
    ]
    return {"data": result, "message": "查询成功"}


@router.get("/{template_id}")
async def get_prompt(template_id: str, user: dict = Depends(verify_token)):
    """GET /prompts/{id} — 详情。"""
    item = dynamodb.get_item(_TEMPLATES_TABLE, {"template_id": template_id})
    if not item:
        raise NotFoundError(f"模板 {template_id} 不存在")
    return {"data": item, "message": "查询成功"}


@router.put("/{template_id}")
async def update_prompt(template_id: str, body: UpdatePromptRequest, user: dict = Depends(verify_token)):
    """PUT /prompts/{id} — 更新。"""
    current = dynamodb.get_item(_TEMPLATES_TABLE, {"template_id": template_id})
    if not current:
        raise NotFoundError(f"模板 {template_id} 不存在")

    # 旧版本写入历史表
    history_item = {
        "template_id": template_id,
        "version": current["version"],
        "system_prompt": current.get("system_prompt", ""),
        "user_prompt": current.get("user_prompt", ""),
        "updated_by": body.updated_by,
        "updated_at": current.get("updated_at", ""),
    }
    dynamodb.put_item(_HISTORY_TABLE, history_item)

    now = _now_iso()
    new_version = int(current["version"]) + 1

    update_fields = {}
    if body.name is not None:
        update_fields["#n"] = body.name
    if body.description is not None:
        update_fields["#d"] = body.description
    if body.system_prompt is not None:
        update_fields["#sp"] = body.system_prompt
    if body.user_prompt is not None:
        update_fields["#up"] = body.user_prompt

    set_parts = ["#v = :ver", "#ua = :ua"]
    expr_values = {":ver": new_version, ":ua": now}
    expr_names = {"#v": "version", "#ua": "updated_at"}

    field_map = {"#n": "name", "#d": "description", "#sp": "system_prompt", "#up": "user_prompt"}
    for alias, value in update_fields.items():
        set_parts.append(f"{alias} = :{alias.strip('#')}")
        expr_values[f":{alias.strip('#')}"] = value
        expr_names[alias] = field_map[alias]

    updated = dynamodb.update_item(
        table_name=_TEMPLATES_TABLE,
        key={"template_id": template_id},
        update_expression="SET " + ", ".join(set_parts),
        expression_values=expr_values,
        expression_names=expr_names,
    )
    return {"data": updated, "message": "模板更新成功"}


@router.delete("/{template_id}")
async def delete_prompt(template_id: str, user: dict = Depends(verify_token)):
    """DELETE /prompts/{id} — 删除。"""
    current = dynamodb.get_item(_TEMPLATES_TABLE, {"template_id": template_id})
    if not current:
        raise NotFoundError(f"模板 {template_id} 不存在")

    from boto3.dynamodb.conditions import Attr
    tasks = dynamodb.scan_all(_TASKS_TABLE, filter_expression=Attr("template_id").eq(template_id))
    if tasks:
        task_refs = [{"task_id": t["task_id"], "name": t.get("name", "")} for t in tasks]
        raise ConflictError(f"模板正在被 {len(tasks)} 个任务引用，无法删除", details=task_refs)

    dynamodb.delete_item(_TEMPLATES_TABLE, {"template_id": template_id})
    return {"message": "模板删除成功"}
