# 项目结构

## 核心脚本

### bedrock_batch_nova2_lite.py
Bedrock 批量推理主脚本

主要功能：
- 从 S3 或 JSON 加载图片列表
- 复制图片到批量推理输入目录
- 构建 JSONL 格式的推理请求
- 创建 Bedrock 批量推理任务
- 解析推理结果并生成 CSV 报告
- 支持断点续传（--resume-output-prefix, --resume-success-csv）
- 结果重建（--reuse-flow, --rebuild-only）

关键函数：
- `list_image_keys()` - 列出 S3 图片
- `build_record()` - 构建推理请求记录
- `rebuild_success_csv()` - 从 JSONL 输出重建 CSV
- `parse_text_payload()` - 解析模型 JSON 响应

### upload_from_lambda_input.py
图片上传和频道数据获取脚本

主要功能：
- 从 JSON 文件读取视频元数据
- 下载 YouTube 缩略图并上传到 S3
- 从 YouTube 频道获取视频列表（RSS Feed 或 API）
- 过滤视频（基于频道白名单和视频信息表）
- 集成 Bedrock 工作流（--workflow）

关键函数：
- `download_image()` - 下载缩略图
- `fetch_video_ids_with_feed()` - 通过 RSS 获取视频
- `fetch_video_ids_with_hotword()` - 通过 YouTube API 获取
- `filter_items_by_channel()` - 频道过滤
- `run_bedrock_workflow()` - 调用 Bedrock 脚本

## 数据文件格式

### 输入 JSON (lambda_input.json)
```json
[
  {
    "image_name": "video_id.jpg",
    "url": "https://i.ytimg.com/vi/video_id/mqdefault.jpg",
    "video_id": "video_id",
    "channel_id": "UCxxxxx",
    "channel_name": "频道名称"
  }
]
```

### 输出 CSV (success_results.csv)
```csv
image_name,contains_child,age_group,is_child_targeted,confidence,视频链接,UID,频道名称
video_id.jpg,true,kids,true,0.95,https://www.youtube.com/watch?v=video_id,UCxxxxx,频道名称
```

### Bedrock 输入 JSONL
```json
{
  "recordId": "0",
  "modelInput": {
    "schemaVersion": "messages-v1",
    "system": [{"text": "You are a YouTube thumbnail analyzer..."}],
    "messages": [{
      "role": "user",
      "content": [
        {"image": {"format": "jpeg", "source": {"s3Location": {"uri": "s3://bucket/key"}}}},
        {"text": "Analyze this YouTube thumbnail..."}
      ]
    }],
    "inferenceConfig": {"temperature": 0, "maxTokens": 200, "topP": 0.9}
  }
}
```

## S3 目录结构

```
s3://nova-test-image/
├── input_from_url/          # 原始缩略图
│   └── video_id.jpg
├── batch/input/             # 批量推理输入
│   ├── nova2lite-batch-20240315120000/
│   │   ├── video_id.jpg
│   │   └── batch_input_nova2lite-batch-20240315120000.jsonl
└── output/                  # 批量推理输出
    └── nova2lite-batch-20240315120000/
        └── *.jsonl.out
```

## 配置文件

### Excel 文件
- 频道列表 (channel_list.xlsx) - 包含 `UID` 列
- 视频信息 (video_info.xlsx) - 包含 `video_id`, `channel_id`, `channel_display_name` 列
- Book1.xlsx / BOOK2.xlsx - 频道映射表（可选）

### 认证文件
- `client_secret.json` - Google OAuth 客户端密钥
- `hotword_token.json` - YouTube API OAuth token

## 代码约定

- 使用 `normalize_prefix()` 确保 S3 前缀以 `/` 结尾
- 图片格式检测：`.png` → "png"，其他 → "jpeg"
- 视频 ID 从图片名提取：`video_id_from_image()`
- 错误处理：跳过失败项，继续处理其余项
- 日志输出：使用 JSON 格式便于解析
