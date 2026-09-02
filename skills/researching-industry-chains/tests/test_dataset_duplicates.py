import unittest

from industry_chain_skills.dataset import DatasetService, _reject_duplicate_source_group
from industry_chain_skills.errors import ClientError


def record(
    url: str,
    category1: str,
    category2: str = "",
    company: str = "",
    source: str = "示例研究院",
) -> dict[str, str]:
    return {
        "主题": "锡膏",
        "信源主体": source,
        "分类1": category1,
        "分类2": category2,
        "分类3": "",
        "分类4": "",
        "公司": company,
        "信源URL": url,
        "备注": "",
    }


def group(group_id: str, records: list[dict[str, str]]) -> dict:
    return {
        "source_group_id": group_id,
        "rows": [{"record": item} for item in records],
    }


class MemoryStore:
    def __init__(self, state: dict) -> None:
        self.state = state

    def mutate_dataset(self, runner_id: str, mutation):
        return mutation(self.state)


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

    def test_same_business_content_is_rejected_across_different_urls(self) -> None:
        existing = group(
            "source_existing",
            [
                record("https://example.com/a", "上游", "锡锭", "甲公司、乙公司"),
                record("https://example.com/a", "中游", "锡膏", "丙公司"),
            ],
        )
        topic = {"source_groups": [existing]}
        incoming = [
            record(
                "https://mirror.example.com/a",
                "中游",
                "锡膏",
                "丙公司",
                source="转载平台",
            ),
            record(
                "https://mirror.example.com/a",
                "上游",
                "锡锭",
                "乙公司、甲公司",
                source="转载平台",
            ),
        ]

        with self.assertRaises(ClientError) as caught:
            _reject_duplicate_source_group(topic, incoming)

        self.assertEqual(caught.exception.code, "SOURCE_GROUP_DUPLICATE_CONTENT")

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
                record("https://mirror.example.com/a", "中游", "锡膏", "乙公司"),
                record("https://mirror.example.com/a", "上游", "锡锭", "甲公司"),
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

        self.assertEqual(
            caught.exception.code,
            "SOURCE_GROUP_DUPLICATE_CONTENT",
        )


if __name__ == "__main__":
    unittest.main()
