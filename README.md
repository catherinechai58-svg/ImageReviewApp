# ImageReviewApp — YouTube 缩略图内容审核平台

基于 AWS ECS Fargate 的 YouTube 视频缩略图 AI 内容审核平台。通过 Amazon Bedrock（Nova Lite / Nova Pro）模型对视频缩略图进行智能识别，支持批量和实时两种推理模式，支持 YouTube Data API v3 无限制获取频道视频。

---

## 功能特性

### 核心功能
- **AI 图片审核** — 使用 Amazon Bedrock Converse API 对 YouTube 缩略图进行内容识别
- **批量 + 实时推理** — 创建任务时可选择批量模式（Batch Invocation）或实时模式（Converse API）
- **多模型支持** — 支持 Nova Lite v1/v2、Nova Pro 等模型，创建任务时可选
- **YouTube API 集成** — 配置 YouTube Data API Key 后可无限制获取频道全部视频，无 Key 时自动回退 RSS Feed（每频道最多 15 条）
- **频道格式兼容** — 支持 `UCxxxx` 频道 ID、`@handle` 和频道 URL 三种输入格式

### 任务管理
- **创建 / 编辑 / 删除任务** — 完整的任务 CRUD，编辑后自动重置为待执行状态
- **执行 / 重做 / 强制重做** — 支持执行任务、智能重做失败图片、强制重做全部图片
- **任务排队机制** — 超过并发上限的任务自动排队，线程空闲时自动开始执行
- **实时状态刷新** — 任务执行中每 5 秒自动刷新状态和日志，日志自动滚动到最新
- **视频时间过滤** — 创建任务时可指定视频发布时间范围

### 系统管理
- **提示词模板** — 可创建、编辑、查看历史版本的提示词模板
- **用户管理** — 管理员可创建/删除用户、重置密码（基于 Cognito）
- **系统设置** — 管理员可在界面上配置任务并发数、推理并发数、YouTube API Key
- **结果导出** — 支持识别结果分页查看、过滤和下载

---

## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
                           ▼
                   ┌───────────────┐
                   │  CloudFront   │
                   │  (CDN 分发)    │
                   └───────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
     ┌─────────────┐          ┌─────────────────┐
     │  S3 Bucket   │          │       ALB       │
     │ (React SPA)  │          │  (负载均衡器)    │
     └─────────────┘          └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   ECS Fargate    │
                              │   (FastAPI)      │
                              │                  │
                              │  ┌────────────┐  │
                              │  │  Worker     │  │
                              │  │ ThreadPool  │  │
                              │  └────────────┘  │
                              └──┬───┬───┬───┬──┘
                                 │   │   │   │
                    ┌────────────┘   │   │   └────────────┐
                    ▼                ▼   ▼                ▼
              ┌──────────┐   ┌──────────┐ ┌─────────┐ ┌──────────┐
              │ Cognito  │   │ DynamoDB │ │   S3    │ │ Bedrock  │
              │ (认证)    │   │ (7张表)  │ │ (图片)  │ │ (AI推理) │
              └──────────┘   └──────────┘ └─────────┘ └──────────┘
```

### 部署架构图

```
┌─ AWS Cloud ──────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─ ImageReviewAppInfraStack ─────────────────────────────────┐  │
│  │                                                             │  │
│  │  CloudFront ─── S3 (Frontend)                               │  │
│  │  Cognito UserPool + Client                                  │  │
│  │  S3 (Images: imagereviewapp-images-{ACCOUNT_ID})            │  │
│  │  IAM Role (BedrockBatchRole)                                │  │
│  │  DynamoDB Tables:                                           │  │
│  │    ├── ImageReviewApp-Users                                 │  │
│  │    ├── ImageReviewApp-PromptTemplates                       │  │
│  │    ├── ImageReviewApp-PromptTemplateHistory                 │  │
│  │    ├── ImageReviewApp-Tasks                                 │  │
│  │    ├── ImageReviewApp-TaskResults                           │  │
│  │    └── ImageReviewApp-TaskLogs                              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ ImageReviewAppStack ──────────────────────────────────────┐  │
│  │                                                             │  │
│  │  VPC (Public + Private Subnets)                             │  │
│  │    └── ALB (Public)                                         │  │
│  │         └── ECS Fargate Service                             │  │
│  │              └── FastAPI Container (Python 3.12)            │  │
│  │                   ├── API Routes                            │  │
│  │                   ├── Worker ThreadPool                     │  │
│  │                   └── Workflow Engine                       │  │
│  │                                                             │  │
│  │  S3 Deploy (Frontend dist → S3 + CloudFront Invalidation)  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | ECS Fargate + FastAPI (Python 3.12) |
| 前端 | React 19 + TypeScript + Vite |
| 认证 | Amazon Cognito (JWT) |
| 数据库 | DynamoDB (7 张表) |
| 存储 | Amazon S3 (图片 + 前端静态资源) |
| AI 推理 | Amazon Bedrock (Converse API + Batch Invocation) |
| CDN | Amazon CloudFront |
| 负载均衡 | Application Load Balancer |
| IaC | AWS CDK (Python) |
| 视频数据 | YouTube Data API v3 / RSS Feed |

### 任务状态流转

```
pending (待执行)
   │
   ▼  执行/重做
queued (排队中) ──── 线程池已满，等待空闲线程
   │
   ▼  线程开始执行
fetching (获取封面中) → downloading (下载图片中) → recognizing (识别中)
   │                                                    │
   ▼                                                    ▼
failed (失败)                              completed (已完成)
   │                                      partial_completed (部分完成)
   │                                              │
   └──────── 重做/强制重做 ◄──────────────────────┘
```

---

## 环境准备

### 工具要求

- Python 3.12+
- Node.js 18+
- Docker
- AWS CLI v2
- AWS CDK CLI
- jq（用于脚本解析 JSON）

```bash
npm install -g aws-cdk
cdk --version && aws sts get-caller-identity && docker --version
```

### AWS 前提

- 目标 Region 已申请 Bedrock Nova 模型访问权限
- S3 桶、IAM 角色、DynamoDB 表等全部由 CDK 自动创建

### 可选：YouTube Data API Key

配置后可突破 RSS Feed 每频道 15 条视频的限制：

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建项目或选择已有项目
3. 启用 [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
4. 创建 [API Key](https://console.cloud.google.com/apis/credentials)
5. 部署后在「系统设置」页面填入 API Key

---

## 首次部署

### Step 1: 安装依赖

```bash
pip install -r cdk/requirements.txt
cd frontend && npm install && cd ..
```

### Step 2: CDK Bootstrap

```bash
cd cdk
cdk bootstrap aws://ACCOUNT_ID/ap-southeast-1
```

### Step 3: 部署基础设施

```bash
cdk deploy ImageReviewAppInfraStack
```

记录输出：`UserPoolId`、`UserPoolClientId`、`DistributionDomainName`。

### Step 4: 构建前端（占位 API 地址）

首次部署时 ALB 地址还不存在，先用占位值：

```bash
cat > frontend/.env.production << EOF
VITE_API_BASE_URL=http://placeholder
VITE_COGNITO_USER_POOL_ID=<Step 3 输出的 UserPoolId>
VITE_COGNITO_CLIENT_ID=<Step 3 输出的 UserPoolClientId>
VITE_AWS_REGION=ap-southeast-1
EOF

cd frontend && npm run build && cd ..
```

### Step 5: 部署应用

```bash
cd cdk
cdk deploy ImageReviewAppStack
```

记录输出 `ALBDnsName`。

### Step 6: 回填 ALB 地址并更新前端

```bash
cat > frontend/.env.production << EOF
VITE_API_BASE_URL=http://<ALBDnsName>
VITE_COGNITO_USER_POOL_ID=<UserPoolId>
VITE_COGNITO_CLIENT_ID=<UserPoolClientId>
VITE_AWS_REGION=ap-southeast-1
EOF

cd frontend && npm run build && cd ..
cd cdk && cdk deploy ImageReviewAppStack
```

> 这是首次部署唯一需要重复的步骤。

### Step 7: 创建管理员

```bash
REGION=ap-southeast-1
USER_POOL_ID=<你的 UserPoolId>

aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username admin \
  --temporary-password 'TempPass123!' \
  --region $REGION

aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username admin \
  --password 'YourPassword123!' \
  --permanent \
  --region $REGION
```

### 访问

- 前端：`https://<DistributionDomainName>`
- API 健康检查：`http://<ALBDnsName>/health`

---

## 日常代码更新

```bash
# 如果改了前端代码，先 build
cd frontend && npm run build && cd ..

# 部署（后端镜像自动重建 + 前端自动上传 + CloudFront 自动刷新）
cd cdk && cdk deploy ImageReviewAppStack
```

---

## 本地开发

### 一键启动脚本

```bash
# 1. 获取环境变量（首次或 Stack 更新后执行）
eval $(bash setup_env.sh)

# 2. 启动后端
bash start_backend.sh

# 3. 另开终端，启动前端
cd frontend && npm run dev
```

访问 `http://localhost:5173`

### 手动配置

#### 后端环境变量

```bash
# 从 CDK 输出自动获取
eval $(bash setup_env.sh)

# 或手动设置
export USERS_TABLE=ImageReviewApp-Users
export PROMPT_TEMPLATES_TABLE=ImageReviewApp-PromptTemplates
export PROMPT_TEMPLATE_HISTORY_TABLE=ImageReviewApp-PromptTemplateHistory
export TASKS_TABLE=ImageReviewApp-Tasks
export TASK_RESULTS_TABLE=ImageReviewApp-TaskResults
export TASK_LOGS_TABLE=ImageReviewApp-TaskLogs
export SETTINGS_TABLE=ImageReviewApp-Settings
export IMAGE_BUCKET=imagereviewapp-images-<ACCOUNT_ID>
export AWS_REGION_NAME=ap-southeast-1
export USER_POOL_ID=<UserPoolId>
export USER_POOL_CLIENT_ID=<UserPoolClientId>
export ROLE_ARN=<BedrockBatchRoleArn>
```

#### 启动服务

```bash
# 终端 1: 后端
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2: 前端
cd frontend && npm run dev
```

#### 前端环境文件

| 文件 | 用途 | Git |
|------|------|-----|
| `.env.development` | `npm run dev` 默认加载 | 提交 |
| `.env.production` | `npm run build` 加载 | 提交 |
| `.env.local` | 本地覆盖（优先级最高） | 忽略 |

---

## 系统设置

管理员登录后，导航栏可见「系统设置」入口，可配置：

| 设置项 | 说明 | 范围 | 默认值 | 生效时机 |
|--------|------|------|--------|----------|
| 任务并发数 | 同时执行的最大任务数 | 1~20 | 3 | 保存后立即生效 |
| 实时推理并发数 | 实时模式下 Bedrock API 并发调用数 | 1~50 | 5 | 下次任务执行时生效 |
| YouTube API Key | YouTube Data API v3 密钥 | — | 空 | 下次任务执行时生效 |

> 未配置 YouTube API Key 时自动回退 RSS Feed（每频道最多 15 条视频）。

---

## 模型配置

创建任务时可选择推理模型。内置可选模型：

| 模型 ID | 名称 |
|---------|------|
| `apac.amazon.nova-lite-v1:0` | Nova Lite v1 |
| `global.amazon.nova-2-lite-v1:0` | Nova Lite v2 |

自定义可选模型列表：设置环境变量 `AVAILABLE_MODELS`（JSON 数组）：

```bash
export AVAILABLE_MODELS='[{"id":"apac.amazon.nova-lite-v1:0","name":"Nova Lite v1"},{"id":"amazon.nova-pro-v1:0","name":"Nova Pro v1"}]'
```

---

## 多 Region 部署

```bash
cd cdk
cdk bootstrap aws://ACCOUNT_ID/us-west-2
cdk deploy --all -c region=us-west-2
```

注意事项：
- `-c region=us-west-2` 必须是 `key=value` 格式
- Bootstrap 的 Region 必须和部署的 Region 一致
- Bedrock 模型可用性因 Region 而异
- `.env.production` 的 `VITE_AWS_REGION` 需与部署 Region 一致

---

## API 端点

### 公开接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| GET | /models | 可选模型列表 |

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/login | 登录 |
| POST | /auth/force-change-password | 强制修改密码（首次登录） |
| POST | /auth/change-password | 修改密码 |

### 提示词模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /prompts | 模板列表 |
| POST | /prompts | 创建模板 |
| GET | /prompts/{id} | 模板详情 |
| PUT | /prompts/{id} | 更新模板 |
| DELETE | /prompts/{id} | 删除模板 |

### 任务管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /tasks | 任务列表 |
| POST | /tasks | 创建任务 |
| GET | /tasks/{id} | 任务详情 |
| PUT | /tasks/{id} | 编辑任务 |
| DELETE | /tasks/{id} | 删除任务 |
| POST | /tasks/{id}/execute | 执行任务 |
| POST | /tasks/{id}/retry | 智能重做失败图片 |
| POST | /tasks/{id}/retry-all | 强制重做全部图片 |
| GET | /tasks/{id}/logs | 任务日志 |
| GET | /tasks/{id}/results | 识别结果（分页+过滤） |
| GET | /tasks/{id}/results/download | 结果下载链接 |

### 用户管理（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /users/me | 当前用户信息 |
| GET | /users | 用户列表 |
| POST | /users | 创建用户 |
| PUT | /users/{username}/reset-password | 重置密码 |
| DELETE | /users/{username} | 删除用户 |

### 系统设置（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /settings | 读取设置 |
| PUT | /settings | 更新设置 |

---

## 项目结构

```
├── cdk/
│   ├── app.py                    # CDK 入口（-c region 参数）
│   ├── infra_stack.py            # Infra: DynamoDB/Cognito/S3/CloudFront/IAM
│   ├── app_stack.py              # App: VPC/ECS/ALB/前端部署
│   └── requirements.txt
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py               # FastAPI 入口 + /health + /models
│   │   ├── auth.py               # Cognito JWT 验证
│   │   ├── constants.py          # 任务状态常量
│   │   ├── models_config.py      # 可选模型配置
│   │   ├── response.py           # 统一异常处理
│   │   ├── worker.py             # 后台任务调度（ThreadPool + 排队）
│   │   ├── workflow.py           # 工作流引擎（YouTube API/RSS + 下载 + 推理）
│   │   └── routers/
│   │       ├── auth_routes.py    # 登录/改密
│   │       ├── prompt_routes.py  # 提示词模板 CRUD
│   │       ├── task_routes.py    # 任务 CRUD + 执行/重做
│   │       ├── user_routes.py    # 用户管理
│   │       └── settings_routes.py # 系统设置
│   └── shared/
│       ├── dynamodb.py           # DynamoDB 操作封装
│       ├── s3_utils.py           # S3 操作封装
│       ├── errors.py             # 自定义异常
│       ├── response.py           # 响应格式
│       └── logger.py             # 任务日志写入
├── frontend/
│   ├── .env.development / .env.production / .env.example
│   ├── vite.config.ts            # Vite 配置 + API 代理
│   ├── src/
│   │   ├── App.tsx               # 路由配置
│   │   ├── config.ts             # 环境变量读取
│   │   ├── services/api.ts       # Axios 实例 + Token 拦截器
│   │   ├── contexts/AuthContext.tsx
│   │   ├── components/
│   │   │   ├── Layout.tsx        # 导航栏布局
│   │   │   └── ProtectedRoute.tsx
│   │   └── pages/
│   │       ├── LoginPage.tsx
│   │       ├── HomePage.tsx
│   │       ├── TasksPage.tsx     # 任务列表
│   │       ├── TaskFormPage.tsx   # 创建/编辑任务
│   │       ├── TaskDetailPage.tsx # 任务详情（实时刷新）
│   │       ├── ResultsPage.tsx   # 识别结果
│   │       ├── PromptsPage.tsx   # 模板列表
│   │       ├── PromptFormPage.tsx # 创建/编辑模板
│   │       ├── PromptViewPage.tsx # 模板详情
│   │       ├── UsersPage.tsx     # 用户管理
│   │       └── SettingsPage.tsx  # 系统设置
│   └── package.json
├── setup_env.sh                  # 从 CDK 输出获取环境变量
├── start_backend.sh              # 一键启动后端
├── bedrock_batch_nova2_lite.py   # 独立批量推理脚本
└── upload_from_lambda_input.py   # 独立缩略图上传脚本
```

---

## CDK 资源清单

| 资源类型 | 名称 | Stack |
|----------|------|-------|
| DynamoDB | ImageReviewApp-Users | Infra |
| DynamoDB | ImageReviewApp-PromptTemplates | Infra |
| DynamoDB | ImageReviewApp-PromptTemplateHistory | Infra |
| DynamoDB | ImageReviewApp-Tasks | Infra |
| DynamoDB | ImageReviewApp-TaskResults | Infra |
| DynamoDB | ImageReviewApp-TaskLogs | Infra |
| DynamoDB | ImageReviewApp-Settings | Infra |
| S3 | imagereviewapp-images-{ACCOUNT_ID} | Infra |
| S3 | imagereviewapp-frontend-{ACCOUNT_ID} | Infra |
| Cognito | ImageReviewAppUserPool | Infra |
| IAM Role | ImageReviewAppBedrockBatchRole | Infra |
| CloudFront | ImageReviewAppDistribution | Infra |
| VPC / ECS / ALB | ImageReviewApp* | App |
