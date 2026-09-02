import copy
import unittest

from industry_chain_skills.dataset import DatasetService, _reject_duplicate_source_group
from industry_chain_skills.errors import ClientError


def record(
    url: str,
    category1: str,
    category2: str = "",
    company: str = "",
    source: str = "示例研究院",
    topic: str = "锡膏",
) -> dict[str, str]:
    return {
        "主题": topic,
        "信源主体": source,
        "分类1": category1,
        "分类2": category2,
        "分类3": "",
        "分类4": "",
        "公司": company,
        "信源URL": url,
        "备注": "",
    }


def group(group_id: str, records: list[dict[str, str]], order: int = 1) -> dict:
    return {
        "source_group_id": group_id,
        "order": order,
        "rows": [
            {
                "row_id": f"{group_id}_row_{index}",
                "order": index,
                "record": item,
            }
            for index, item in enumerate(records, start=1)
        ],
    }


class MemoryStore:
    def __init__(self, state: dict) -> None:
        self.state = state

    def mutate_dataset(self, runner_id: str, mutation):
        candidate = copy.deepcopy(self.state)
        result = mutation(candidate)
        self.state = candidate
        return result


class DuplicateSourceGroupTests(unittest.TestCase):
    def test_same_url_is_rejected_even_when_structure_differs(self) -> None:
        existing = group(
            "source_existing",
            [record("https://example.com/a", "上游", "锡锭", "甲公司")],
        )
        topic = {"source_groups": [existing]}
        incoming = [record("https://example.com/a", "中游", "锡膏", "乙公司")]

        with self.assertRaises(ClientError) as caught:
            _reject_duplicate_source_group(topic, incoming)

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_URL")
        self.assertEqual(
            caught.exception.details["existing_source_group_id"],
            "source_existing",
        )

    def test_same_business_content_same_original_source_is_rejected(self) -> None:
        existing = group(
            "source_existing",
            [
                record(
                    "https://askci.com/a",
                    "上游",
                    "锡锭",
                    "甲公司、乙公司",
                    source="中商情报网",
                ),
                record(
                    "https://askci.com/a",
                    "中游",
                    "锡膏",
                    "丙公司",
                    source="中商情报网",
                ),
            ],
        )
        topic = {"source_groups": [existing]}
        incoming = [
            record(
                "https://eastmoney.com/a",
                "中游",
                "锡膏",
                "丙公司",
                source="东方财富网（中商情报网）",
            ),
            record(
                "https://eastmoney.com/a",
                "上游",
                "锡锭",
                "乙公司、甲公司",
                source="东方财富网（中商情报网）",
            ),
        ]

        with self.assertRaises(ClientError) as caught:
            _reject_duplicate_source_group(topic, incoming)

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")

    def test_same_business_content_different_original_sources_is_allowed(self) -> None:
        existing = group(
            "source_existing",
            [
                record(
                    "https://huaon.com/a",
                    "上游",
                    "锡锭",
                    "甲公司",
                    source="华经情报网",
                ),
                record(
                    "https://huaon.com/a",
                    "中游",
                    "锡膏",
                    "乙公司",
                    source="华经情报网",
                ),
            ],
        )
        topic = {"source_groups": [existing]}
        incoming = [
            record(
                "https://chyxx.com/a",
                "中游",
                "锡膏",
                "乙公司",
                source="智研网",
            ),
            record(
                "https://chyxx.com/a",
                "上游",
                "锡锭",
                "甲公司",
                source="智研网",
            ),
        ]

        _reject_duplicate_source_group(topic, incoming)

    def test_same_structure_with_different_company_evidence_is_allowed(self) -> None:
        existing = group(
            "source_existing",
            [
                record("https://example.com/a", "上游", "锡锭", "甲公司"),
                record("https://example.com/a", "中游", "锡膏", "乙公司"),
            ],
        )
        topic = {"source_groups": [existing]}
        incoming = [
            record("https://example.com/b", "上游", "锡锭", "甲公司"),
            record("https://example.com/b", "中游", "锡膏", "乙公司、丙公司"),
        ]

        _reject_duplicate_source_group(topic, incoming)

    def test_source_group_insert_uses_duplicate_guard(self) -> None:
        existing_records = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [group("source_existing", existing_records)],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))
        payload = {
            "records": [
                record("https://example.com/b", "中游", "锡膏", "乙公司"),
                record("https://example.com/b", "上游", "锡锭", "甲公司"),
            ]
        }

        with self.assertRaises(ClientError) as caught:
            service.insert(
                "runner_test",
                "source_group",
                payload,
                "node_0001",
                None,
                None,
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")

    def test_source_group_patch_cannot_change_parent_topic(self) -> None:
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [
                        group(
                            "source_a",
                            [record("https://example.com/a", "中游", "锡膏", "甲公司")],
                        )
                    ],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))

        with self.assertRaises(ClientError) as caught:
            service.patch(
                "runner_test",
                "source_group",
                "source_a",
                {"主题": "机器人"},
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_TOPIC_MISMATCH")

    def test_source_group_replace_cannot_duplicate_another_group(self) -> None:
        records_a = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        records_b = [
            record("https://example.com/b", "上游", "锡锭", "甲公司"),
            record("https://example.com/b", "中游", "锡膏", "乙公司、丙公司"),
        ]
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [
                        group("source_a", records_a, 1),
                        group("source_b", records_b, 2),
                    ],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))

        with self.assertRaises(ClientError) as caught:
            service.replace(
                "runner_test",
                "source_group",
                "source_b",
                {"records": records_a},
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_URL")

    def test_source_group_replace_can_keep_its_own_content(self) -> None:
        records_a = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [group("source_a", records_a)],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))

        service.replace(
            "runner_test",
            "source_group",
            "source_a",
            {"records": records_a},
            None,
        )

    def test_row_insert_cannot_make_group_duplicate(self) -> None:
        records_a = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        records_b = [
            record("https://example.com/b", "上游", "锡锭", "甲公司"),
        ]
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [
                        group("source_a", records_a, 1),
                        group("source_b", records_b, 2),
                    ],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))

        with self.assertRaises(ClientError) as caught:
            service.insert(
                "runner_test",
                "row",
                record("https://example.com/b", "中游", "锡膏", "乙公司"),
                "source_b",
                None,
                None,
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")

    def test_row_patch_cannot_make_group_duplicate(self) -> None:
        records_a = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        records_b = [
            record("https://example.com/b", "上游", "锡锭", "甲公司"),
            record("https://example.com/b", "中游", "锡膏", "乙公司、丙公司"),
        ]
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [
                        group("source_a", records_a, 1),
                        group("source_b", records_b, 2),
                    ],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))
        target_row = state["topics"][0]["source_groups"][1]["rows"][1]["row_id"]

        with self.assertRaises(ClientError) as caught:
            service.patch(
                "runner_test",
                "row",
                target_row,
                {"公司": "乙公司"},
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")

    def test_row_replace_cannot_change_parent_topic(self) -> None:
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [
                        group(
                            "source_a",
                            [record("https://example.com/a", "中游", "锡膏", "甲公司")],
                        )
                    ],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))
        target_row = state["topics"][0]["source_groups"][0]["rows"][0]["row_id"]

        with self.assertRaises(ClientError) as caught:
            service.replace(
                "runner_test",
                "row",
                target_row,
                record(
                    "https://example.com/a",
                    "中游",
                    "锡膏",
                    "甲公司",
                    topic="机器人",
                ),
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_TOPIC_MISMATCH")

    def test_row_remove_cannot_make_group_duplicate(self) -> None:
        records_a = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        records_b = [
            record("https://example.com/b", "上游", "锡锭", "甲公司"),
            record("https://example.com/b", "中游", "锡膏", "乙公司"),
            record("https://example.com/b", "下游", "消费电子", "丙公司"),
        ]
        state = {
            "topics": [
                {
                    "node_id": "node_0001",
                    "主题": "锡膏",
                    "status": "completed",
                    "source_groups": [
                        group("source_a", records_a, 1),
                        group("source_b", records_b, 2),
                    ],
                }
            ]
        }
        service = DatasetService(MemoryStore(state))
        target_row = state["topics"][0]["source_groups"][1]["rows"][2]["row_id"]

        with self.assertRaises(ClientError) as caught:
            service.remove(
                "runner_test",
                "row",
                target_row,
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")

    def test_topic_insert_rejects_duplicate_groups_inside_payload(self) -> None:
        records_a = [
            record("https://example.com/a", "上游", "锡锭", "甲公司"),
            record("https://example.com/a", "中游", "锡膏", "乙公司"),
        ]
        records_b = [
            record("https://example.com/b", "中游", "锡膏", "乙公司"),
            record("https://example.com/b", "上游", "锡锭", "甲公司"),
        ]
        state = {"topics": []}
        service = DatasetService(MemoryStore(state))

        with self.assertRaises(ClientError) as caught:
            service.insert(
                "runner_test",
                "topic",
                {
                    "主题": "锡膏",
                    "path": ["锡膏"],
                    "aliases": [],
                    "source_groups": [
                        {"records": records_a},
                        {"records": records_b},
                    ],
                },
                None,
                None,
                None,
                None,
            )

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")


if __name__ == "__main__":
    unittest.main()
