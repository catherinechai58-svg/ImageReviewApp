# 实施计划：图片批量识别与审核平台

## 概述

按照依赖关系从底层基础设施到上层应用逐步构建。先搭建 CDK 基础设施和共享工具层，再实现各 Lambda 函数，然后构建 Step Functions 编排，最后实现前端和集成测试。

## 任务

- [x] 1. 搭建项目结构和 CDK 基础设施
  - [x] 1.1 创建项目目录结构和依赖配置
    - 创建 `cdk/`、`backend/lambdas/`、`backend/shared/`、`frontend/` 目录
    - 创建 `cdk/requirements.txt`（aws-cdk-lib、constructs）
    - 创建 `backend/requirements.txt`（boto3、hypothesis、pytest、moto）
    - 创建 `cdk/app.py` CDK 入口文件
    - _需求: 12.1_

  - [x] 1.2 实现 InfraStack — DynamoDB 表定义
    - 在 `cdk/infra_stack.py` 中定义 6 张 DynamoDB 表（Users、PromptTemplates、PromptTemplateHistory、Tasks、TaskResults、TaskLogs）
    - 配置各表的主键、排序键和 GSI（NameIndex、StatusIndex、TaskStatusIndex、TaskReviewIndex）
    - 导出表名和 ARN 供 AppStack 引用
    - _需求: 2.1, 3.1, 4.1, 6.4, 8.1, 9.1_

  - [x] 1.3 实现 InfraStack — Cognito、API Gateway、S3、Step Functions、CloudFront
    - 定义 Cognito User Pool 和 App Client
    - 定义 API Gateway REST API，配置 Cognito Authorizer
    - 引用现有 S3 桶 `nova-test-image`
    - 定义 Step Functions 状态机占位（后续 AppStack 中填充定义）
    - 定义 CloudFront Distribution 指向前端 S3 桶
    - 导出所有资源 ARN
    - _需求: 1.1, 11.1, 12.1, 12.2_

  - [x] 1.4 实现 AppStack — Lambda 函数定义和权限绑定
    - 定义 12 个 Lambda 函数（5 个 API handler + 7 个 Step Functions handler）
    - 配置 Lambda 运行时为 Python 3.12，设置环境变量（表名、桶名、区域等）
    - 绑定 API Gateway 路由到对应 Lambda
    - 配置 Lambda IAM 权限（DynamoDB、S3、Bedrock、Step Functions）
    - 定义 Step Functions 状态机完整流程
    - _需求: 7.1, 7.2, 12.1_

- [x] 2. 实现共享工具层
  - [x] 2.1 实现统一错误处理和响应格式
    - 在 `backend/shared/response.py` 中实现统一响应构建函数（success_response、error_response）
    - 在 `backend/shared/errors.py` 中定义错误类型（ValidationError、NotFoundError、ConflictError）
    - 实现 Lambda handler 错误处理装饰器，捕获异常并返回对应 HTTP 状态码
    - 500 错误不暴露内部细节（堆栈跟踪、文件路径、表名）
    - _需求: 12.3, 12.4_

  - [ ]* 2.2 编写属性测试 — API 参数验证和内部错误信息不泄露
    - **Property 26: API 参数验证** — 不合法参数返回 400 且包含具体错误描述
    - **Property 27: 内部错误信息不泄露** — 500 错误响应不包含堆栈跟踪、文件路径、表名
    - **验证: 需求 12.3, 12.4**

  - [x] 2.3 实现 DynamoDB 工具函数
    - 在 `backend/shared/dynamodb.py` 中封装 DynamoDB CRUD 操作（put_item、get_item、query、update_item、delete_item）
    - 实现指数退避重试逻辑（最多 3 次，初始 0.5s）
    - 实现分页查询辅助函数
    - _需求: 9.1_

  - [x] 2.4 实现 S3 工具函数
    - 在 `backend/shared/s3_utils.py` 中封装 S3 操作（upload_file、download_file、generate_presigned_url、list_objects）
    - 实现 `build_s3_path(task_id, filename)` 确保路径格式为 `tasks/{task_id}/input/{filename}`
    - _需求: 11.1, 11.2, 11.3_

  - [ ]* 2.5 编写属性测试 — S3 路径格式不变量
    - **Property 14: S3 路径格式不变量** — 验证图片路径、JSONL 路径、结果文件路径格式正确
    - **验证: 需求 5.4, 11.1, 11.2**

  - [x] 2.6 实现日志写入工具
    - 在 `backend/shared/logger.py` 中实现 `write_task_log(task_id, operation_type, target, result, message)` 函数
    - 写入 TaskLogs 表，timestamp 使用 ISO 8601 格式
    - _需求: 8.1, 8.3_

- [x] 3. 检查点 — 确保基础设施和共享层代码无误
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. 实现认证模块
  - [x] 4.1 实现 auth_handler Lambda
    - 在 `backend/lambdas/auth_handler.py` 中实现登录和修改密码功能
    - 登录：调用 Cognito `admin_initiate_auth` 验证凭据，返回 JWT token
    - 修改密码：调用 Cognito `change_password` API
    - 认证失败返回通用错误信息，不透露具体失败原因（不区分用户名不存在和密码错误）
    - _需求: 1.1, 1.2, 1.3_

  - [ ]* 4.2 编写属性测试 — 认证相关
    - **Property 17: 认证令牌校验** — 受保护 API 不携带有效 token 返回 401
    - **Property 18: 认证错误信息不泄露** — 无效凭据返回的错误信息不包含具体失败原因
    - **验证: 需求 1.2, 1.4, 12.2**

- [x] 5. 实现提示词模板管理模块
  - [x] 5.1 实现 prompt_handler Lambda
    - 在 `backend/lambdas/prompt_handler.py` 中实现提示词模板 CRUD
    - 创建：生成 UUID，保存 name、description、system_prompt、user_prompt，version 初始为 1
    - 列表：查询所有模板，返回 name、description、created_at
    - 详情：按 template_id 查询
    - 更新：更新内容，version 递增，将旧版本写入 PromptTemplateHistory 表
    - 删除：检查是否被 Task 引用（查询 Tasks 表 template_id），未引用则删除，被引用则返回 409
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 5.2 编写属性测试 — 提示词模板
    - **Property 1: 提示词模板创建 round-trip** — 创建后查询返回相同内容
    - **Property 2: 提示词模板列表完整性** — 列表数量等于已创建数量
    - **Property 3: 提示词模板编辑保留历史** — 编辑后历史表存在旧版本
    - **Property 4: 未引用模板可删除** — 删除成功后查询返回 not found
    - **Property 5: 被引用模板删除保护** — 被引用时拒绝删除
    - **验证: 需求 2.1, 2.2, 2.3, 2.4, 2.5**

- [x] 6. 实现任务管理模块
  - [x] 6.1 实现 task_handler Lambda — 任务 CRUD
    - 在 `backend/lambdas/task_handler.py` 中实现任务创建、列表、详情
    - 创建：生成 UUID，保存配置，状态设为 `pending`，支持频道 URL 自动解析为频道 ID
    - 列表：查询所有任务，返回 name、status、created_at、updated_at
    - 详情：返回完整配置和进度统计（total_images、success_count、failure_count）
    - 运行模式验证：仅接受 `batch` 或 `realtime`
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.4_

  - [ ]* 6.2 编写属性测试 — 任务管理
    - **Property 6: 任务创建 round-trip** — 创建后查询返回相同配置，状态为 pending
    - **Property 7: 频道 URL 解析** — 有效 URL 正确解析出频道 ID
    - **Property 8: 运行模式验证** — 非法模式返回参数错误
    - **Property 9: 任务列表字段完整性** — 每条记录包含必要字段
    - **Property 11: 任务详情包含进度统计** — success_count + failure_count <= total_images
    - **验证: 需求 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.4**

  - [x] 6.3 实现 task_handler — 执行触发和重做
    - 执行：调用 Step Functions `start_execution`，传入任务配置，立即返回 202
    - 重做：查询失败结果，启动 Step Functions 仅执行识别阶段
    - 更新任务状态和 sfn_execution_arn
    - _需求: 7.1, 10.1, 10.4_

  - [x] 6.4 实现 log_handler Lambda
    - 在 `backend/lambdas/log_handler.py` 中实现任务日志查询
    - 按 task_id 查询 TaskLogs 表，按 timestamp 排序返回
    - _需求: 8.2_

  - [ ]* 6.5 编写属性测试 — 日志和状态
    - **Property 10: 状态变更更新时间戳** — 状态变更后 updated_at 晚于变更前
    - **Property 19: 日志完整性与排序** — 日志包含必要字段且按时间排序
    - **验证: 需求 4.3, 8.1, 8.2, 8.3**

- [x] 7. 检查点 — 确保 API 层所有 Lambda 函数正常工作
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 8. 实现 Step Functions 任务编排 — 频道获取和图片下载
  - [x] 8.1 实现 channel_fetcher Lambda
    - 在 `backend/lambdas/channel_fetcher.py` 中实现 YouTube RSS Feed 解析
    - 遍历频道 ID 列表，获取每个频道的视频列表
    - 提取 thumbnail_url、video_id、channel_id、channel_name
    - 单个频道失败记录错误日志，继续处理其余频道
    - 全部失败则抛出异常，由 Step Functions 捕获
    - 实现重试逻辑（3 次，指数退避，初始 1s）
    - _需求: 5.1, 5.2, 5.3_

  - [ ]* 8.2 编写属性测试 — 频道获取
    - **Property 12: RSS Feed 解析完整性** — 解析后每条记录包含必要字段
    - **Property 13: 频道获取容错** — 部分频道失败不影响成功频道
    - **验证: 需求 5.2, 5.3**

  - [x] 8.3 实现 image_downloader Lambda
    - 在 `backend/lambdas/image_downloader.py` 中实现缩略图下载和 S3 上传
    - 从 YouTube 下载缩略图，上传到 `tasks/{task_id}/input/{video_id}.jpg`
    - 单张失败跳过并记录日志，继续处理
    - 实现重试逻辑（2 次，固定 2s 间隔）
    - 返回成功/失败统计
    - _需求: 5.4, 11.1_

  - [x] 8.4 实现 status_updater Lambda
    - 在 `backend/lambdas/status_updater.py` 中实现任务状态更新
    - 更新 Tasks 表的 status 和 updated_at
    - 更新进度统计（total_images、success_count、failure_count）
    - _需求: 4.2, 4.3_

- [x] 9. 实现 Step Functions 任务编排 — AI 识别
  - [x] 9.1 实现 recognizer_batch Lambda
    - 在 `backend/lambdas/recognizer_batch.py` 中实现批量推理
    - 构建 JSONL 格式请求：每条记录包含 recordId、S3 图片 URI、system_prompt（含 cachePoint 标记）、user_prompt
    - batch_input.jsonl 保存到 `tasks/{task_id}/input/` 目录
    - 调用 Bedrock `create_model_invocation_job` 提交批量任务
    - 返回 batch job ARN
    - _需求: 6.1, 6.3_

  - [ ]* 9.2 编写属性测试 — 批量推理 JSONL 构建
    - **Property 15: 批量推理 JSONL 构建正确性** — 验证 JSONL 格式、S3 URI、system/user prompt、cachePoint 标记
    - **Property 29: Prompt Cache 标记正确性** — system 消息包含 cachePoint 标记
    - **验证: 需求 6.1, 6.3**

  - [x] 9.3 实现 recognizer_realtime Lambda
    - 在 `backend/lambdas/recognizer_realtime.py` 中实现实时推理
    - 使用 asyncio + Semaphore 控制并发数
    - 调用 Bedrock `invoke_model` API，传入 system_prompt（含 cachePoint）和 user_prompt
    - 单张失败标记为 failed 并记录 error_message
    - 实现重试逻辑（3 次，指数退避，初始 2s）
    - _需求: 6.2, 6.3, 6.5, 7.4_

  - [ ]* 9.4 编写属性测试 — 实时推理并发控制
    - **Property 28: 实时推理并发控制** — 同时执行的推理调用数不超过配置的并发数
    - **验证: 需求 7.4**

  - [x] 9.5 实现 batch_status_checker Lambda
    - 在 `backend/lambdas/batch_status_checker.py` 中实现批量任务状态轮询
    - 调用 Bedrock `get_model_invocation_job` 查询状态
    - 返回任务状态（InProgress / Completed / Failed）
    - _需求: 6.1_

  - [x] 9.6 实现 result_collector Lambda
    - 在 `backend/lambdas/result_collector.py` 中实现结果收集
    - 解析批量推理输出 JSONL 或实时推理返回结果
    - 从 result_json 中提取 review_result（pass/fail）
    - 写入 TaskResults 表（task_id、image_name、video_id、channel_id、channel_name、s3_key、status、result_json、review_result）
    - 生成 results.json 保存到 `tasks/{task_id}/output/`
    - _需求: 6.4, 6.5, 9.4_

  - [ ]* 9.7 编写属性测试 — 识别结果存储
    - **Property 16: 识别结果存储完整性** — 保存后查询返回相同数据，成功记录含 result_json 和 review_result，失败记录含 error_message
    - **验证: 需求 6.4, 6.5, 9.3**

- [x] 10. 实现结果查询模块
  - [x] 10.1 实现 result_handler Lambda
    - 在 `backend/lambdas/result_handler.py` 中实现结果查询
    - 分页查询：支持 page_size 和 last_evaluated_key 参数
    - 过滤查询：支持按 review_result、status 过滤，支持 result_json 中自定义字段过滤
    - 下载链接：生成 S3 预签名 URL 返回
    - _需求: 9.1, 9.2, 9.3, 11.3_

  - [ ]* 10.2 编写属性测试 — 结果查询
    - **Property 20: 结果分页正确性** — 分页遍历后总数等于实际结果数
    - **Property 21: 结果过滤准确性** — 返回结果均满足过滤条件
    - **Property 22: 结果 JSON 文件与 DynamoDB 一致性** — S3 文件内容与 DynamoDB 记录一致
    - **验证: 需求 9.1, 9.2, 9.4**

  - [ ]* 10.3 编写属性测试 — 重做机制
    - **Property 23: 重做保持成功结果不变量** — 重做后成功记录内容和时间戳不变
    - **Property 24: 重做后进度统计一致性** — success_count + failure_count == total_images
    - **Property 25: 可重复重做** — 仍有失败时再次重做不返回错误
    - **验证: 需求 10.1, 10.2, 10.3, 10.4**

- [x] 11. 检查点 — 确保后端所有模块正常工作
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 12. 实现前端 React 应用
  - [x] 12.1 初始化前端项目和基础框架
    - 使用 Vite 创建 React + TypeScript 项目
    - 安装依赖：react-router-dom、axios、@aws-amplify/auth（Cognito 集成）
    - 配置 API 基础 URL 和 Cognito 参数
    - 实现登录页面和认证状态管理（token 存储、自动刷新、过期跳转）
    - 实现路由守卫（未登录重定向到登录页）
    - _需求: 1.1, 1.4, 1.5_

  - [x] 12.2 实现提示词模板管理页面
    - 模板列表页：展示所有模板，支持创建、编辑、删除操作
    - 模板编辑表单：name、description、system_prompt、user_prompt 字段
    - 删除确认对话框，被引用时展示关联任务信息
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 12.3 实现任务管理页面
    - 任务列表页：展示所有任务的名称、状态、创建时间，状态标签颜色区分
    - 任务创建表单：名称、描述、频道 ID/URL 输入（支持多个）、模板选择、运行模式选择
    - 任务详情页：展示配置信息、进度统计、执行/重做按钮、日志面板
    - _需求: 3.1, 3.2, 3.3, 3.4, 4.1, 4.4, 7.1, 8.2, 10.1, 10.4_

  - [x] 12.4 实现结果查询页面
    - 结果列表：分页展示识别结果，包含图片缩略图预览、识别结果、审核结论
    - 过滤面板：按 review_result（pass/fail）、status（success/failed）过滤
    - 结果下载按钮：调用下载链接 API
    - _需求: 9.1, 9.2, 9.3, 11.3_

- [x] 13. 集成和联调
  - [x] 13.1 配置 Step Functions 状态机完整流程
    - 在 CDK 中定义完整的 Step Functions 状态机
    - 实现正常流程：FetchChannels → DownloadImages → ChooseMode → (Batch/Realtime) → CollectResults → UpdateStatus
    - 实现重做流程：跳过频道获取和下载，直接进入识别阶段
    - 配置错误处理和重试策略
    - 配置批量模式的轮询等待（WaitBatchComplete 循环）
    - _需求: 7.1, 7.2, 7.3, 10.1_

  - [x] 13.2 前后端联调和 CORS 配置
    - 在 API Gateway 上配置 CORS（允许 CloudFront 域名）
    - 验证前端所有 API 调用正常工作
    - 配置 CloudFront 前端部署
    - _需求: 12.1_

- [x] 14. 最终检查点 — 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保可追溯性
- 检查点任务用于阶段性验证，确保增量开发的正确性
- 属性测试验证设计文档中定义的 29 个正确性属性
- 单元测试和属性测试互补：单元测试捕获具体 bug，属性测试验证通用正确性
