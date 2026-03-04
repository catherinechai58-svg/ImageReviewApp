"""后台异步任务 Worker — 使用 ThreadPoolExecutor 管理工作流并发执行。"""

import os
import traceback
from concurrent.futures import Future, ThreadPoolExecutor

from backend.shared.logger import write_task_log


class TaskWorker:
    """后台任务执行器，管理工作流的异步执行。"""

    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running_tasks: dict[str, Future] = {}

    def submit_execute(self, task_id: str, payload: dict) -> None:
        """提交完整工作流（频道获取 → 图片下载 → 推理 → 结果收集）。"""
        from backend.app.workflow import run_workflow
        future = self.executor.submit(self._safe_run, run_workflow, task_id, payload)
        self.running_tasks[task_id] = future

    def submit_retry(self, task_id: str, payload: dict) -> None:
        """提交重做工作流（跳过频道获取和图片下载）。"""
        from backend.app.workflow import run_retry_workflow
        future = self.executor.submit(self._safe_run, run_retry_workflow, task_id, payload)
        self.running_tasks[task_id] = future

    def get_status(self, task_id: str) -> str:
        """查询后台任务运行状态。"""
        future = self.running_tasks.get(task_id)
        if future is None:
            return "unknown"
        if future.running():
            return "running"
        if future.done():
            return "completed" if future.exception() is None else "failed"
        return "pending"

    def shutdown(self) -> None:
        """关闭线程池，等待所有任务完成。"""
        self.executor.shutdown(wait=True)

    @staticmethod
    def _safe_run(func, task_id: str, payload: dict) -> None:
        """安全执行工作流，捕获未处理异常并更新状态为 failed。"""
        try:
            func(task_id, payload)
        except Exception:
            traceback.print_exc()
            try:
                from backend.shared.dynamodb import update_item
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                update_item(
                    table_name=os.environ.get("TASKS_TABLE", "Tasks"),
                    key={"task_id": task_id},
                    update_expression="SET #s = :status, updated_at = :now",
                    expression_values={":status": "failed", ":now": now},
                    expression_names={"#s": "status"},
                )
                write_task_log(task_id, "workflow", task_id, "failed", traceback.format_exc()[:500])
            except Exception:
                traceback.print_exc()


_max_workers = int(os.environ.get("CONCURRENCY", "3"))
task_worker = TaskWorker(max_workers=_max_workers)
