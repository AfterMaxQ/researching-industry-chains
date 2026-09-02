"""九字段来源组校验和分级数据操作。"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit
from uuid import uuid4

from jsonschema import Draft202012Validator

from .errors import ClientError
from .runner import require_and_renew_claim
from .storage import RunnerStore


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "record.schema.json"
RECORD_VALIDATOR = Draft202012Validator(
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
)
SHARED_FIELDS = ("主题", "信源主体", "信源URL")
CATEGORY_FIELDS = ("分类1", "分类2", "分类3", "分类4")


def _record_path(record: dict[str, str]) -> tuple[str, ...]:
    """返回一行业务记录的完整分类路径。"""
    return tuple(record[field] for field in CATEGORY_FIELDS if record[field])


def _company_key(company: str) -> tuple[str, ...]:
    """把顿号分隔的企业集合转换为与顺序无关的确定性键。"""
    return tuple(sorted(item.strip() for item in company.split("、") if item.strip()))


def _source_content_key(
    records: list[dict[str, str]],
) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    """生成与 URL、备注、信源主体和行顺序无关的来源业务内容键。"""
    return tuple(
        sorted(
            (_record_path(record), _company_key(record["公司"]))
            for record in records
        )
    )


def _original_source_name(source: str) -> str | None:
    """从规范信源主体中提取原始研究主体。"""
    value = source.strip()
    if value.endswith("）"):
        start = value.rfind("（")
        if start >= 0:
            original = value[start + 1 : -1].strip()
            if original == "原始主体未明" or not original:
                return None
            return original
    return value or None


def _reject_duplicate_source_group(
    topic: dict,
    records: list[dict[str, str]],
    exclude_group_id: str | None = None,
) -> None:
    """拒绝同一主题中 URL 重复或同原始主体业务内容重复的来源组。"""
    incoming_url = records[0]["信源URL"]
    incoming_key = _source_content_key(records)
    incoming_original_source = _original_source_name(records[0]["信源主体"])

    for group in topic["source_groups"]:
        if group["source_group_id"] == exclude_group_id:
            continue

        existing_records = [row["record"] for row in group["rows"]]
        if not existing_records:
            continue

        existing_url = existing_records[0]["信源URL"]
        details = {
            "existing_source_group_id": group["source_group_id"],
            "existing_url": existing_url,
        }

        if existing_url == incoming_url:
            raise ClientError(
                "SOURCE_GROUP_DUPLICATE_URL",
                "同一主题中已存在相同信源URL的来源组",
                details,
            )

        existing_original_source = _original_source_name(
            existing_records[0]["信源主体"]
        )
        if (
            incoming_original_source
            and existing_original_source
            and incoming_original_source == existing_original_source
            and _source_content_key(existing_records) == incoming_key
        ):
            raise ClientError(
                "SOURCE_GROUP_DUPLICATE_CONTENT",
                "同一主题中已存在同原始主体且业务内容相同的来源组",
                details,
            )


def validate_source_payload(payload: dict) -> list[dict[str, str]]:
    """校验模型输出外壳、九字段记录和来源组业务约束。"""
    errors = sorted(
        RECORD_VALIDATOR.iter_errors(payload), key=lambda item: list(item.path)
    )
    if errors:
        raise ClientError("RECORD_SCHEMA_INVALID", errors[0].message)
    records = payload["records"]
    required_values = ("主题", "信源主体", "分类1", "信源URL")
    for index, record in enumerate(records):
        if any(not record[field] for field in required_values):
            raise ClientError(
                "RECORD_REQUIRED_VALUE_EMPTY", f"第{index + 1}行必填值为空"
            )
        if record["分类3"] and not record["分类2"]:
            raise ClientError("CATEGORY_GAP", f"第{index + 1}行分类层级断层")
        if record["分类4"] and not record["分类3"]:
            raise ClientError("CATEGORY_GAP", f"第{index + 1}行分类层级断层")
        parsed = urlsplit(record["信源URL"])
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ClientError("SOURCE_URL_INVALID", f"第{index + 1}行信源URL无效")
    if any(record["备注"] for record in records[1:]):
        raise ClientError("REMARK_NOT_FIRST_ROW", "只有来源组第一行可以填写备注")
    if not any(record["公司"] for record in records):
        raise ClientError("SOURCE_GROUP_HAS_NO_COMPANY", "来源组至少一行必须包含企业")
    for field in SHARED_FIELDS:
        if len({record[field] for record in records}) != 1:
            raise ClientError(
                "SOURCE_GROUP_METADATA_MISMATCH", f"来源组内{field}必须一致"
            )
    return records


def _validate_source_group_for_topic(
    topic: dict,
    payload: dict,
    exclude_group_id: str | None = None,
) -> list[dict[str, str]]:
    """统一校验来源组结构、父主题一致性和同主题重复。"""
    records = validate_source_payload(payload)
    if records[0]["主题"] != topic["主题"]:
        raise ClientError("SOURCE_TOPIC_MISMATCH", "来源组主题与目标主题不一致")
    _reject_duplicate_source_group(topic, records, exclude_group_id)
    return records


class DatasetService:
    """对主题、来源组和数据行执行原子数据操作。"""

    def __init__(
        self,
        store: RunnerStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        """返回带时区当前时间。"""
        now = self.clock()
        if now.tzinfo is None:
            raise ClientError("RUNNER_STATE_INVALID", "数据操作时钟必须包含时区")
        return now

    @staticmethod
    def _find_topic(state: dict, node_id: str) -> dict:
        """查找主题。"""
        for topic in state["topics"]:
            if topic["node_id"] == node_id:
                return topic
        raise ClientError("TOPIC_NOT_FOUND", "指定主题不存在", {"node_id": node_id})

    @staticmethod
    def _find_group(state: dict, group_id: str) -> tuple[dict, dict]:
        """查找来源组及其所属主题。"""
        for topic in state["topics"]:
            for group in topic["source_groups"]:
                if group["source_group_id"] == group_id:
                    return topic, group
        raise ClientError("SOURCE_GROUP_NOT_FOUND", "指定来源组不存在")

    @staticmethod
    def _find_row(state: dict, row_id: str) -> tuple[dict, dict, dict]:
        """查找数据行、来源组及其所属主题。"""
        for topic in state["topics"]:
            for group in topic["source_groups"]:
                for row in group["rows"]:
                    if row["row_id"] == row_id:
                        return topic, group, row
        raise ClientError("ROW_NOT_FOUND", "指定数据行不存在")

    @staticmethod
    def _authorize(topic: dict, claim_token: str | None, now: datetime) -> None:
        """处理中主题要求有效令牌，终态审核修改不要求令牌。"""
        if topic["status"] == "in_progress":
            require_and_renew_claim(topic, claim_token or "", now)

    @staticmethod
    def _validate_position(before_id: str | None, after_id: str | None) -> None:
        """检查插入位置参数互斥。"""
        if before_id and after_id:
            raise ClientError("POSITION_CONFLICT", "before_id 与 after_id 不能同时使用")

    @staticmethod
    def _insert_index(
        items: list[dict],
        id_field: str,
        before_id: str | None,
        after_id: str | None,
    ) -> int:
        """计算同级列表中的确定插入位置。"""
        if not before_id and not after_id:
            return len(items)
        target_id = before_id or after_id
        for index, item in enumerate(items):
            if item[id_field] == target_id:
                return index if before_id else index + 1
        raise ClientError("POSITION_TARGET_NOT_FOUND", "指定的同级位置目标不存在")

    @staticmethod
    def _renumber(items: list[dict]) -> None:
        """按当前顺序重新编号。"""
        for order, item in enumerate(items, start=1):
            item["order"] = order

    @staticmethod
    def _ordered_groups(state: dict) -> list[dict]:
        """返回按全局顺序排列的全部来源组。"""
        return sorted(
            [group for topic in state["topics"] for group in topic["source_groups"]],
            key=lambda group: group["order"],
        )

    @staticmethod
    def _rows_payload(group: dict) -> dict:
        """把来源组转换为可重新校验的 records 外壳。"""
        return {"records": [row["record"] for row in group["rows"]]}

    @staticmethod
    def _new_rows(records: list[dict[str, str]], timestamp: str) -> list[dict]:
        """为完整记录生成稳定行对象。"""
        return [
            {
                "row_id": f"row_{uuid4().hex[:12]}",
                "order": order,
                "created_at": timestamp,
                "updated_at": timestamp,
                "record": copy.deepcopy(record),
            }
            for order, record in enumerate(records, start=1)
        ]

    def _new_group(self, records: list[dict[str, str]], timestamp: str) -> dict:
        """为来源记录生成来源组对象。"""
        return {
            "source_group_id": f"source_{uuid4().hex[:12]}",
            "order": 0,
            "created_at": timestamp,
            "updated_at": timestamp,
            "rows": self._new_rows(records, timestamp),
        }

    def get(self, runner_id: str, scope: str, target_id: str) -> dict:
        """读取指定作用域对象的一致快照。"""
        state = self.store.read(runner_id)
        if scope == "topic":
            return copy.deepcopy(self._find_topic(state, target_id))
        if scope == "source_group":
            return copy.deepcopy(self._find_group(state, target_id)[1])
        if scope == "row":
            return copy.deepcopy(self._find_row(state, target_id)[2])
        raise ClientError("SCOPE_INVALID", "数据作用域无效")

    def insert(
        self,
        runner_id: str,
        scope: str,
        payload: dict,
        parent_id: str | None,
        before_id: str | None,
        after_id: str | None,
        claim_token: str | None,
    ) -> dict:
        """在主题、来源组或数据行作用域插入新对象。"""
        self._validate_position(before_id, after_id)
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            if scope == "topic":
                existing_groups = self._ordered_groups(state)
                topic = self._build_topic(payload, timestamp)
                index = self._insert_index(
                    state["topics"], "node_id", before_id, after_id
                )
                state["topics"].insert(index, topic)
                self._renumber(state["topics"])
                insertion = len(existing_groups)
                if before_id or after_id:
                    target_topic = self._find_topic(state, before_id or after_id or "")
                    target_groups = sorted(
                        target_topic["source_groups"], key=lambda group: group["order"]
                    )
                    if target_groups:
                        positions = [existing_groups.index(group) for group in target_groups]
                        insertion = min(positions) if before_id else max(positions) + 1
                existing_groups[insertion:insertion] = topic["source_groups"]
                self._renumber(existing_groups)
                result = topic
            elif scope == "source_group":
                if not parent_id:
                    raise ClientError("PARENT_ID_REQUIRED", "插入来源组必须指定主题")
                topic = self._find_topic(state, parent_id)
                self._authorize(topic, claim_token, now)
                if topic["status"] == "no_qualified_source":
                    raise ClientError("TOPIC_TERMINAL_DATA_CONFLICT", "无合格来源主题必须先重开")
                records = _validate_source_group_for_topic(topic, payload)
                index = self._insert_index(
                    topic["source_groups"], "source_group_id", before_id, after_id
                )
                group = self._new_group(records, timestamp)
                topic["source_groups"].insert(index, group)
                ordered = [
                    item for item in self._ordered_groups(state) if item is not group
                ]
                if before_id or after_id:
                    target = next(
                        (
                            item
                            for item in ordered
                            if item["source_group_id"] == (before_id or after_id)
                        ),
                        None,
                    )
                    if target is None or target not in topic["source_groups"]:
                        raise ClientError(
                            "POSITION_TARGET_NOT_FOUND", "位置目标必须属于同一主题"
                        )
                    target_index = ordered.index(target)
                    ordered.insert(target_index if before_id else target_index + 1, group)
                else:
                    ordered.append(group)
                self._renumber(ordered)
                result = group
            elif scope == "row":
                if not parent_id:
                    raise ClientError("PARENT_ID_REQUIRED", "插入数据行必须指定来源组")
                topic, group = self._find_group(state, parent_id)
                self._authorize(topic, claim_token, now)
                record = payload.get("record") if set(payload) == {"record"} else payload
                if not isinstance(record, dict):
                    raise ClientError("RECORD_SCHEMA_INVALID", "数据行必须是九字段对象")
                index = self._insert_index(group["rows"], "row_id", before_id, after_id)
                row = self._new_rows([record], timestamp)[0]
                group["rows"].insert(index, row)
                self._renumber(group["rows"])
                _validate_source_group_for_topic(
                    topic,
                    self._rows_payload(group),
                    group["source_group_id"],
                )
                group["updated_at"] = timestamp
                result = row
            else:
                raise ClientError("SCOPE_INVALID", "数据作用域无效")
            state["updated_at"] = timestamp
            return copy.deepcopy(result)

        return self.store.mutate_dataset(runner_id, mutation)

    def _build_topic(
        self,
        payload: dict,
        timestamp: str,
        node_id: str | None = None,
    ) -> dict:
        """从主题载荷构造主题状态对象。"""
        allowed = {"主题", "path", "aliases", "source_groups"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ClientError("TOPIC_PAYLOAD_INVALID", "主题载荷包含无效字段")
        topic_name = payload.get("主题")
        path = payload.get("path", [])
        aliases = payload.get("aliases", [])
        if not isinstance(topic_name, str) or not topic_name:
            raise ClientError("TOPIC_PAYLOAD_INVALID", "主题名称不能为空")
        if not isinstance(path, list) or any(
            not isinstance(value, str) for value in path
        ):
            raise ClientError("TOPIC_PAYLOAD_INVALID", "主题 path 必须是字符串数组")
        if not isinstance(aliases, list) or any(
            not isinstance(value, str) for value in aliases
        ):
            raise ClientError("TOPIC_PAYLOAD_INVALID", "主题 aliases 必须是字符串数组")
        topic = {
            "node_id": node_id or f"node_{uuid4().hex[:12]}",
            "主题": topic_name,
            "path": copy.deepcopy(path),
            "aliases": copy.deepcopy(aliases),
            "order": 0,
            "status": "pending",
            "last_error": None,
            "claim": None,
            "source_groups": [],
        }
        for group_payload in payload.get("source_groups", []):
            records = _validate_source_group_for_topic(topic, group_payload)
            topic["source_groups"].append(self._new_group(records, timestamp))
        return topic

    def patch(
        self,
        runner_id: str,
        scope: str,
        target_id: str,
        changes: dict,
        claim_token: str | None,
    ) -> dict:
        """修改指定字段并保留目标 ID 和位置。"""
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            if not isinstance(changes, dict) or not changes:
                raise ClientError("PATCH_INVALID", "Patch 必须包含修改字段")
            if scope == "topic":
                topic = self._find_topic(state, target_id)
                self._authorize(topic, claim_token, now)
                if set(changes) - {"主题", "path", "aliases"}:
                    raise ClientError("PATCH_FIELD_INVALID", "主题 Patch 包含无效字段")
                new_name = changes.get("主题", topic["主题"])
                new_path = changes.get("path", topic["path"])
                new_aliases = changes.get("aliases", topic["aliases"])
                if not isinstance(new_name, str) or not new_name:
                    raise ClientError("TOPIC_PAYLOAD_INVALID", "主题名称不能为空")
                if not isinstance(new_path, list) or any(
                    not isinstance(value, str) for value in new_path
                ):
                    raise ClientError("TOPIC_PAYLOAD_INVALID", "主题 path 必须是字符串数组")
                if not isinstance(new_aliases, list) or any(
                    not isinstance(value, str) for value in new_aliases
                ):
                    raise ClientError(
                        "TOPIC_PAYLOAD_INVALID", "主题 aliases 必须是字符串数组"
                    )
                topic["主题"] = new_name
                topic["path"] = copy.deepcopy(new_path)
                topic["aliases"] = copy.deepcopy(new_aliases)
                for group in topic["source_groups"]:
                    for row in group["rows"]:
                        row["record"]["主题"] = new_name
                        row["updated_at"] = timestamp
                    group["updated_at"] = timestamp
                result = topic
            elif scope == "source_group":
                topic, group = self._find_group(state, target_id)
                self._authorize(topic, claim_token, now)
                if set(changes) - {"主题", "信源主体", "信源URL", "备注"}:
                    raise ClientError(
                        "PATCH_FIELD_INVALID", "来源组 Patch 包含无效字段"
                    )
                for row_index, row in enumerate(group["rows"]):
                    for field in ("主题", "信源主体", "信源URL"):
                        if field in changes:
                            row["record"][field] = changes[field]
                    if "备注" in changes:
                        row["record"]["备注"] = (
                            changes["备注"] if row_index == 0 else ""
                        )
                    row["updated_at"] = timestamp
                _validate_source_group_for_topic(
                    topic,
                    self._rows_payload(group),
                    group["source_group_id"],
                )
                group["updated_at"] = timestamp
                result = group
            elif scope == "row":
                topic, group, row = self._find_row(state, target_id)
                self._authorize(topic, claim_token, now)
                if set(changes) - set(row["record"]):
                    raise ClientError("PATCH_FIELD_INVALID", "数据行 Patch 包含无效字段")
                row["record"].update(changes)
                _validate_source_group_for_topic(
                    topic,
                    self._rows_payload(group),
                    group["source_group_id"],
                )
                row["updated_at"] = timestamp
                group["updated_at"] = timestamp
                result = row
            else:
                raise ClientError("SCOPE_INVALID", "数据作用域无效")
            state["updated_at"] = timestamp
            return copy.deepcopy(result)

        return self.store.mutate_dataset(runner_id, mutation)

    def replace(
        self,
        runner_id: str,
        scope: str,
        target_id: str,
        payload: dict,
        claim_token: str | None,
    ) -> dict:
        """原子替换目标内容，并保留目标 ID 和位置。"""
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            if scope == "row":
                topic, group, row = self._find_row(state, target_id)
                self._authorize(topic, claim_token, now)
                record = payload.get("record") if set(payload) == {"record"} else payload
                old_created = row["created_at"]
                row["record"] = copy.deepcopy(record)
                row["created_at"] = old_created
                row["updated_at"] = timestamp
                _validate_source_group_for_topic(
                    topic,
                    self._rows_payload(group),
                    group["source_group_id"],
                )
                group["updated_at"] = timestamp
                result = row
            elif scope == "source_group":
                topic, group = self._find_group(state, target_id)
                self._authorize(topic, claim_token, now)
                records = _validate_source_group_for_topic(
                    topic,
                    payload,
                    group["source_group_id"],
                )
                group["rows"] = self._new_rows(records, timestamp)
                group["updated_at"] = timestamp
                result = group
            elif scope == "topic":
                topic = self._find_topic(state, target_id)
                self._authorize(topic, claim_token, now)
                replacement = self._build_topic(payload, timestamp, node_id=target_id)
                replacement["order"] = topic["order"]
                replacement["status"] = topic["status"]
                replacement["last_error"] = topic["last_error"]
                replacement["claim"] = topic["claim"]
                if replacement["status"] == "completed" and not replacement["source_groups"]:
                    raise ClientError(
                        "TOPIC_TERMINAL_DATA_CONFLICT",
                        "完成主题必须保留至少一个来源组",
                    )
                if (
                    replacement["status"] == "no_qualified_source"
                    and replacement["source_groups"]
                ):
                    raise ClientError(
                        "TOPIC_TERMINAL_DATA_CONFLICT",
                        "无合格来源主题不能包含来源组",
                    )
                old_orders = [group["order"] for group in topic["source_groups"]]
                start_order = (
                    min(old_orders)
                    if old_orders
                    else len(self._ordered_groups(state)) + 1
                )
                index = state["topics"].index(topic)
                state["topics"][index] = replacement
                other_groups = [
                    group
                    for current in state["topics"]
                    if current is not replacement
                    for group in current["source_groups"]
                ]
                ordered = sorted(other_groups, key=lambda group: group["order"])
                insertion = min(start_order - 1, len(ordered))
                ordered[insertion:insertion] = replacement["source_groups"]
                self._renumber(ordered)
                result = replacement
            else:
                raise ClientError("SCOPE_INVALID", "数据作用域无效")
            state["updated_at"] = timestamp
            return copy.deepcopy(result)

        return self.store.mutate_dataset(runner_id, mutation)

    def remove(
        self,
        runner_id: str,
        scope: str,
        target_id: str,
        claim_token: str | None,
    ) -> dict:
        """删除目标并保持剩余对象相对顺序。"""
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            if scope == "row":
                topic, group, row = self._find_row(state, target_id)
                self._authorize(topic, claim_token, now)
                if len(group["rows"]) == 1:
                    raise ClientError(
                        "REMOVE_SOURCE_GROUP_REQUIRED",
                        "删除最后一行时应删除整个来源组",
                    )
                group["rows"].remove(row)
                self._renumber(group["rows"])
                _validate_source_group_for_topic(
                    topic,
                    self._rows_payload(group),
                    group["source_group_id"],
                )
                group["updated_at"] = timestamp
                result = {"removed_id": target_id, "scope": scope}
            elif scope == "source_group":
                topic, group = self._find_group(state, target_id)
                self._authorize(topic, claim_token, now)
                if topic["status"] == "completed" and len(topic["source_groups"]) == 1:
                    raise ClientError(
                        "TOPIC_TERMINAL_DATA_CONFLICT",
                        "完成主题必须保留至少一个来源组",
                    )
                topic["source_groups"].remove(group)
                self._renumber(self._ordered_groups(state))
                result = {"removed_id": target_id, "scope": scope}
            elif scope == "topic":
                topic = self._find_topic(state, target_id)
                self._authorize(topic, claim_token, now)
                state["topics"].remove(topic)
                self._renumber(state["topics"])
                self._renumber(self._ordered_groups(state))
                result = {"removed_id": target_id, "scope": scope}
            else:
                raise ClientError("SCOPE_INVALID", "数据作用域无效")
            state["updated_at"] = timestamp
            return result

        return self.store.mutate_dataset(runner_id, mutation)
