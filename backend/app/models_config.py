"""可选模型配置 — 通过环境变量 AVAILABLE_MODELS 自定义。

环境变量格式（JSON 数组）：
  AVAILABLE_MODELS='[{"id":"apac.amazon.nova-lite-v1:0","name":"Nova Lite v1"},...]'

未设置时使用内置默认列表。
"""

import json
import os

# 内置默认模型列表
_DEFAULT_MODELS = [
    {"id": "apac.amazon.nova-lite-v1:0", "name": "Nova Lite v1"},
    {"id": "global.amazon.nova-2-lite-v1:0", "name": "Nova Lite v2"},
]


def get_available_models() -> list[dict]:
    """返回可选模型列表。优先读取环境变量 AVAILABLE_MODELS。"""
    raw = os.environ.get("AVAILABLE_MODELS")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return _DEFAULT_MODELS


def get_default_model_id() -> str:
    """返回默认模型 ID。"""
    models = get_available_models()
    return models[0]["id"] if models else "apac.amazon.nova-lite-v1:0"


def is_valid_model(model_id: str) -> bool:
    """检查 model_id 是否在可选列表中。"""
    return any(m["id"] == model_id for m in get_available_models())
