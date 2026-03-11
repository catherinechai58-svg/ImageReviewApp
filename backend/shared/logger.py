"""任务日志写入工具，写入 TaskLogs DynamoDB 表。"""

import os
from datetime import datetime, timezone

from backend.shared.dynamodb import put_item


def write_task_log(
    task_id: str,
    operation_type: str,
    target: str,
    result: str,
    message: str,
) -> None:
    """写入一条任务日志到 TaskLogs 表。

    Args:
        task_id: 任务 ID
        operation_type: 操作类型（channel_fetch / image_download / model_invoke / status_update）
        target: 操作对象（频道 ID、图片名等）
        result: 操作结果（success / failed）
        message: 详细信息
    """
    table_name = os.environ["TASK_LOGS_TABLE"]
    timestamp = datetime.now(timezone.utc).isoformat()

    item = {
        "task_id": task_id,
        "timestamp": timestamp,
        "operation_type": operation_type,
        "target": target,
        "result": result,
        "message": message,
    }

    put_item(table_name, item)
