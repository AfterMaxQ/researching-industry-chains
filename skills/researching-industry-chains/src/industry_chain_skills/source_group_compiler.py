"""SourceResult 到来源组写入前的纯业务转换辅助。"""

from __future__ import annotations

from copy import deepcopy

from .errors import ClientError
from .source_result import compile_tree_records


def build_source_group_payload(source_result: dict, topic: str) -> dict:
    """把 SourceResult 编译为 DatasetService 可消费的 records payload。

    该函数不负责持久化、不负责生成 ID、不负责修改 Runner 状态。
    """
    if source_result.get("outcome") != "accept":
        raise ClientError(
            "SOURCE_RESULT_NOT_ACCEPTED",
            "只有 accept 类型 SourceResult 可以直接生成正式来源组",
        )

    source = source_result.get("source") or {}
    description = source_result.get("description", "")

    records = compile_tree_records(
        source_result.get("chain", []),
        topic=topic,
        source_name=source.get("name", ""),
        source_url=source.get("url", ""),
        remark=description,
    )

    return {"records": deepcopy(records)}
