"""DynamoDB CRUD 工具函数，封装指数退避重试和分页查询。"""

import os
import time
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


# 重试配置
MAX_RETRIES = 3
INITIAL_DELAY = 0.5  # 秒


def _get_resource():
    """获取 DynamoDB resource（便于测试时替换）。"""
    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    return boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint_url)


def _get_table(table_name: str):
    """获取 DynamoDB Table 对象。"""
    return _get_resource().Table(table_name)


def _retry_with_backoff(func, max_retries=MAX_RETRIES, initial_delay=INITIAL_DELAY):
    """指数退避重试装饰逻辑。

    最多重试 max_retries 次，初始延迟 initial_delay 秒，每次翻倍。
    仅对 DynamoDB 可重试异常进行重试（ProvisionedThroughputExceededException、
    ThrottlingException、InternalServerError）。
    """
    retryable_codes = {
        "ProvisionedThroughputExceededException",
        "ThrottlingException",
        "InternalServerError",
    }
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code not in retryable_codes:
                raise
            last_exception = e
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                time.sleep(delay)
    raise last_exception


def put_item(table_name: str, item: dict, condition_expression=None, **kwargs) -> dict:
    """写入单条记录。

    Args:
        table_name: DynamoDB 表名
        item: 要写入的记录
        condition_expression: 可选的条件表达式（如防止覆盖）
        **kwargs: 传递给 Table.put_item 的额外参数

    Returns:
        DynamoDB put_item 响应
    """
    table = _get_table(table_name)
    params = {"Item": item, **kwargs}
    if condition_expression is not None:
        params["ConditionExpression"] = condition_expression
    return _retry_with_backoff(lambda: table.put_item(**params))


def get_item(table_name: str, key: dict, consistent_read: bool = False) -> dict | None:
    """读取单条记录。

    Args:
        table_name: DynamoDB 表名
        key: 主键字典，如 {"task_id": "xxx"}
        consistent_read: 是否强一致性读取

    Returns:
        记录字典，不存在时返回 None
    """
    table = _get_table(table_name)
    response = _retry_with_backoff(
        lambda: table.get_item(Key=key, ConsistentRead=consistent_read)
    )
    return response.get("Item")


def query(
    table_name: str,
    key_condition,
    index_name: str | None = None,
    filter_expression=None,
    scan_forward: bool = True,
    limit: int | None = None,
    exclusive_start_key: dict | None = None,
    **kwargs,
) -> dict:
    """查询记录。

    Args:
        table_name: DynamoDB 表名
        key_condition: 键条件表达式（boto3 Key condition）
        index_name: GSI 名称（可选）
        filter_expression: 过滤表达式（可选）
        scan_forward: True=升序，False=降序
        limit: 单次返回最大数量
        exclusive_start_key: 分页起始键
        **kwargs: 传递给 Table.query 的额外参数

    Returns:
        包含 Items 和可选 LastEvaluatedKey 的字典
    """
    table = _get_table(table_name)
    params = {
        "KeyConditionExpression": key_condition,
        "ScanIndexForward": scan_forward,
        **kwargs,
    }
    if index_name:
        params["IndexName"] = index_name
    if filter_expression is not None:
        params["FilterExpression"] = filter_expression
    if limit is not None:
        params["Limit"] = limit
    if exclusive_start_key is not None:
        params["ExclusiveStartKey"] = exclusive_start_key

    response = _retry_with_backoff(lambda: table.query(**params))
    result = {"Items": response.get("Items", [])}
    if "LastEvaluatedKey" in response:
        result["LastEvaluatedKey"] = response["LastEvaluatedKey"]
    return result


def update_item(
    table_name: str,
    key: dict,
    update_expression: str,
    expression_values: dict | None = None,
    expression_names: dict | None = None,
    condition_expression=None,
    return_values: str = "ALL_NEW",
    **kwargs,
) -> dict:
    """更新单条记录。

    Args:
        table_name: DynamoDB 表名
        key: 主键字典
        update_expression: 更新表达式，如 "SET #n = :val"
        expression_values: 表达式值映射
        expression_names: 表达式名称映射（用于保留字）
        condition_expression: 可选的条件表达式
        return_values: 返回值模式，默认 ALL_NEW
        **kwargs: 传递给 Table.update_item 的额外参数

    Returns:
        更新后的记录（Attributes）
    """
    table = _get_table(table_name)
    params = {
        "Key": key,
        "UpdateExpression": update_expression,
        "ReturnValues": return_values,
        **kwargs,
    }
    if expression_values:
        params["ExpressionAttributeValues"] = expression_values
    if expression_names:
        params["ExpressionAttributeNames"] = expression_names
    if condition_expression is not None:
        params["ConditionExpression"] = condition_expression

    response = _retry_with_backoff(lambda: table.update_item(**params))
    return response.get("Attributes", {})


def delete_item(table_name: str, key: dict, condition_expression=None, **kwargs) -> dict:
    """删除单条记录。

    Args:
        table_name: DynamoDB 表名
        key: 主键字典
        condition_expression: 可选的条件表达式
        **kwargs: 传递给 Table.delete_item 的额外参数

    Returns:
        DynamoDB delete_item 响应
    """
    table = _get_table(table_name)
    params = {"Key": key, **kwargs}
    if condition_expression is not None:
        params["ConditionExpression"] = condition_expression
    return _retry_with_backoff(lambda: table.delete_item(**params))


def query_all_pages(
    table_name: str,
    key_condition,
    index_name: str | None = None,
    filter_expression=None,
    scan_forward: bool = True,
    **kwargs,
) -> list[dict]:
    """分页查询辅助函数，自动遍历所有分页并返回全部记录。

    Args:
        table_name: DynamoDB 表名
        key_condition: 键条件表达式
        index_name: GSI 名称（可选）
        filter_expression: 过滤表达式（可选）
        scan_forward: True=升序，False=降序
        **kwargs: 传递给 query 的额外参数

    Returns:
        所有记录的列表
    """
    all_items = []
    exclusive_start_key = None

    while True:
        result = query(
            table_name=table_name,
            key_condition=key_condition,
            index_name=index_name,
            filter_expression=filter_expression,
            scan_forward=scan_forward,
            exclusive_start_key=exclusive_start_key,
            **kwargs,
        )
        all_items.extend(result["Items"])
        exclusive_start_key = result.get("LastEvaluatedKey")
        if exclusive_start_key is None:
            break

    return all_items


def scan_all(table_name: str, filter_expression=None, **kwargs) -> list[dict]:
    """全表扫描，自动遍历所有分页。

    仅用于数据量较小的表（如 PromptTemplates）。

    Args:
        table_name: DynamoDB 表名
        filter_expression: 过滤表达式（可选）
        **kwargs: 传递给 Table.scan 的额外参数

    Returns:
        所有记录的列表
    """
    table = _get_table(table_name)
    all_items = []
    params = {**kwargs}
    if filter_expression is not None:
        params["FilterExpression"] = filter_expression

    while True:
        response = _retry_with_backoff(lambda: table.scan(**params))
        all_items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if last_key is None:
            break
        params["ExclusiveStartKey"] = last_key

    return all_items
