"""任务和结果状态常量定义"""

# 任务状态
class TaskStatus:
    PENDING = "pending"              # 待执行
    QUEUED = "queued"                # 排队中
    DOWNLOADING = "downloading"      # 下载图片中
    RECOGNIZING = "recognizing"      # 推理中
    COMPLETED = "completed"          # 已完成
    FAILED = "failed"                # 失败
    PARTIAL_COMPLETED = "partial_completed"  # 部分完成

# 结果状态
class ResultStatus:
    SUCCESS = "success"              # 成功
    FAILED = "failed"                # 失败

# 允许执行的任务状态
EXECUTE_ALLOWED_STATUSES = {
    TaskStatus.PENDING,
    TaskStatus.FAILED,
    TaskStatus.PARTIAL_COMPLETED
}

# 允许重做的任务状态
RETRY_ALLOWED_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.PARTIAL_COMPLETED,
    TaskStatus.FAILED
}
