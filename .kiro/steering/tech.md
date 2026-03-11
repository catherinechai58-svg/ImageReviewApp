# 技术栈

## 编程语言
- Python 3.x

## 核心依赖库
- `boto3` - AWS SDK，用于 S3、Bedrock 服务交互
- `openpyxl` - Excel 文件读写（频道列表、视频信息）
- `google-api-python-client` - YouTube Data API 集成（可选）
- `google-auth` - Google OAuth 认证

## AWS 服务
- Amazon Bedrock - AI 模型推理服务
- Amazon S3 - 图片存储和批量输入/输出
- IAM - 权限管理（需要 BedrockBatchInferenceRole）

## 推理模型
- Amazon Nova Lite v1 (apac.amazon.nova-lite-v1:0)
- 使用 APAC 推理配置文件

## 常用命令

### 上传缩略图到 S3
```bash
python3 upload_from_lambda_input.py \
  --input lambda_input.json \
  --bucket nova-test-image \
  --prefix input_from_url/ \
  --region ap-northeast-1
```

### 创建 Bedrock 批量推理任务
```bash
python3 bedrock_batch_nova2_lite.py \
  --bucket nova-test-image \
  --input-prefix input_from_url/ \
  --batch-output-prefix output/ \
  --region ap-northeast-1 \
  --limit 500
```

### 重建结果 CSV
```bash
python3 bedrock_batch_nova2_lite.py \
  --reuse-flow \
  --rebuild-success-csv success_results.csv \
  --rebuild-output-prefix output/ \
  --bucket nova-test-image \
  --region ap-northeast-1
```

### 从频道获取视频（使用 RSS Feed）
```bash
python3 upload_from_lambda_input.py \
  --channel-fetch \
  --channel-ids "UCxxxxx,UCyyyyy" \
  --channel-video-limit 10 \
  --output-json channel_videos.json
```

### 完整工作流（上传 + 推理）
```bash
python3 upload_from_lambda_input.py \
  --workflow \
  --input lambda_input.json \
  --bucket nova-test-image \
  --bedrock-script bedrock_batch_nova2_lite.py
```

## 环境变量配置

```bash
export BUCKET="nova-test-image"
export AWS_REGION="ap-northeast-1"
export INPUT_PREFIX="input_from_url/"
export OUTPUT_PREFIX="output/"
export LIMIT="500"
export MODEL_ID="apac.amazon.nova-lite-v1:0"
export ROLE_ARN="arn:aws:iam::359144475210:role/BedrockBatchInferenceRole"
```

## 认证要求
- AWS 凭证配置（通过 AWS CLI 或环境变量）
- YouTube API 需要 OAuth 2.0 token（可选，仅使用热词脚本时）
