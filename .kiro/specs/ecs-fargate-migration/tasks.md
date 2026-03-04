# Implementation Plan: ECS Fargate Migration

## Overview

将现有 Step Functions + Lambda 后端架构迁移到 ECS Fargate 统一服务架构。所有 12 个 Lambda 函数合并为一个 FastAPI 服务，工作流编排从 Step Functions 改为后台异步任务（ThreadPoolExecutor）。CDK 基础设施移除 Lambda/Step Functions，新增 VPC/ECS/ALB。

## Tasks

- [x] 1. 创建 FastAPI 应用基础结构
  - [x] 1.1 创建 `backend/app/main.py` — FastAPI 应用入口，注册路由、CORS 中间件、健康检查端点 `/health`
    - 配置 CORS 允许所有来源（与现有 API Gateway 一致）
    - 注册 auth_router、prompt_router、task_router 子路由
    - 添加 startup/shutdown 事件管理 Worker 生命周期
    - _Requirements: 1.1, 1.3, 11.3_

  - [x] 1.2 创建 `backend/app/auth.py` — Cognito JWT 验证中间件
    - 从 Cognito JWKS 端点获取公钥并缓存
    - 使用 `python-jose` 验证 JWT Token 签名和过期时间
    - 提取 username、sub 注入请求上下文
    - 无效/过期 Token 返回 HTTP 401
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 1.3 创建 `backend/app/response.py` — FastAPI 统一响应和异常处理
    - 复用 `backend/shared/errors.py` 的异常类型
    - 创建 FastAPI exception handler，将 AppError 转换为与现有 Lambda 格式一致的 JSON 响应
    - 确保响应体结构（`{"data": ..., "message": ...}` 和 `{"error": {"code": ..., "message": ...}}`）与现有完全一致
    - _Requirements: 1.2, 1.4_

- [x] 2. 迁移 API Lambda handler 到 FastAPI 路由
  - [x] 2.1 创建 `backend/app/routers/auth_routes.py` — 认证路由
    - `POST /auth/login` — 无需 JWT 验证，复用 `auth_handler.py` 中的 `_login` 逻辑
    - `POST /auth/change-password` — 需要 JWT 验证，复用 `_change_password` 逻辑
    - 直接调用 `backend/shared/dynamodb.py` 和 boto3 Cognito 客户端
    - _Requirements: 1.1, 2.5_

  - [x] 2.2 创建 `backend/app/routers/prompt_routes.py` — 提示词模板 CRUD 路由
    - `POST /prompts`, `GET /prompts`, `GET /prompts/{id}`, `PUT /prompts/{id}`, `DELETE /prompts/{id}`
    - 所有路由需要 JWT 验证（`Depends(verify_token)`）
    - 复用 `prompt_handler.py` 中的业务逻辑（创建、列表、详情、更新、删除）
    - 复用 `backend/shared/dynamodb.py` 进行数据访问
    - _Requirements: 1.1, 1.2, 12.1, 12.2_

  - [x] 2.3 创建 `backend/app/routers/task_routes.py` — 任务管理路由
    - `POST /tasks`, `GET /tasks`, `GET /tasks/{id}` — CRUD 操作
    - `POST /tasks/{id}/execute` — 触发完整工作流，返回 HTTP 202，提交到 Worker
    - `POST /tasks/{id}/retry` — 触发重做工作流，返回 HTTP 202，提交到 Worker
    - `GET /tasks/{id}/logs` — 查询任务日志（复用 `log_handler.py` 逻辑）
    - `GET /tasks/{id}/results` — 分页查询结果（复用 `result_handler.py` 逻辑）
    - `GET /tasks/{id}/results/download` — 生成预签名下载 URL
    - execute/retry 中移除 Step Functions 调用，改为调用 `task_worker.submit_execute/submit_retry`
    - _Requirements: 1.1, 1.2, 3.1, 5.1, 8.2, 8.3, 12.1, 12.2_

- [x] 3. Checkpoint — 确保 FastAPI 应用结构完整
  - 确保所有路由文件创建完成，模块导入无误，ask the user if questions arise.

- [x] 4. 实现后台异步任务 Worker
  - [x] 4.1 创建 `backend/app/worker.py` — TaskWorker 类
    - 使用 `ThreadPoolExecutor(max_workers=3)` 管理并发工作流
    - `submit_execute(task_id, payload)` — 提交完整工作流
    - `submit_retry(task_id, payload)` — 提交重做工作流
    - `get_status(task_id)` — 查询后台任务状态
    - 全局单例 `task_worker` 实例
    - _Requirements: 3.1, 3.4, 5.1_

  - [x] 4.2 创建 `backend/app/workflow.py` — 工作流执行逻辑
    - `run_workflow(task_id, payload)` — 完整工作流：频道获取 → 图片下载 → 状态更新(recognizing) → 推理 → 结果收集 → 状态更新(completed/partial_completed/failed)
    - `run_retry_workflow(task_id, payload)` — 重做工作流：跳过频道获取和图片下载，直接推理
    - 复用 `channel_fetcher.py` 的 `_fetch_feed` 和 `_parse_feed` 函数
    - 复用 `image_downloader.py` 的 `_download_image` 函数
    - 复用 `backend/shared/s3_utils.py` 和 `backend/shared/logger.py`
    - 错误处理：未捕获异常时更新状态为 failed 并写入 TaskLogs
    - _Requirements: 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.2, 5.3_

  - [x] 4.3 在 `backend/app/workflow.py` 中实现批量推理逻辑
    - `run_batch_inference(task_id, images, payload)` — 构建 JSONL → 提交 Bedrock 批量任务 → 轮询等待 → 收集结果
    - `poll_batch_job(task_id, batch_job_arn, interval=60)` — 异步轮询，每次写入 TaskLogs
    - 复用 `recognizer_batch.py` 的 `_build_jsonl`、`_build_record`、`_detect_format` 函数
    - 复用 `result_collector.py` 的 `_process_batch_results`、`_parse_model_output` 函数
    - 复用 `batch_status_checker.py` 的状态归类逻辑
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 4.4 在 `backend/app/workflow.py` 中实现实时推理逻辑
    - `run_realtime_inference(task_id, images, payload)` — 使用 asyncio + Semaphore 并发调用 Bedrock invoke_model
    - 复用 `recognizer_realtime.py` 的 `_invoke_single`、`_build_request_body`、`_parse_response` 函数
    - 单张失败记录日志并继续处理其余图片
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 4.5 在 `backend/app/workflow.py` 中实现结果收集和 results.json 生成
    - 复用 `result_collector.py` 的 `_generate_results_json` 函数
    - 工作流完成后生成 results.json 上传到 S3
    - _Requirements: 8.1, 12.3_

- [x] 5. Checkpoint — 确保 Worker 和工作流逻辑完整
  - 确保所有工作流步骤串联正确，模块导入无误，ask the user if questions arise.

- [x] 6. 创建 Dockerfile 和依赖配置
  - [x] 6.1 创建 `backend/Dockerfile`
    - 基于 `python:3.12-slim`
    - 安装 `requirements.txt` 依赖
    - 复制 `backend/` 代码
    - `CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
    - _Requirements: 10.1, 10.2_

  - [x] 6.2 更新 `backend/requirements.txt` — 添加 FastAPI 依赖
    - 添加 `fastapi`, `uvicorn[standard]`, `python-jose[cryptography]`, `httpx`
    - 保留现有 `boto3` 依赖
    - 移除仅测试用的依赖（hypothesis, pytest, moto）
    - _Requirements: 10.1_

- [x] 7. 更新 CDK 基础设施
  - [x] 7.1 更新 `cdk/infra_stack.py` — 移除 Step Functions 占位状态机和 API Gateway
    - 移除 `sfn.StateMachine` 占位定义
    - 移除 `apigw.RestApi` 和 `CognitoUserPoolsAuthorizer` 定义
    - 移除相关的 `CfnOutput`（StateMachineArn, ApiGatewayId, ApiGatewayUrl）
    - 保留 DynamoDB 表、Cognito、S3、CloudFront 定义不变
    - _Requirements: 9.6_

  - [x] 7.2 更新 `cdk/app_stack.py` — 移除所有 Lambda 和 Step Functions，新增 VPC/ECS/ALB
    - 移除所有 12 个 Lambda 函数定义和 IAM 权限绑定
    - 移除所有 API Gateway 路由绑定
    - 移除 Step Functions 状态机定义
    - 新增 VPC（2 AZ，1 NAT Gateway，公有+私有子网）
    - 新增 ECS Cluster
    - 新增 `DockerImageAsset` 从 `backend/` 目录构建镜像
    - 新增 `ApplicationLoadBalancedFargateService`（CPU=512, Memory=1024MB, desired_count=1, container_port=8000）
    - 配置 ALB 健康检查指向 `/health`
    - 配置 ECS Task Role IAM 权限（DynamoDB 全表读写、S3 读写、Bedrock invoke/batch、Cognito、iam:PassRole）
    - 传入环境变量（所有表名、IMAGE_BUCKET、AWS_REGION_NAME、USER_POOL_ID、USER_POOL_CLIENT_ID、MODEL_ID、ROLE_ARN、CONCURRENCY）
    - 输出 ALB DNS 名称
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.3, 10.4, 11.1, 11.2, 11.4_

  - [x] 7.3 更新 `cdk/requirements.txt` — 调整 CDK 依赖
    - 确保包含 `aws-cdk-lib`（已包含 ecs、ec2、ecs_patterns、ecr_assets 模块）
    - _Requirements: 9.2_

- [x] 8. 更新前端 API 配置
  - [x] 8.1 更新前端 API base URL 配置，指向 ALB 地址
    - 更新 `frontend/src/config.ts` 或 `.env` 文件中的 `apiBaseUrl`，从 API Gateway URL 改为 ALB URL
    - _Requirements: 1.1_

- [x] 9. Final Checkpoint — 确保所有代码完整
  - 确保所有文件创建/修改完成，模块导入链正确，CDK 定义完整，ask the user if questions arise.

## Notes

- 所有任务均为代码实现任务，无测试任务
- `backend/shared/` 工具层（dynamodb.py、s3_utils.py、response.py、errors.py、logger.py）完全复用，不做修改
- 现有 `backend/lambdas/` 目录中的函数逻辑将被提取复用到 FastAPI 路由和 Worker 中，Lambda 文件本身保留不删除（CDK 不再引用即可）
- 每个任务引用了具体的需求编号，确保需求全覆盖
