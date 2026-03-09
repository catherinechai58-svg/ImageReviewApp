"""工作流执行逻辑 — 完整工作流和重做工作流。"""

import asyncio
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from backend.shared.dynamodb import put_item, query_all_pages, update_item
from backend.shared.logger import write_task_log
from backend.shared.s3_utils import (
    build_batch_input_path,
    build_results_path,
    build_s3_path,
    download_file,
    list_objects,
    upload_file,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ══════════════════════════════════════════════
# 工具函数（原 lambdas 中提取）
# ══════════════════════════════════════════════

# --- channel_fetcher ---

_YT_API_BASE = "https://www.googleapis.com/youtube/v3"
_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
_RSS_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def _get_youtube_api_key() -> str:
    try:
        from backend.app.routers.settings_routes import get_setting
        key = get_setting("youtube_api_key")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("YOUTUBE_API_KEY", "")


def _yt_api_get(path: str, params: dict) -> dict:
    import json as _json
    query = urllib.parse.urlencode(params)
    url = f"{_YT_API_BASE}/{path}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _json.loads(resp.read())


def _resolve_channel_id(raw: str, api_key: str) -> tuple[str, str]:
    """将频道 ID 或 @handle 解析为 (channel_id, channel_name)。"""
    if raw.startswith("UC") and len(raw) == 24:
        data = _yt_api_get("channels", {"part": "snippet", "id": raw, "key": api_key})
        items = data.get("items", [])
        name = items[0]["snippet"]["title"] if items else raw
        return raw, name
    params = {"part": "snippet", "key": api_key}
    if raw.startswith("@"):
        params["forHandle"] = raw[1:]
    else:
        params["forHandle"] = raw
    data = _yt_api_get("channels", params)
    items = data.get("items", [])
    if not items:
        raise ValueError(f"无法解析频道: {raw}")
    return items[0]["id"], items[0]["snippet"]["title"]


def _fetch_playlist_videos(channel_id: str, channel_name: str, api_key: str,
                           date_from: str = "", date_to: str = "") -> list[dict]:
    """通过 playlistItems.list 分页获取频道全部视频。"""
    uploads_id = "UU" + channel_id[2:]
    videos: list[dict] = []
    page_token = None

    while True:
        params: dict = {
            "part": "snippet", "playlistId": uploads_id,
            "maxResults": 50, "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        data = _yt_api_get("playlistItems", params)

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            if not video_id:
                continue
            published = snippet.get("publishedAt", "")
            pub_date = published[:10] if published else ""
            if date_from and pub_date and pub_date < date_from:
                continue
            if date_to and pub_date and pub_date > date_to:
                continue
            videos.append({
                "video_id": video_id,
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                "channel_id": channel_id, "channel_name": channel_name,
                "published": published,
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def _fetch_feed_rss(channel_id: str) -> list[dict]:
    """RSS Feed 回退（最多 15 条）。"""
    url = _RSS_URL.format(channel_id=channel_id)
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_text = resp.read().decode("utf-8")
            break
        except Exception as exc:
            last_err = exc
            if attempt < 2:
                time.sleep(1 * (2 ** attempt))
    else:
        raise last_err  # type: ignore[misc]

    root = ET.fromstring(xml_text)
    videos: list[dict] = []
    feed_author = root.find("atom:author/atom:name", _RSS_NS)
    feed_channel_name = feed_author.text if feed_author is not None else channel_id

    for entry in root.findall("atom:entry", _RSS_NS):
        video_id_el = entry.find("yt:videoId", _RSS_NS)
        if video_id_el is None or not video_id_el.text:
            continue
        video_id = video_id_el.text
        author_name_el = entry.find("atom:author/atom:name", _RSS_NS)
        ch_name = author_name_el.text if author_name_el is not None else feed_channel_name
        published_el = entry.find("atom:published", _RSS_NS)
        published = published_el.text if published_el is not None and published_el.text else ""
        videos.append({"video_id": video_id,
                        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                        "channel_id": channel_id, "channel_name": ch_name, "published": published})
    return videos


def _resolve_handle_to_channel_id(handle: str) -> str:
    """通过抓取 YouTube 页面将 @handle 解析为 UCxxxx channel ID。"""
    import re
    url = f"https://www.youtube.com/{handle}" if handle.startswith("@") else f"https://www.youtube.com/@{handle}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    m = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]+)"', html)
    if not m:
        raise ValueError(f"无法从 {handle} 解析出频道 ID")
    return m.group(1)


def _fetch_channel_videos(channel_id: str, date_from: str = "", date_to: str = "") -> list[dict]:
    """获取频道视频：有 API Key 用 YouTube API（无限制），失败或无 Key 回退 RSS（最多 15 条）。"""
    api_key = _get_youtube_api_key()
    if api_key:
        try:
            resolved_id, channel_name = _resolve_channel_id(channel_id, api_key)
            return _fetch_playlist_videos(resolved_id, channel_name, api_key, date_from, date_to)
        except Exception as e:
            print(f"[channel_fetch] YouTube API failed for {channel_id}, falling back to RSS: {e}")
    # 无 API Key 或 API 失败，回退 RSS — 需要先解析 @handle
    if channel_id.startswith("@") or (not channel_id.startswith("UC")):
        channel_id = _resolve_handle_to_channel_id(channel_id)
    return _fetch_feed_rss(channel_id)


# --- image_downloader ---

def _download_image(url: str) -> bytes:
    """从 URL 下载图片，带固定间隔重试。"""
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception as exc:
            last_err = exc
            if attempt < 1:
                time.sleep(2)
    raise last_err  # type: ignore[misc]


# --- recognizer_batch helpers ---

def _detect_format(image_name: str) -> str:
    """根据文件扩展名检测图片格式。"""
    return "png" if image_name.lower().endswith(".png") else "jpeg"


def _assemble_user_prompt(payload: dict) -> str:
    """组装完整的用户提示词：内置前缀 + 用户分析要求 + 审核判定规则。"""
    from backend.app.system_prompt import USER_PROMPT_PREFIX
    parts = [USER_PROMPT_PREFIX, payload["user_prompt"]]
    rules = payload.get("review_rules", "")
    if rules:
        parts.append(f"\n\n审核判定规则：\n{rules}")
    return "\n".join(parts)


def _build_record(record_id: str, s3_uri: str, image_format: str, system_prompt: str, user_prompt: str) -> dict:
    """构建单条 JSONL 推理记录。"""
    return {
        "recordId": record_id,
        "modelInput": {
            "schemaVersion": "messages-v1",
            "system": [{"text": system_prompt, "cachePoint": {"type": "default"}}],
            "messages": [{"role": "user", "content": [
                {"image": {"format": image_format, "source": {"s3Location": {"uri": s3_uri}}}},
                {"text": user_prompt},
            ]}],
            "inferenceConfig": {"temperature": 0, "maxTokens": 200, "topP": 0.9},
        },
    }


def _build_jsonl(images: list[dict], task_id: str, bucket: str, system_prompt: str, user_prompt: str) -> str:
    """为图片列表构建完整的 JSONL 内容。"""
    lines = []
    for idx, img in enumerate(images):
        s3_key = img["s3_key"]
        image_name = img.get("image_name", s3_key.rsplit("/", 1)[-1])
        s3_uri = f"s3://{bucket}/{s3_key}"
        record = _build_record(str(idx), s3_uri, _detect_format(image_name), system_prompt, user_prompt)
        lines.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(lines) + "\n" if lines else ""


# --- result_collector helpers ---

def _parse_model_output(model_output: dict) -> tuple[dict, str]:
    """从 Bedrock 批量推理 modelOutput 中提取 result_json 和 review_result。"""
    try:
        text = model_output["output"]["message"]["content"][0]["text"]
        # 模型结果可能包含```json 或 ```,请判断并去掉
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        result_json = json.loads(text)
        return result_json, result_json.get("review_result", "fail")
    except (KeyError, IndexError, json.JSONDecodeError):
        return {}, "fail"


def _decimal_to_native(obj):
    """递归转换 DynamoDB Decimal 类型为 Python 原生类型"""
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


def _generate_results_json(task_id: str) -> None:
    """从 TaskResults 表查询所有成功记录，生成 results.json 上传到 S3。"""
    results_table = os.environ["TASK_RESULTS_TABLE"]
    bucket = os.environ["IMAGE_BUCKET"]
    all_results = query_all_pages(table_name=results_table, key_condition=Key("task_id").eq(task_id))
    success_results = [
        _decimal_to_native({
            "image_name": r.get("image_name", ""), "video_id": r.get("video_id", ""),
            "channel_id": r.get("channel_id", ""), "channel_name": r.get("channel_name", ""),
            "s3_key": r.get("s3_key", ""), "status": r.get("status", ""),
            "result_json": r.get("result_json", {}), "review_result": r.get("review_result", "")
        })
        for r in all_results if r.get("status") == "success"
    ]
    results_json = json.dumps(success_results, ensure_ascii=False, indent=2)
    results_key = build_results_path(task_id)
    upload_file(bucket, results_key, results_json)
    write_task_log(task_id, "model_invoke", "results.json", "success",
                   f"已生成 results.json ({len(success_results)} 条成功记录) 到 {results_key}")


import re as _re

# --- recognizer_realtime helpers ---

def _parse_converse_response(response: dict) -> dict:
    """解析 Bedrock converse 响应，提取 JSON 结果。"""
    try:
        text = response["output"]["message"]["content"][0]["text"]
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # 清理无效 unicode 转义
        text = _re.sub(r'\\u[0-9a-fA-F]{0,3}(?![0-9a-fA-F])', '', text)
        logger.debug(f"Bedrock response text: {text}")
        result = json.loads(text, parse_float=Decimal)
        return result
    except (KeyError, IndexError) as e:
        logger.error(f"Failed to extract text from response: {e}, response structure: {response}")
        raise ValueError(f"Invalid response structure: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}, text: {text[:500]}")
        raise ValueError(f"Invalid JSON in response: {e}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_task_status(task_id: str, status: str, stats: dict | None = None) -> None:
    """更新任务状态和统计信息。"""
    table = os.environ.get("TASKS_TABLE", "Tasks")
    now = _now_iso()

    parts = ["#st = :status", "#ua = :updated_at"]
    values = {":status": status, ":updated_at": now}
    names = {"#st": "status", "#ua": "updated_at"}

    if stats:
        if "total" in stats:
            parts.append("total_images = :total")
            values[":total"] = stats["total"]
        if "success" in stats:
            parts.append("success_count = :sc")
            values[":sc"] = stats["success"]
        if "failed" in stats:
            parts.append("failure_count = :fc")
            values[":fc"] = stats["failed"]

    update_item(table, {"task_id": task_id}, "SET " + ", ".join(parts), values, names)
    write_task_log(task_id, "status_update", task_id, "success", f"状态更新为 {status}")


# ══════════════════════════════════════════════
# 完整工作流
# ══════════════════════════════════════════════

def run_workflow(task_id: str, payload: dict) -> None:
    """完整工作流：频道获取 → 图片下载 → 推理 → 结果收集 → 状态更新。"""
    skip_channel_fetch = payload.get("skip_channel_fetch", False)
    
    # Step 1: 频道获取（可跳过）
    if skip_channel_fetch:
        all_videos = payload.get("images", [])
    else:
        channel_ids = payload["channel_ids"]
        all_videos: list[dict] = []
        success_ch = 0
        fail_ch = 0

        date_from = payload.get("date_from", "")
        date_to = payload.get("date_to", "")

        for ch_id in channel_ids:
            try:
                videos = _fetch_channel_videos(ch_id, date_from, date_to)
                all_videos.extend(videos)
                success_ch += 1
                write_task_log(task_id, "channel_fetch", ch_id, "success", f"获取到 {len(videos)} 个视频")
            except Exception as exc:
                import traceback
                fail_ch += 1
                err_detail = f"{type(exc).__name__}: {exc}"
                print(f"[channel_fetch] {ch_id} failed: {err_detail}")
                traceback.print_exc()
                write_task_log(task_id, "channel_fetch", ch_id, "failed", err_detail)

        if success_ch == 0 and fail_ch > 0:
            raise RuntimeError(f"所有频道获取失败 ({fail_ch}/{len(channel_ids)})")

    # Step 1.5: 按时间范围过滤（RSS 回退时需要，API 路径已在获取时过滤）
    if not skip_channel_fetch:
        date_from = date_from  # 已在上面赋值
        date_to = date_to
    else:
        date_from = payload.get("date_from", "")
        date_to = payload.get("date_to", "")
    if date_from or date_to:
        before_count = len(all_videos)
        filtered = []
        for v in all_videos:
            pub = v.get("published", "")[:10]  # "2024-03-15T..." → "2024-03-15"
            if not pub:
                filtered.append(v)
                continue
            if date_from and pub < date_from:
                continue
            if date_to and pub > date_to:
                continue
            filtered.append(v)
        all_videos = filtered
        write_task_log(task_id, "date_filter", "filter", "success",
                       f"时间过滤: {before_count} → {len(all_videos)} ({date_from} ~ {date_to})")

    # Step 2: 图片下载
    downloaded: list[dict] = []
    
    for idx, video in enumerate(all_videos, 1):
        video_id = video["video_id"]
        image_name = f"{video_id}.jpg"
        s3_key = build_s3_path(task_id, image_name)
        try:
            
            image_data = _download_image(video["thumbnail_url"])
            
            
            upload_file(None, s3_key, image_data)
            downloaded.append({**video, "s3_key": s3_key, "image_name": image_name})
            write_task_log(task_id, "image_download", image_name, "success", f"已上传到 {s3_key}")
        except Exception as exc:
            error_type = type(exc).__name__
            write_task_log(task_id, "image_download", image_name, "failed", 
                          f"{error_type}: {str(exc)[:200]}")
            logger.debug(f"任务{task_id}封面图下载失败，video：{video_id}，封面链接：{video["thumbnail_url"]}，错误信息：{str(exc)}")


    # Step 3: 更新状态 → recognizing
    _update_task_status(task_id, "recognizing", {"total": len(all_videos)})

    # Step 4: 推理
    run_mode = payload.get("run_mode", "batch")
    
    if run_mode == "batch":
        stats = _run_batch_inference(task_id, downloaded, payload)
    else:
        stats = _run_realtime_inference(task_id, downloaded, payload)

    # Step 5: 生成 results.json
    _generate_results_json(task_id)

    # Step 6: 从结果表统计真实总数并更新最终状态
    results_table = os.environ.get("TASK_RESULTS_TABLE", "TaskResults")
    all_results = query_all_pages(results_table, key_condition=Key("task_id").eq(task_id))
    total = len(all_results)
    success = sum(1 for r in all_results if r.get("status") == "success")
    failed = total - success
    stats = {"total": total, "success": success, "failed": failed}

    if failed > 0 and success > 0:
        _update_task_status(task_id, "partial_completed", stats)
    elif stats["failed"] > 0:
        _update_task_status(task_id, "failed", stats)
    else:
        _update_task_status(task_id, "completed", stats)


# ══════════════════════════════════════════════
# 重做工作流
# ══════════════════════════════════════════════

def run_retry_workflow(task_id: str, payload: dict) -> None:
    """重做工作流：跳过频道获取和图片下载，直接推理。"""
    failed_images = payload.get("failed_images", [])
    if not failed_images:
        raise ValueError("没有需要重做的图片")

    run_mode = payload.get("run_mode", "batch")
    if run_mode == "batch":
        _run_batch_inference(task_id, failed_images, payload)
    else:
        _run_realtime_inference(task_id, failed_images, payload)

    # 生成 results.json
    _generate_results_json(task_id)

    # 从结果表统计真实总数
    results_table = os.environ.get("TASK_RESULTS_TABLE", "TaskResults")
    all_results = query_all_pages(results_table, key_condition=Key("task_id").eq(task_id))
    total = len(all_results)
    success = sum(1 for r in all_results if r.get("status") == "success")
    failed = total - success
    stats = {"total": total, "success": success, "failed": failed}

    if failed > 0 and success > 0:
        _update_task_status(task_id, "partial_completed", stats)
    elif failed > 0:
        _update_task_status(task_id, "failed", stats)
    else:
        _update_task_status(task_id, "completed", stats)


# ══════════════════════════════════════════════
# 批量推理
# ══════════════════════════════════════════════

def _run_batch_inference(task_id: str, images: list[dict], payload: dict) -> dict:
    """批量推理：构建 JSONL → 提交任务 → 轮询等待 → 收集结果。"""
    bucket = os.environ["IMAGE_BUCKET"]
    model_id = payload.get("model_id") or os.environ.get("MODEL_ID", "apac.amazon.nova-lite-v1:0")
    role_arn = os.environ["ROLE_ARN"]
    region = os.environ.get("AWS_REGION_NAME", "ap-northeast-1")
    system_prompt = payload["system_prompt"]
    user_prompt = _assemble_user_prompt(payload)

    # 构建并上传 JSONL
    jsonl_content = _build_jsonl(images, task_id, bucket, system_prompt, user_prompt)
    jsonl_key = build_batch_input_path(task_id)
    upload_file(bucket, jsonl_key, jsonl_content)
    write_task_log(task_id, "model_invoke", "batch_input.jsonl", "success",
                   f"已上传 JSONL ({len(images)} 条记录)")

    # 提交 Bedrock 批量任务
    input_s3_uri = f"s3://{bucket}/tasks/{task_id}/input/"
    output_prefix = f"tasks/{task_id}/output/"
    output_s3_uri = f"s3://{bucket}/{output_prefix}"

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    job_name = f"task-{task_id[:8]}-{now_str}"

    bedrock = boto3.client("bedrock", region_name=region)
    response = bedrock.create_model_invocation_job(
        jobName=job_name, roleArn=role_arn, modelId=model_id,
        inputDataConfig={"s3InputDataConfig": {"s3InputFormat": "JSONL", "s3Uri": input_s3_uri}},
        outputDataConfig={"s3OutputDataConfig": {"s3Uri": output_s3_uri}},
    )
    batch_job_arn = response["jobArn"]
    write_task_log(task_id, "model_invoke", job_name, "success", f"批量任务已提交: {batch_job_arn}")

    # 轮询等待
    final_status = _poll_batch_job(task_id, batch_job_arn, bedrock, interval=60)
    if final_status == "Failed":
        raise RuntimeError(f"批量推理任务失败: {batch_job_arn}")

    # 收集结果
    return _collect_batch_results(task_id, images, output_prefix, bucket)


def _poll_batch_job(task_id: str, batch_job_arn: str, bedrock_client, interval: int = 60) -> str:
    """轮询 Bedrock 批量任务状态，每次写入 TaskLogs。"""
    while True:
        response = bedrock_client.get_model_invocation_job(jobIdentifier=batch_job_arn)
        raw_status = response.get("status", "Unknown")

        if raw_status in ("InProgress", "Validating", "Scheduled", "Submitted"):
            normalized = "InProgress"
        elif raw_status == "Completed":
            normalized = "Completed"
        else:
            normalized = "Failed"

        write_task_log(task_id, "model_invoke", batch_job_arn,
                       "success" if normalized != "Failed" else "failed",
                       f"批量任务状态: {raw_status} → {normalized}")

        if normalized in ("Completed", "Failed"):
            return normalized

        time.sleep(interval)


def _collect_batch_results(task_id: str, images: list[dict], output_prefix: str, bucket: str) -> dict:
    """从 S3 读取批量推理输出 JSONL，解析结果写入 TaskResults 表。"""
    results_table = os.environ["TASK_RESULTS_TABLE"]
    now = _now_iso()

    # recordId → video 映射
    video_map = {str(idx): img for idx, img in enumerate(images)}

    output_keys = list_objects(bucket, output_prefix)
    jsonl_keys = [k for k in output_keys if k.endswith(".jsonl.out")]

    success_count = 0
    failed_count = 0

    for jsonl_key in jsonl_keys:
        content = download_file(bucket, jsonl_key)
        for line in content.decode("utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            record_id = record.get("recordId", "")
            status = record.get("status", "failed")
            video = video_map.get(record_id, {})

            image_name = video.get("image_name", "")
            item_base = {
                "task_id": task_id, "image_name": image_name,
                "video_id": video.get("video_id", ""), "channel_id": video.get("channel_id", ""),
                "channel_name": video.get("channel_name", ""), "s3_key": video.get("s3_key", ""),
                "created_at": now, "updated_at": now,
            }

            if status == "success":
                result_json, review_result = _parse_model_output(record.get("modelOutput", {}))
                put_item(results_table, {**item_base, "status": "success",
                                         "result_json": result_json, "review_result": review_result,
                                         "error_message": ""})
                success_count += 1
            else:
                error_msg = record.get("error", "批量推理失败")
                put_item(results_table, {**item_base, "status": "failed",
                                         "result_json": {}, "review_result": "error",
                                         "error_message": error_msg})
                failed_count += 1
                write_task_log(task_id, "model_invoke", image_name, "failed", f"批量推理失败: {error_msg}")

    write_task_log(task_id, "model_invoke", "result_collector", "success",
                   f"批量结果收集完成: 成功={success_count}, 失败={failed_count}")
    return {"success": success_count, "failed": failed_count}


# ══════════════════════════════════════════════
# 实时推理
# ══════════════════════════════════════════════

def _run_realtime_inference(task_id: str, images: list[dict], payload: dict) -> dict:
    """实时推理：使用 asyncio + Semaphore 并发调用 Bedrock converse API。"""
    bucket = os.environ["IMAGE_BUCKET"]
    model_id = payload.get("model_id") or os.environ.get("MODEL_ID", "apac.amazon.nova-lite-v1:0")
    region = os.environ.get("AWS_REGION_NAME", "ap-northeast-1")
    try:
        from backend.app.routers.settings_routes import get_setting
        concurrency = get_setting("realtime_concurrency")
    except Exception:
        concurrency = int(os.environ.get("REALTIME_CONCURRENCY", "5"))
    system_prompt = payload["system_prompt"]
    
    user_prompt = _assemble_user_prompt(payload)

    bedrock_client = boto3.client("bedrock-runtime", region_name=region)
    results_table = os.environ["TASK_RESULTS_TABLE"]

    write_task_log(task_id, "model_invoke", "realtime", "success",
                   f"开始实时推理: {len(images)} 张图片, 并发数={concurrency}")

    async def _process():
        semaphore = asyncio.Semaphore(concurrency)
        
        tasks = [_invoke_single_rt(bedrock_client, model_id, img, bucket,
                                   system_prompt, user_prompt, task_id,
                                   results_table, semaphore) for img in images]
        
        return await asyncio.gather(*tasks)

    results = asyncio.run(_process())

    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    return {"success": success_count, "failed": failed_count}


async def _invoke_single_rt(
    bedrock_client, model_id: str, image: dict, bucket: str,
    system_prompt: str, user_prompt: str, task_id: str,
    results_table: str, semaphore: asyncio.Semaphore,
) -> dict:
    """对单张图片调用 Bedrock converse API，含重试。"""
    image_name = image.get("image_name", image.get("s3_key", "").rsplit("/", 1)[-1])
    s3_key = image["s3_key"]
    s3_uri = f"s3://{bucket}/{s3_key}"
    image_format = _detect_format(image_name)
    now = _now_iso()

    max_retries = 1
    initial_backoff = 2
    last_error = None


    async with semaphore:
        for attempt in range(max_retries):
            try:
                
                logger.debug(f"[{task_id}] {image_name} calling bedrock.converse, attempt {attempt+1}")
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: bedrock_client.converse(
                        modelId=model_id,
                        system=[{"text": system_prompt}],
                        messages=[{
                            "role": "user",
                            "content": [
                                {"image": {"format": image_format, "source": {"s3Location": {"uri": s3_uri}}}},
                                {"text": user_prompt},
                            ],
                        },
                        {
                            "role": "assistant",
                            "content": [{"text": " Here is the JSON response: ```json"}]
                        }],
                        inferenceConfig={"temperature": 0, "maxTokens": 2000, "topP": 0.9},
                    ),
                )
                
                logger.debug(f"[{task_id}] {image_name} bedrock response received: {response}")
                
                
                result_json = _parse_converse_response(response)
                review_result = result_json.get("review_result", "fail")


                put_item(results_table, {
                    "task_id": task_id, "image_name": image_name,
                    "video_id": image.get("video_id", ""), "channel_id": image.get("channel_id", ""),
                    "channel_name": image.get("channel_name", ""), "s3_key": s3_key,
                    "status": "success", "result_json": result_json,
                    "review_result": review_result, "error_message": "",
                    "created_at": now, "updated_at": now,
                })
                write_task_log(task_id, "model_invoke", image_name, "success",
                               f"推理成功: review_result={review_result}")
                logger.info(f"[{task_id}] {image_name} inference SUCCESS")
                return {"image_name": image_name, "status": "success"}

            except Exception as e:
                last_error = str(e)
                error_type = type(e).__name__
                logger.info(f"[{task_id}] {image_name} warning: "
                              f"尝试 {attempt+1} 失败 ({error_type}): {last_error}")
                
                if attempt < max_retries - 1:
                    backoff = initial_backoff * (2 ** attempt)
                    await asyncio.sleep(backoff)

    # 所有重试失败
    error_msg = f"重试 {max_retries} 次后仍失败: {last_error}"
    write_task_log(task_id, "model_invoke", image_name, "failed", error_msg)
    
    put_item(results_table, {
        "task_id": task_id, "image_name": image_name,
        "video_id": image.get("video_id", ""), "channel_id": image.get("channel_id", ""),
        "channel_name": image.get("channel_name", ""), "s3_key": s3_key,
        "status": "failed", "result_json": {}, "review_result": "error",
        "error_message": error_msg, "created_at": now, "updated_at": now,
    })
    write_task_log(task_id, "model_invoke", image_name, "failed", error_msg)
    return {"image_name": image_name, "status": "failed"}
