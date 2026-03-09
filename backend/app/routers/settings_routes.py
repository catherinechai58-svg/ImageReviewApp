"""系统设置路由 — 管理员可配置并发参数和 YouTube API Key。"""

import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth import verify_token
from backend.shared import dynamodb
from backend.shared.errors import ValidationError, AuthenticationError

router = APIRouter()

_USERS_TABLE = os.environ.get("USERS_TABLE", "ImageReviewApp-Users")
_SETTINGS_TABLE = os.environ.get("SETTINGS_TABLE", "ImageReviewApp-Settings")
_SETTINGS_KEY = {"setting_key": "global"}

_INT_DEFAULTS = {
    "task_max_workers": 3,
    "realtime_concurrency": 5,
}

_STR_DEFAULTS = {
    "youtube_api_key": "",
}


def _require_admin(user: dict) -> None:
    username = user.get("username", "")
    record = dynamodb.get_item(_USERS_TABLE, {"user_id": username})
    if not record or record.get("role") != "admin":
        raise AuthenticationError("需要管理员权限")


def get_settings() -> dict:
    """读取系统设置，不存在则返回默认值。"""
    item = dynamodb.get_item(_SETTINGS_TABLE, _SETTINGS_KEY)
    if not item:
        return {**_INT_DEFAULTS, **_STR_DEFAULTS}
    result = {}
    for k, v in _INT_DEFAULTS.items():
        result[k] = int(item.get(k, v))
    for k, v in _STR_DEFAULTS.items():
        result[k] = str(item.get(k, v))
    return result


def get_setting(key: str):
    """读取单个设置值。"""
    settings = get_settings()
    return settings.get(key, _INT_DEFAULTS.get(key, _STR_DEFAULTS.get(key, "")))


class UpdateSettingsRequest(BaseModel):
    task_max_workers: int | None = None
    realtime_concurrency: int | None = None
    youtube_api_key: str | None = None


@router.get("")
async def read_settings(user: dict = Depends(verify_token)):
    """GET /settings — 读取系统设置。"""
    return {"data": get_settings(), "message": "查询成功"}


@router.put("")
async def update_settings(body: UpdateSettingsRequest, user: dict = Depends(verify_token)):
    """PUT /settings — 更新系统设置（仅管理员）。"""
    _require_admin(user)

    current = get_settings()
    if body.task_max_workers is not None:
        if not 1 <= body.task_max_workers <= 20:
            raise ValidationError("任务并发数须在 1~20 之间")
        current["task_max_workers"] = body.task_max_workers
    if body.realtime_concurrency is not None:
        if not 1 <= body.realtime_concurrency <= 50:
            raise ValidationError("推理并发数须在 1~50 之间")
        current["realtime_concurrency"] = body.realtime_concurrency
    if body.youtube_api_key is not None:
        current["youtube_api_key"] = body.youtube_api_key.strip()

    dynamodb.put_item(_SETTINGS_TABLE, {**_SETTINGS_KEY, **current})

    # 动态调整 worker 线程池
    from backend.app.worker import task_worker
    task_worker.update_max_workers(current["task_max_workers"])

    return {"data": current, "message": "设置已更新"}
