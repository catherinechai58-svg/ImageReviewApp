# 需求文档

## 简介

将现有的 YouTube 缩略图儿童内容检测脚本重构为一个完整的图片批量识别与审核平台。平台包含前端 Web 界面和后端 REST API，支持用户管理、提示词维护、任务管理与执行、结果查询与审核等功能。后端基于 AWS 服务（Bedrock Nova Lite、S3、DynamoDB），采用异步并发架构处理图片识别任务。

## 术语表

- **Platform**: 图片批量识别审核平台，包含前端和后端的完整系统
- **User**: 使用平台的操作人员，需登录后使用
- **Prompt_Template**: 提示词模板，包含系统提示词（定义模型角色）和用户提示词（定义分析指令），推理时启用 Prompt Caching
- **Task**: 一次图片识别任务，包含名称、描述、频道信息、提示词、运行模式等配置
- **Task_Executor**: 后端异步任务执行引擎，负责调度和执行识别任务
- **Channel_Fetcher**: 频道数据获取模块，通过 YouTube 频道 ID 或 URL 获取视频封面图列表
- **Image_Downloader**: 图片下载模块，负责从 YouTube 下载缩略图并上传到 S3
- **Nova_Recognizer**: AI 识别模块，调用 Amazon Bedrock Nova Lite 模型对图片进行分析
- **Result_Store**: 结果存储模块，将任务和识别结果保存到 DynamoDB 和 S3
- **API_Gateway**: 后端统一 REST API 入口，接收和路由所有前端请求
- **Batch_Mode**: 批量运行模式，使用 Bedrock 批量推理 API 处理大量图片
- **Realtime_Mode**: 实时运行模式，使用 Bedrock 实时推理 API 逐张处理图片

## 需求

### 需求 1：用户认证

**用户故事：** 作为操作人员，我希望通过登录认证访问平台，以确保系统安全和操作可追溯。

#### 验收标准

1. WHEN User 提供有效的用户名和密码, THE Platform SHALL 验证凭据并返回认证令牌
2. WHEN User 提供无效的用户名或密码, THE Platform SHALL 返回认证失败的错误信息，且不透露具体失败原因
3. WHEN User 请求修改密码并提供正确的旧密码和符合规则的新密码, THE Platform SHALL 更新密码并返回成功状态
4. WHEN User 访问受保护的 API 且未携带有效认证令牌, THE Platform SHALL 返回 401 未授权状态码
5. WHEN 认证令牌过期, THE Platform SHALL 返回 401 状态码并要求 User 重新登录

### 需求 2：提示词模板管理

**用户故事：** 作为操作人员，我希望维护提示词模板，以便灵活定义不同的图片审核规则和分析指令。

#### 验收标准

1. WHEN User 创建 Prompt_Template 并提供名称和内容, THE Platform SHALL 保存模板到 DynamoDB 并返回模板 ID
2. WHEN User 查询 Prompt_Template 列表, THE Platform SHALL 返回所有可用模板的名称、描述和创建时间
3. WHEN User 编辑已有的 Prompt_Template, THE Platform SHALL 更新模板内容并保留修改历史
4. WHEN User 删除一个未被任何 Task 引用的 Prompt_Template, THE Platform SHALL 删除该模板并返回成功状态
5. IF User 尝试删除一个正在被 Task 引用的 Prompt_Template, THEN THE Platform SHALL 拒绝删除并返回关联任务信息

### 需求 3：任务创建与配置

**用户故事：** 作为操作人员，我希望创建和配置识别任务，以便指定要分析的 YouTube 频道和分析参数。

#### 验收标准

1. WHEN User 提交任务创建请求（包含名称、描述、频道 ID 或频道 URL、Prompt_Template 选择、运行模式选择）, THE Platform SHALL 创建 Task 记录并保存到 DynamoDB，状态设为"待执行"
2. THE Platform SHALL 支持在任务中配置一个或多个 YouTube 频道 ID
3. THE Platform SHALL 支持在任务中通过 YouTube 频道 URL 自动解析出频道 ID
4. WHEN User 选择运行模式, THE Platform SHALL 接受 Batch_Mode 或 Realtime_Mode 两种模式之一
5. THE Platform SHALL 为每个 Task 生成唯一的任务 ID，用于组织 S3 存储路径和 DynamoDB 记录

### 需求 4：任务列表与状态查看

**用户故事：** 作为操作人员，我希望查看所有任务的列表和运行状态，以便掌握整体任务进度。

#### 验收标准

1. WHEN User 请求任务列表, THE Platform SHALL 返回所有 Task 的名称、状态、创建时间和最后更新时间
2. THE Platform SHALL 为 Task 维护以下状态：待执行、获取封面中、下载图片中、识别中、已完成、失败、部分完成
3. WHEN Task 状态发生变化, THE Task_Executor SHALL 更新 DynamoDB 中的任务状态和时间戳
4. WHEN User 查看单个 Task 详情, THE Platform SHALL 返回任务配置信息、当前状态、进度统计（总数、成功数、失败数）

### 需求 5：频道封面图获取

**用户故事：** 作为操作人员，我希望系统自动获取指定 YouTube 频道下的所有视频封面图，以便进行批量分析。

#### 验收标准

1. WHEN Task_Executor 开始执行 Task, THE Channel_Fetcher SHALL 通过 YouTube RSS Feed 获取指定频道下的视频列表
2. WHEN Channel_Fetcher 获取到视频列表, THE Channel_Fetcher SHALL 提取每个视频的缩略图 URL、视频 ID、频道 ID 和频道名称
3. IF Channel_Fetcher 无法访问某个频道的 RSS Feed, THEN THE Channel_Fetcher SHALL 记录错误信息并继续处理其余频道
4. WHEN Channel_Fetcher 完成视频列表获取, THE Image_Downloader SHALL 下载缩略图并上传到 S3 桶，路径格式为 `{任务ID}/input/{图片文件名}`

### 需求 6：图片识别执行

**用户故事：** 作为操作人员，我希望系统根据配置的提示词和运行模式对图片进行 AI 识别，以便自动化审核流程。

#### 验收标准

1. WHEN Task 运行模式为 Batch_Mode, THE Nova_Recognizer SHALL 构建 JSONL 格式的批量推理请求并提交 Bedrock 批量推理任务
2. WHEN Task 运行模式为 Realtime_Mode, THE Nova_Recognizer SHALL 使用可配置的并发数逐张调用 Bedrock 实时推理 API
3. THE Nova_Recognizer SHALL 使用 Task 关联的 Prompt_Template 内容作为模型推理的提示词
4. WHEN Nova_Recognizer 完成单张图片识别, THE Result_Store SHALL 将识别结果保存到 DynamoDB，包含图片名称、识别结果 JSON、状态（成功/失败）
5. IF Nova_Recognizer 调用模型失败, THEN THE Nova_Recognizer SHALL 将该图片标记为失败状态并记录错误信息

### 需求 7：异步任务执行

**用户故事：** 作为操作人员，我希望任务提交后在后台异步执行，以便我可以同时管理多个任务。

#### 验收标准

1. WHEN User 提交 Task 执行请求, THE API_Gateway SHALL 立即返回任务已提交的响应，不阻塞等待执行完成
2. THE Task_Executor SHALL 在后台异步执行 Task 的各个阶段（获取封面、下载图片、AI 识别）
3. WHILE Task 正在执行, THE Task_Executor SHALL 定期更新任务进度信息到 DynamoDB
4. THE Task_Executor SHALL 支持可配置的并发数，控制同时处理的图片数量

### 需求 8：任务运行日志

**用户故事：** 作为操作人员，我希望查看任务的运行日志，以便排查问题和了解执行细节。

#### 验收标准

1. WHILE Task 正在执行, THE Task_Executor SHALL 记录关键操作日志（频道获取、图片下载、模型调用）到 DynamoDB
2. WHEN User 请求查看 Task 的运行日志, THE Platform SHALL 返回按时间排序的日志列表
3. THE Task_Executor SHALL 在日志中包含时间戳、操作类型、操作对象和操作结果

### 需求 9：任务结果查询与过滤

**用户故事：** 作为操作人员，我希望查询和过滤任务的识别结果，以便快速定位需要关注的内容。

#### 验收标准

1. WHEN User 查询 Task 的识别结果, THE Platform SHALL 返回分页的结果列表，包含图片名称、识别结果、状态
2. WHEN User 按条件过滤结果（如：包含儿童、年龄段、置信度范围、成功/失败状态）, THE Platform SHALL 返回符合条件的结果子集
3. THE Result_Store SHALL 区分成功识别的图片和识别失败的图片
4. WHEN Task 执行完成, THE Result_Store SHALL 将完整结果汇总为 JSON 文件保存到 S3，路径格式为 `{任务ID}/output/results.json`

### 需求 10：失败重做机制

**用户故事：** 作为操作人员，我希望对识别失败的图片进行重做，以便提高任务的整体成功率。

#### 验收标准

1. WHEN User 对一个已完成或部分完成的 Task 发起重做请求, THE Task_Executor SHALL 仅重新识别状态为失败的图片
2. THE Task_Executor SHALL 保留原有成功结果不变，仅更新重做后的失败图片结果
3. WHEN 重做完成, THE Result_Store SHALL 更新 Task 的进度统计和最终结果 JSON 文件
4. IF 重做后仍有失败图片, THEN THE Platform SHALL 允许 User 再次发起重做

### 需求 11：S3 存储组织

**用户故事：** 作为操作人员，我希望任务数据在 S3 中按规范组织，以便管理和下载。

#### 验收标准

1. THE Image_Downloader SHALL 将下载的封面图保存到 S3 路径 `{任务ID}/input/` 下
2. THE Result_Store SHALL 将最终结果 JSON 保存到 S3 路径 `{任务ID}/output/` 下
3. WHEN User 请求下载任务结果, THE Platform SHALL 返回 S3 结果文件的预签名下载 URL

### 需求 12：REST API 统一入口

**用户故事：** 作为前端开发者，我希望通过统一的 REST API 与后端交互，以便前后端解耦开发。

#### 验收标准

1. THE API_Gateway SHALL 提供 RESTful 风格的 HTTP API，覆盖用户认证、提示词管理、任务管理、结果查询等所有功能
2. THE API_Gateway SHALL 对所有请求进行认证令牌校验（登录接口除外）
3. WHEN API 请求参数不合法, THE API_Gateway SHALL 返回 400 状态码和具体的参数错误信息
4. IF API 处理过程中发生未预期的错误, THEN THE API_Gateway SHALL 返回 500 状态码和通用错误信息，不暴露内部实现细节
