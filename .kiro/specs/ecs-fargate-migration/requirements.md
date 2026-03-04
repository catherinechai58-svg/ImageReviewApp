# Requirements Document

## Introduction

将现有 Step Functions + Lambda 后端架构完全迁移到 ECS Fargate 统一服务架构。迁移后，所有 12 个 Lambda 函数合并为一个 ECS Fargate 服务，API 层使用 FastAPI 框架，工作流编排从 Step Functions 改为 Fargate 服务内的后台异步任务（ThreadPoolExecutor）。前端无需修改，API 接口保持完全兼容。

## Glossary

- **Fargate_Service**: 运行在 AWS ECS Fargate 上的容器化后端服务，包含 FastAPI HTTP 服务器和后台异步任务 Worker
- **FastAPI_Server**: Fargate 容器内的 HTTP 服务器，提供 REST API 接口，替代原有 API Gateway + Lambda handler
- **Task_Worker**: Fargate 容器内的后台异步任务执行器，使用 ThreadPoolExecutor 管理工作流执行，替代原有 Step Functions 状态机
- **ALB**: Application Load Balancer，替代原有 API Gateway 作为流量入口
- **JWT_Middleware**: FastAPI 中间件，验证 Cognito JWT Token，替代原有 API Gateway Cognito Authorizer
- **Workflow**: 完整的任务执行流程，包括频道获取、图片下载、推理、结果收集、状态更新
- **Batch_Inference**: 使用 Bedrock 批量推理 API 处理图片的模式
- **Realtime_Inference**: 使用 Bedrock 实时推理 API 逐张处理图片的模式

## Requirements

### Requirement 1: FastAPI HTTP 服务

**User Story:** As a 前端开发者, I want 后端提供与现有 API Gateway 完全一致的 REST API 接口, so that 前端代码无需任何修改即可正常工作。

#### Acceptance Criteria

1. THE FastAPI_Server SHALL 提供与现有 API Gateway 完全一致的路由路径和 HTTP 方法（POST /auth/login, POST /auth/change-password, CRUD /prompts, CRUD /tasks, GET /tasks/{id}/logs, GET /tasks/{id}/results, GET /tasks/{id}/results/download）
2. WHEN 收到 API 请求时, THE FastAPI_Server SHALL 返回与现有 Lambda handler 格式一致的 JSON 响应体
3. THE FastAPI_Server SHALL 在 `/health` 路径提供健康检查端点，返回 HTTP 200 状态码
4. WHEN 请求参数不合法时, THE FastAPI_Server SHALL 返回包含错误描述的 JSON 响应和对应的 HTTP 错误状态码

### Requirement 2: Cognito JWT 认证

**User Story:** As a 系统管理员, I want JWT Token 验证从 API Gateway 迁移到应用层, so that 认证行为与迁移前完全一致。

#### Acceptance Criteria

1. WHEN 收到需要认证的 API 请求时, THE JWT_Middleware SHALL 从请求 Authorization header 中提取 Bearer Token 并验证其签名和过期时间
2. WHEN JWT Token 无效或过期时, THE JWT_Middleware SHALL 返回 HTTP 401 状态码和错误描述
3. WHEN JWT Token 验证通过时, THE JWT_Middleware SHALL 将用户身份信息（username、sub）注入到请求上下文中供后续处理使用
4. THE JWT_Middleware SHALL 从 Cognito JWKS 端点获取公钥用于 Token 签名验证
5. WHEN 请求 POST /auth/login 时, THE FastAPI_Server SHALL 跳过 JWT 验证，允许未认证访问

### Requirement 3: 工作流异步执行

**User Story:** As a 内容审核员, I want 任务执行工作流在后台异步运行, so that 提交任务后可以立即返回并继续其他操作。

#### Acceptance Criteria

1. WHEN 用户提交任务执行请求（POST /tasks/{id}/execute）时, THE FastAPI_Server SHALL 返回 HTTP 202 状态码并立即响应，工作流在后台异步执行
2. WHEN 后台工作流开始执行时, THE Task_Worker SHALL 按顺序执行：频道获取 → 图片下载 → 推理 → 结果收集 → 状态更新
3. WHILE 工作流正在执行时, THE Task_Worker SHALL 在每个步骤完成后将日志写入 TaskLogs 表
4. THE Task_Worker SHALL 限制同时执行的工作流数量不超过配置的最大并发数（默认 3）

### Requirement 4: 工作流状态管理

**User Story:** As a 内容审核员, I want 任务状态在工作流执行过程中实时更新, so that 我可以随时了解任务的执行进度。

#### Acceptance Criteria

1. WHEN 工作流开始执行时, THE Task_Worker SHALL 将任务状态更新为 `fetching`
2. WHEN 频道获取和图片下载完成后, THE Task_Worker SHALL 将任务状态更新为 `recognizing`
3. WHEN 工作流全部成功完成时, THE Task_Worker SHALL 将任务状态更新为 `completed` 并更新 success_count 和 failure_count
4. WHEN 工作流中部分图片处理失败时, THE Task_Worker SHALL 将任务状态更新为 `partial_completed` 并记录成功和失败计数
5. WHEN 工作流执行过程中发生未捕获异常时, THE Task_Worker SHALL 将任务状态更新为 `failed` 并将错误信息写入 TaskLogs 表

### Requirement 5: 重做工作流

**User Story:** As a 内容审核员, I want 对失败的图片重新执行推理, so that 不需要重新下载所有图片即可修复失败项。

#### Acceptance Criteria

1. WHEN 用户提交重做请求（POST /tasks/{id}/retry）时, THE FastAPI_Server SHALL 返回 HTTP 202 状态码并在后台启动重做工作流
2. WHEN 重做工作流执行时, THE Task_Worker SHALL 跳过频道获取和图片下载步骤，直接从推理阶段开始处理失败的图片
3. WHEN 重做工作流完成时, THE Task_Worker SHALL 按照与完整工作流相同的规则更新任务状态和计数

### Requirement 6: 批量推理模式

**User Story:** As a 内容审核员, I want 使用 Bedrock 批量推理处理大量图片, so that 可以高效地批量分析缩略图。

#### Acceptance Criteria

1. WHEN 任务的 run_mode 为 "batch" 时, THE Task_Worker SHALL 构建 JSONL 格式的推理请求并上传到 S3
2. WHEN JSONL 上传完成后, THE Task_Worker SHALL 调用 Bedrock create_model_invocation_job API 创建批量推理任务
3. WHILE 批量推理任务正在运行时, THE Task_Worker SHALL 以固定间隔（默认 60 秒）轮询任务状态并将轮询结果写入 TaskLogs
4. WHEN 批量推理任务完成时, THE Task_Worker SHALL 从 S3 读取输出 JSONL 文件并解析推理结果写入 TaskResults 表
5. IF 批量推理任务失败, THEN THE Task_Worker SHALL 将任务状态标记为 failed 并记录错误信息

### Requirement 7: 实时推理模式

**User Story:** As a 内容审核员, I want 使用 Bedrock 实时推理逐张处理图片, so that 可以快速获得少量图片的分析结果。

#### Acceptance Criteria

1. WHEN 任务的 run_mode 为 "realtime" 时, THE Task_Worker SHALL 使用 Bedrock invoke_model API 逐张处理图片
2. WHILE 执行实时推理时, THE Task_Worker SHALL 使用并发控制（Semaphore）限制同时调用 Bedrock API 的请求数
3. WHEN 单张图片推理完成时, THE Task_Worker SHALL 将结果写入 TaskResults 表
4. IF 单张图片推理失败, THEN THE Task_Worker SHALL 记录错误日志并继续处理其余图片

### Requirement 8: 结果收集与导出

**User Story:** As a 内容审核员, I want 查看和下载推理结果, so that 可以分析缩略图的儿童内容检测结果。

#### Acceptance Criteria

1. WHEN 工作流的推理阶段完成后, THE Task_Worker SHALL 将所有结果汇总并生成 results.json 文件上传到 S3
2. WHEN 用户请求 GET /tasks/{id}/results 时, THE FastAPI_Server SHALL 从 TaskResults 表查询并返回该任务的所有推理结果
3. WHEN 用户请求 GET /tasks/{id}/results/download 时, THE FastAPI_Server SHALL 返回 S3 上 results.json 文件的预签名下载 URL

### Requirement 9: ECS Fargate 基础设施

**User Story:** As a 运维工程师, I want 使用 CDK 定义 ECS Fargate 基础设施, so that 可以通过 IaC 方式管理和部署后端服务。

#### Acceptance Criteria

1. THE CDK_Stack SHALL 创建包含公有子网和私有子网的 VPC，私有子网通过 NAT Gateway 访问外部服务
2. THE CDK_Stack SHALL 创建 ECS Cluster 和 Fargate Task Definition，配置 CPU（512）和内存（1024 MB）
3. THE CDK_Stack SHALL 创建 Application Load Balancer，将流量转发到 Fargate 服务的 8000 端口
4. THE CDK_Stack SHALL 为 ECS Task Role 配置与现有 Lambda 角色相同的 IAM 权限（DynamoDB、S3、Bedrock、Cognito）
5. THE CDK_Stack SHALL 配置 ALB 健康检查指向 `/health` 端点
6. THE CDK_Stack SHALL 移除所有 Lambda 函数和 Step Functions 状态机的 CDK 定义

### Requirement 10: 容器化与部署

**User Story:** As a 运维工程师, I want 后端服务容器化并通过 CDK 自动构建部署, so that 部署流程简单可靠。

#### Acceptance Criteria

1. THE Fargate_Service SHALL 使用 Dockerfile 定义容器镜像，基于 Python 3.12-slim 基础镜像
2. THE Fargate_Service SHALL 通过 uvicorn 启动 FastAPI 应用，监听 8000 端口
3. THE CDK_Stack SHALL 使用 DockerImageAsset 从本地 Dockerfile 自动构建并推送容器镜像
4. WHEN Fargate 容器异常退出时, THE ECS_Service SHALL 自动重启容器以恢复服务

### Requirement 11: 安全配置

**User Story:** As a 安全工程师, I want 服务运行在安全的网络环境中, so that 系统免受未授权访问。

#### Acceptance Criteria

1. THE Fargate_Service SHALL 运行在 VPC 私有子网中，不直接暴露到公网
2. THE ALB SHALL 仅开放 80 和 443 端口接受入站流量
3. THE FastAPI_Server SHALL 配置 CORS 中间件，仅允许前端域名的跨域请求
4. THE CDK_Stack SHALL 通过 ECS Task Definition 的环境变量或 Secrets Manager 注入敏感配置

### Requirement 12: 数据兼容性

**User Story:** As a 开发者, I want 迁移后数据层完全兼容, so that 现有数据无需迁移即可继续使用。

#### Acceptance Criteria

1. THE Fargate_Service SHALL 继续使用现有 DynamoDB 表结构（Tasks、Users、PromptTemplates、PromptTemplateHistory、TaskResults、TaskLogs），不做任何表结构变更
2. THE Fargate_Service SHALL 复用现有 backend/shared/ 工具层（dynamodb.py、s3_utils.py、response.py、errors.py）的数据访问逻辑
3. WHEN 任务执行完成后, THE Task_Worker SHALL 将结果写入 TaskResults 表，数据格式与现有 Lambda 写入的格式完全一致
