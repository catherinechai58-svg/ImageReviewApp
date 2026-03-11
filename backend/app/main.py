"""FastAPI 应用入口 — 注册路由、CORS 中间件、健康检查端点。"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.logging_config import setup_logging
from backend.app.models_config import get_available_models
from backend.app.response import register_exception_handlers
from backend.app.routers.auth_routes import router as auth_router
from backend.app.routers.prompt_routes import router as prompt_router
from backend.app.routers.settings_routes import router as settings_router
from backend.app.routers.task_routes import router as task_router
from backend.app.routers.user_routes import router as user_router
from backend.app.worker import task_worker

# 配置日志
setup_logging()

# 启动时打印关键环境变量
print(f"[STARTUP] AWS_REGION: {os.environ.get('AWS_REGION', 'NOT SET')}")
print(f"[STARTUP] AWS_REGION_NAME: {os.environ.get('AWS_REGION_NAME', 'NOT SET')}")
print(f"[STARTUP] USER_POOL_ID: {os.environ.get('USER_POOL_ID', 'NOT SET')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理 Worker 生命周期。"""
    yield
    task_worker.shutdown()


app = FastAPI(title="Image Review API", lifespan=lifespan)

# CORS 中间件 — 允许所有来源（与现有 API Gateway 一致）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册统一异常处理
register_exception_handlers(app)

# 注册子路由
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(prompt_router, prefix="/prompts", tags=["prompts"])
app.include_router(task_router, prefix="/tasks", tags=["tasks"])
app.include_router(user_router, prefix="/users", tags=["users"])
app.include_router(settings_router, prefix="/settings", tags=["settings"])


@app.get("/health")
async def health_check():
    """健康检查端点 — ALB 使用。"""
    return {"status": "ok"}


@app.get("/models")
async def list_models():
    """返回可选模型列表。"""
    return {"data": get_available_models(), "message": "查询成功"}
