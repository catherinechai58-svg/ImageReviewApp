"""后台异步任务 Worker — 使用 ThreadPoolExecutor 管理工作流并发执行。"""

import os
import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone

from backend.shared.logger import write_task_log


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_task_status(task_id: str, status: str) -> None:
    from backend.shared.dynamodb import update_item
    update_item(
        table_name=os.environ.get("TASKS_TABLE", "Tasks"),
        key={"task_id": task_id},
        update_expression="SET #s = :status, updated_at = :now",
        expression_values={":status": status, ":now": _now_iso()},
        expression_names={"#s": "status"},
    )


class TaskWorker:
    """后台任务执行器，管理工作流的异步执行。"""

    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running_tasks: dict[str, Future] = {}
        self._max_workers = max_workers
        self._lock = threading.Lock()

    def update_max_workers(self, max_workers: int) -> None:
        """动态调整线程池大小。"""
        self._max_workers = max_workers
        self.executor._max_workers = max_workers

    def _active_count(self) -> int:
        """当前正在运行（非排队）的任务数。"""
        return sum(1 for f in self.running_tasks.values() if f.running())

    def is_at_capacity(self) -> bool:
        """线程池是否已满。"""
        return self._active_count() >= self._max_workers

    def submit_execute(self, task_id: str, payload: dict) -> None:
        """提交完整工作流。"""
        from backend.app.workflow import run_workflow
        initial_status = "fetching"
        future = self.executor.submit(self._safe_run, run_workflow, task_id, payload, initial_status)
        self.running_tasks[task_id] = future

    def submit_retry(self, task_id: str, payload: dict) -> None:
        """提交重做工作流。"""
        old_future = self.running_tasks.get(task_id)
        if old_future and not old_future.done():
            write_task_log(task_id, "retry_submit", "worker", "info", "取消旧任务")
            old_future.cancel()

        write_task_log(task_id, "retry_submit", "worker", "info",
                      f"提交重做任务到线程池，图片数: {len(payload.get('failed_images', []))}")

        from backend.app.workflow import run_retry_workflow
        initial_status = "recognizing"
        future = self.executor.submit(self._safe_run, run_retry_workflow, task_id, payload, initial_status)
        self.running_tasks[task_id] = future

        write_task_log(task_id, "retry_submit", "worker", "success", "重做任务已加入执行队列")

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
    def _safe_run(func, task_id: str, payload: dict, initial_status: str) -> None:
        """线程开始执行时更新状态，然后运行工作流。"""
        print(f"[Worker] _safe_run started for task {task_id}, func: {func.__name__}")
        try:
            # 线程真正开始执行，更新状态从 queued → 实际运行状态
            _update_task_status(task_id, initial_status)
            write_task_log(task_id, "worker", "thread", "success", f"开始执行，状态更新为 {initial_status}")
            func(task_id, payload)
            print(f"[Worker] _safe_run completed successfully for task {task_id}")
        except Exception as e:
            print(f"[Worker] _safe_run failed for task {task_id}: {e}")
            traceback.print_exc()
            try:
                _update_task_status(task_id, "failed")
                write_task_log(task_id, "workflow", task_id, "failed", traceback.format_exc()[:500])
            except Exception:
                traceback.print_exc()


def _get_initial_max_workers() -> int:
    try:
        from backend.app.routers.settings_routes import get_setting
        return get_setting("task_max_workers")
    except Exception:
        return int(os.environ.get("TASK_MAX_WORKERS", "3"))


task_worker = TaskWorker(max_workers=_get_initial_max_workers())
