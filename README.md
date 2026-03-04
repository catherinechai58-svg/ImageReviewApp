# ImageReviewApp — 图片批量识别与审核平台

基于 AWS ECS Fargate 的 YouTube 缩略图内容审核平台。通过 Amazon Bedrock (Nova Lite / Nova Pro) 模型对视频缩略图进行 AI 识别，支持批量和实时两种推理模式，创建任务时可选择模型。

## 架构概览

```
CloudFront (HTTPS) → S3 (React SPA)
                          ↓
ALB → ECS Fargate (FastAPI) → DynamoDB / S3 / Bedrock
         ↑
   Cognito JWT 认证
```

| 组件 | 技术 |
|------|------|
| 后端 | ECS Fargate + FastAPI (Python 3.12) |
| 前端 | React 19 + TypeScript + Vite |
| 认证 | Amazon Cognito |
| 数据库 | DynamoDB (6 张表) |
| AI 推理 | Amazon Bedrock (Converse API) |
| IaC | AWS CDK (Python) |

所有资源统一以 `ImageReviewApp` 为前缀命名，标记 `Project: ImageReviewApp` 标签。

---

## 1. 环境准备

### 1.1 工具要求

- Python 3.12+、Node.js 18+、Docker、AWS CLI v2、AWS CDK CLI

```bash
npm install -g aws-cdk
cdk --version && aws sts get-caller-identity && docker --version
```

### 1.2 安装项目依赖

```bash
pip install -r cdk/requirements.txt
cd frontend && npm install && cd ..
```

### 1.3 AWS 前提

- 目标 region 已申请 Bedrock Nova 模型访问权限
- S3 桶、IAM 角色、DynamoDB 表等全部由 CDK 自动创建，无需手动操作

---

## 2. 首次部署（一次走通）

整个部署分 4 步，无需重复 `cdk deploy`。

### Step 1: CDK Bootstrap

```bash
cd cdk
cdk bootstrap aws://ACCOUNT_ID/ap-southeast-1
```

### Step 2: 部署基础设施

```bash
cdk deploy ImageReviewAppInfraStack
```

记录输出：`UserPoolId`、`UserPoolClientId`、`DistributionDomainName`。

### Step 3: 构建前端（先用占位 API 地址）

首次部署时 ALB 地址还不存在，前端先用占位值构建。AppStack 部署后拿到 ALB 地址会自动把前端推到 S3 + 刷新 CloudFront，后续再更新 `.env.production` 重新 build 即可。

```bash
# 编辑 frontend/.env.production
VITE_API_BASE_URL=http://placeholder
VITE_COGNITO_USER_POOL_ID=<Step 2 输出的 UserPoolId>
VITE_COGNITO_CLIENT_ID=<Step 2 输出的 UserPoolClientId>
VITE_AWS_REGION=ap-southeast-1
```

```bash
cd frontend && npm run build && cd ..
```

### Step 4: 部署应用

```bash
cd cdk
cdk deploy ImageReviewAppStack
```

记录输出 `ALBDnsName`。

### Step 5: 回填 ALB 地址并更新前端

```bash
# 编辑 frontend/.env.production，把 VITE_API_BASE_URL 改为真实 ALB 地址
VITE_API_BASE_URL=http://<ALBDnsName>
```

```bash
cd frontend && npm run build && cd ..
cd cdk && cdk deploy ImageReviewAppStack
```

> 这是首次部署唯一需要重复的步骤。后续代码更新不需要。

### Step 6: 创建管理员

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
- API：`http://<ALBDnsName>/health`

---

## 3. 日常代码更新

后端或前端代码变更后，只需一条命令：

```bash
# 如果改了前端代码，先 build
cd frontend && npm run build && cd ..

# 部署（后端镜像自动重建 + 前端自动上传 + CloudFront 自动刷新）
cd cdk && cdk deploy ImageReviewAppStack
```

---

## 4. 本地开发

### 4.1 前端配置

编辑 `frontend/.env.local`（git 忽略，优先级最高）：

```bash
VITE_API_BASE_URL=
VITE_COGNITO_USER_POOL_ID=<你的 UserPoolId>
VITE_COGNITO_CLIENT_ID=<你的 UserPoolClientId>
VITE_AWS_REGION=ap-southeast-1
```

`VITE_API_BASE_URL` 留空，Vite 会自动代理到 `localhost:8000`。

### 4.2 后端环境变量

```bash
# 从 CDK 输出获取
aws cloudformation describe-stacks \
  --stack-name ImageReviewAppInfraStack \
  --query 'Stacks[0].Outputs' --output table
```

```bash
export USERS_TABLE=ImageReviewApp-Users
export PROMPT_TEMPLATES_TABLE=ImageReviewApp-PromptTemplates
export PROMPT_TEMPLATE_HISTORY_TABLE=ImageReviewApp-PromptTemplateHistory
export TASKS_TABLE=ImageReviewApp-Tasks
export TASK_RESULTS_TABLE=ImageReviewApp-TaskResults
export TASK_LOGS_TABLE=ImageReviewApp-TaskLogs
export IMAGE_BUCKET=<ImageBucketName>
export AWS_REGION_NAME=ap-southeast-1
export USER_POOL_ID=<UserPoolId>
export USER_POOL_CLIENT_ID=<UserPoolClientId>
export ROLE_ARN=<BedrockBatchRoleArn>
export CONCURRENCY=3
```

### 4.3 启动

```bash
# 终端 1: 后端（项目根目录）
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2: 前端
cd frontend && npm run dev
```

访问 `http://localhost:5173`。

### 4.4 环境文件优先级

| 文件 | 用途 | Git |
|------|------|-----|
| `.env.development` | `npm run dev` 默认加载 | 提交 |
| `.env.production` | `npm run build` 加载 | 提交 |
| `.env.local` | 本地覆盖（优先级最高） | 忽略 |

---

## 5. 基础设施变更

```bash
cd cdk

# 预览
cdk diff ImageReviewAppInfraStack
cdk diff ImageReviewAppStack

# 部署
cdk deploy ImageReviewAppInfraStack   # DynamoDB/Cognito/S3/CloudFront/IAM
cdk deploy ImageReviewAppStack        # VPC/ECS/ALB

# 或一次全部
cdk deploy --all
```

---

## 6. 多 Region 部署

默认部署到 `ap-southeast-1`。如需部署到其他 region：

```bash
cd cdk
cdk bootstrap aws://ACCOUNT_ID/us-west-2
cdk deploy --all -c region=us-west-2
```

> ⚠️ 常见错误：`-c region=us-west-2` 不能写成 `-c us-west-2`，`-c` 后面必须是 `key=value` 格式。

注意事项：
- Bootstrap 的 region 必须和部署的 region 一致
- Bedrock 模型可用性因 region 而异，确认目标 region 支持所选模型
- S3 桶名由 CDK 自动生成（`imagereviewapp-images-{ACCOUNT_ID}`）
- CDK Bootstrap 每个 region 执行一次
- `.env.production` 的 `VITE_AWS_REGION` 需与部署 region 一致

---

## 7. 模型配置

创建任务时可选择推理模型。内置可选模型：

| 模型 ID | 名称 |
|---------|------|
| `apac.amazon.nova-lite-v1:0` | Nova Lite v1 (APAC) |
| `amazon.nova-lite-v1:0` | Nova Lite v1 |
| `apac.amazon.nova-pro-v1:0` | Nova Pro v1 (APAC) |
| `amazon.nova-pro-v1:0` | Nova Pro v1 |

自定义可选模型列表：设置环境变量 `AVAILABLE_MODELS`（JSON 数组）：

```bash
export AVAILABLE_MODELS='[{"id":"apac.amazon.nova-lite-v1:0","name":"Nova Lite v1 (APAC)"},{"id":"amazon.nova-pro-v1:0","name":"Nova Pro v1"}]'
```

实时推理使用 Bedrock Converse API，批量推理使用 Bedrock Batch Invocation API。

---

## CDK 资源清单

| 资源类型 | 名称 | Stack |
|----------|------|-------|
| DynamoDB | ImageReviewApp-Users / PromptTemplates / PromptTemplateHistory / Tasks / TaskResults / TaskLogs | Infra |
| S3 | imagereviewapp-images-{ACCOUNT_ID} | Infra |
| S3 | imagereviewapp-frontend-{ACCOUNT_ID} | Infra |
| Cognito | ImageReviewAppUserPool | Infra |
| IAM Role | ImageReviewAppBedrockBatchRole | Infra |
| CloudFront | ImageReviewAppDistribution | Infra |
| VPC / ECS / ALB | ImageReviewApp* | App |

---

## API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | /health | 健康检查 | 否 |
| GET | /models | 可选模型列表 | 否 |
| POST | /auth/login | 登录 | 否 |
| POST | /auth/change-password | 修改密码 | 是 |
| GET/POST | /prompts | 模板列表/创建 | 是 |
| GET/PUT/DELETE | /prompts/{id} | 模板详情/更新/删除 | 是 |
| GET/POST | /tasks | 任务列表/创建 | 是 |
| GET | /tasks/{id} | 任务详情 | 是 |
| POST | /tasks/{id}/execute | 执行任务 (202) | 是 |
| POST | /tasks/{id}/retry | 重做失败图片 (202) | 是 |
| GET | /tasks/{id}/logs | 任务日志 | 是 |
| GET | /tasks/{id}/results | 识别结果（分页+过滤） | 是 |
| GET | /tasks/{id}/results/download | 结果下载链接 | 是 |

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
│   │   ├── models_config.py      # 可选模型配置
│   │   ├── response.py           # 统一异常处理
│   │   ├── worker.py             # 后台任务调度
│   │   ├── workflow.py           # 工作流（Converse API）
│   │   └── routers/
│   │       ├── auth_routes.py
│   │       ├── prompt_routes.py
│   │       └── task_routes.py
│   └── shared/
│       ├── dynamodb.py / s3_utils.py / errors.py / response.py / logger.py
└── frontend/
    ├── .env.development / .env.production / .env.local
    ├── src/
    │   ├── config.ts / services/ / contexts/ / components/ / pages/
    ├── package.json
    └── vite.config.ts
```
