"""提示词模板 CRUD 路由 — 支持个人/公开可见性。"""

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
    review_rules: str = ""
    visibility: str = "private"  # private | public


class UpdatePromptRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    review_rules: str | None = None
    visibility: str | None = None


@router.post("", status_code=201)
async def create_prompt(body: CreatePromptRequest, user: dict = Depends(verify_token)):
    """POST /prompts — 创建模板。"""
    from backend.app.system_prompt import SYSTEM_PROMPT

    missing = []
    if not body.name:
        missing.append({"field": "name", "message": "名称不能为空"})
    if not body.user_prompt:
        missing.append({"field": "user_prompt", "message": "用户提示词不能为空"})
    if not body.review_rules:
        missing.append({"field": "review_rules", "message": "审核判定规则不能为空"})
    if missing:
        raise ValidationError("请求参数不完整", details=missing)

    if "review_result" not in body.review_rules:
        raise ValidationError("审核判定规则必须包含 review_result 的判定逻辑",
                              details=[{"field": "review_rules", "message": "规则中必须包含 review_result"}])

    if body.visibility not in ("private", "public"):
        raise ValidationError("可见性只能为 private 或 public")

    now = _now_iso()
    username = user.get("username", "")
    item = {
        "template_id": str(uuid.uuid4()),
        "name": body.name,
        "description": body.description,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": body.user_prompt,
        "review_rules": body.review_rules,
        "visibility": body.visibility,
        "created_by": username,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    dynamodb.put_item(_TEMPLATES_TABLE, item)
    return {"data": item, "message": "模板创建成功"}


@router.get("")
async def list_prompts(user: dict = Depends(verify_token)):
    """GET /prompts — 列表（只返回自己的 + 公开的）。"""
    username = user.get("username", "")
    items = dynamodb.scan_all(_TEMPLATES_TABLE)
    # 过滤：自己创建的 或 公开的
    visible = [it for it in items
               if it.get("created_by", "") == username or it.get("visibility", "private") == "public"]
    result = [
        {
            "template_id": it["template_id"],
            "name": it.get("name", ""),
            "description": it.get("description", ""),
            "visibility": it.get("visibility", "private"),
            "created_by": it.get("created_by", ""),
            "created_at": it.get("created_at", ""),
        }
        for it in visible
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
    """PUT /prompts/{id} — 更新（仅作者可修改）。"""
    from backend.app.system_prompt import SYSTEM_PROMPT

    current = dynamodb.get_item(_TEMPLATES_TABLE, {"template_id": template_id})
    if not current:
        raise NotFoundError(f"模板 {template_id} 不存在")

    # 权限检查：只有作者能修改
    username = user.get("username", "")
    if current.get("created_by", "") and current["created_by"] != username:
        raise ValidationError("只有模板作者才能修改此模板")

    # review_rules 校验
    new_rules = body.review_rules if body.review_rules is not None else current.get("review_rules", "")
    if not new_rules:
        raise ValidationError("审核判定规则不能为空",
                              details=[{"field": "review_rules", "message": "审核判定规则不能为空"}])
    if "review_result" not in new_rules:
        raise ValidationError("审核判定规则必须包含 review_result 的判定逻辑",
                              details=[{"field": "review_rules", "message": "规则中必须包含 review_result"}])

    if body.visibility is not None and body.visibility not in ("private", "public"):
        raise ValidationError("可见性只能为 private 或 public")

    # 旧版本写入历史表
    history_item = {
        "template_id": template_id,
        "version": current["version"],
        "system_prompt": current.get("system_prompt", ""),
        "user_prompt": current.get("user_prompt", ""),
        "review_rules": current.get("review_rules", ""),
        "updated_by": username,
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
    update_fields["#sp"] = SYSTEM_PROMPT
    if body.user_prompt is not None:
        update_fields["#up"] = body.user_prompt
    if body.review_rules is not None:
        update_fields["#rr"] = body.review_rules
    if body.visibility is not None:
        update_fields["#vi"] = body.visibility

    set_parts = ["#v = :ver", "#ua = :ua"]
    expr_values = {":ver": new_version, ":ua": now}
    expr_names = {"#v": "version", "#ua": "updated_at"}

    field_map = {"#n": "name", "#d": "description", "#sp": "system_prompt",
                 "#up": "user_prompt", "#rr": "review_rules", "#vi": "visibility"}
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
    """DELETE /prompts/{id} — 删除（仅作者可删除）。"""
    current = dynamodb.get_item(_TEMPLATES_TABLE, {"template_id": template_id})
    if not current:
        raise NotFoundError(f"模板 {template_id} 不存在")

    username = user.get("username", "")
    if current.get("created_by", "") and current["created_by"] != username:
        raise ValidationError("只有模板作者才能删除此模板")

    from boto3.dynamodb.conditions import Attr
    tasks = dynamodb.scan_all(_TASKS_TABLE, filter_expression=Attr("template_id").eq(template_id))
    if tasks:
        task_refs = [{"task_id": t["task_id"], "name": t.get("name", "")} for t in tasks]
        raise ConflictError(f"模板正在被 {len(tasks)} 个任务引用，无法删除", details=task_refs)

    dynamodb.delete_item(_TEMPLATES_TABLE, {"template_id": template_id})
    return {"message": "模板删除成功"}
