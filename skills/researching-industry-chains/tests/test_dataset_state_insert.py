"""DatasetService 事务内来源组插入测试。"""

import unittest

from industry_chain_skills.dataset import DatasetService
from industry_chain_skills.errors import ClientError


STAMP = "2026-09-03T00:00:00+00:00"


def record(topic: str, source: str, url: str, company: str) -> dict[str, str]:
    """创建一行最小合法九字段记录。"""
    return {
        "主题": topic,
        "信源主体": source,
        "分类1": "上游",
        "分类2": "",
        "分类3": "",
        "分类4": "",
        "公司": company,
        "信源URL": url,
        "备注": "来源说明",
    }


def group(group_id: str, order: int, row: dict[str, str]) -> dict:
    """创建已有来源组。"""
    return {
        "source_group_id": group_id,
        "order": order,
        "created_at": STAMP,
        "updated_at": STAMP,
        "rows": [
            {
                "row_id": f"row_{group_id}",
                "order": 1,
                "created_at": STAMP,
                "updated_at": STAMP,
                "record": row,
            }
        ],
    }


def topic(node_id: str, name: str, groups: list[dict]) -> dict:
    """创建测试主题状态。"""
    return {
        "node_id": node_id,
        "主题": name,
        "path": [name],
        "aliases": [],
        "order": 1,
        "status": "in_progress",
        "last_error": None,
        "claim": None,
        "source_groups": groups,
    }


class DatasetStateInsertTests(unittest.TestCase):
    """验证 SourceService 可复用的事务内插入边界。"""

    def test_state_insert_appends_to_global_source_order(self) -> None:
        first = topic(
            "node_0001",
            "锡膏",
            [group("source_1", 1, record("锡膏", "来源一", "https://example.com/1", "甲公司"))],
        )
        second = topic(
            "node_0002",
            "焊料",
            [group("source_2", 2, record("焊料", "来源二", "https://example.com/2", "乙公司"))],
        )
        state = {"topics": [first, second]}
        service = DatasetService(store=None)  # type: ignore[arg-type]

        created = service.insert_source_group_in_state(
            state,
            first,
            {"records": [record("锡膏", "来源三", "https://example.com/3", "丙公司")]},
            STAMP,
        )

        self.assertIs(created, first["source_groups"][-1])
        self.assertEqual(3, created["order"])
        self.assertEqual(
            [1, 2, 3],
            sorted(
                item["order"]
                for current in state["topics"]
                for item in current["source_groups"]
            ),
        )

    def test_state_insert_reuses_duplicate_guard_without_mutating_state(self) -> None:
        existing = group(
            "source_1",
            1,
            record("锡膏", "来源一", "https://example.com/1", "甲公司"),
        )
        current = topic("node_0001", "锡膏", [existing])
        state = {"topics": [current]}
        service = DatasetService(store=None)  # type: ignore[arg-type]

        with self.assertRaises(ClientError) as error:
            service.insert_source_group_in_state(
                state,
                current,
                {"records": [record("锡膏", "其它转载", "https://example.com/1", "乙公司")]},
                STAMP,
            )

        self.assertEqual("SOURCE_GROUP_DUPLICATE_URL", error.exception.code)
        self.assertEqual([existing], current["source_groups"])


if __name__ == "__main__":
    unittest.main()
