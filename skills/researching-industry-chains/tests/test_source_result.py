"""SourceResult 协议测试。"""

import unittest

from industry_chain_skills.errors import ClientError
from industry_chain_skills.source_result import (
    compile_tree_records,
    validate_source_result,
)


class SourceResultTests(unittest.TestCase):
    def test_accept_rejects_uncertainty(self) -> None:
        payload = {
            "outcome": "accept",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "说明",
            "chain": [{"name": "上游", "uncertainties": [{"message": "不确定"}]}],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "SOURCE_RESULT_ACCEPT_HAS_UNCERTAINTY")

    def test_review_requires_uncertainty(self) -> None:
        payload = {
            "outcome": "review",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "说明",
            "chain": [{"name": "上游"}],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "SOURCE_RESULT_REVIEW_HAS_NO_UNCERTAINTY")

    def test_tree_compiles_to_records(self) -> None:
        rows = compile_tree_records(
            "锡膏",
            {"name": "研究院", "url": "https://example.com"},
            "来源说明",
            [{"name": "材料", "children": [{"name": "锡粉", "companies": ["A公司"]}]}],
        )
        self.assertEqual(rows[0]["分类1"], "材料")
        self.assertEqual(rows[0]["分类2"], "锡粉")
        self.assertEqual(rows[0]["公司"], "A公司")


if __name__ == "__main__":
    unittest.main()
