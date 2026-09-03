"""SourceResult 协议测试。"""

import unittest

from industry_chain_skills.errors import ClientError
from industry_chain_skills.source_result import (
    compile_tree_records,
    iter_uncertainties,
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

    def test_company_uncertainty_must_reference_company_on_its_node(self) -> None:
        payload = {
            "outcome": "review",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "企业归属仍需确认。",
            "chain": [
                {
                    "name": "锡粉",
                    "companies": ["甲公司"],
                    "uncertainties": [
                        {"company": "乙公司", "message": "归属不清"}
                    ],
                }
            ],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "UNCERTAINTY_COMPANY_NOT_IN_NODE")

    def test_source_result_requires_a_nonempty_description(self) -> None:
        payload = {
            "outcome": "accept",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "  ",
            "chain": [{"name": "锡粉", "companies": ["甲公司"]}],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "SOURCE_RESULT_DESCRIPTION_INVALID")

    def test_accept_requires_at_least_one_company(self) -> None:
        payload = {
            "outcome": "accept",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "来源完整展示产业链。",
            "chain": [{"name": "上游", "children": [{"name": "锡粉"}]}],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "SOURCE_RESULT_ACCEPT_HAS_NO_COMPANY")

    def test_accept_rejects_an_empty_uncertainties_field(self) -> None:
        payload = {
            "outcome": "accept",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "来源完整展示产业链。",
            "chain": [{"name": "锡粉", "companies": ["甲公司"]}],
            "uncertainties": [],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "SOURCE_RESULT_FIELD_INVALID")

    def test_tree_rejects_duplicate_sibling_names(self) -> None:
        payload = {
            "outcome": "accept",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "来源完整展示产业链。",
            "chain": [
                {"name": "锡粉", "companies": ["甲公司"]},
                {"name": "锡粉", "companies": ["乙公司"]},
            ],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "TREE_DUPLICATE_SIBLING")

    def test_review_rejects_evidence_without_locator_and_description(self) -> None:
        payload = {
            "outcome": "review",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "企业归属仍需确认。",
            "chain": [],
            "uncertainties": [{"message": "需要核对", "evidence": [{"locator": "第 17 页"}]}],
        }
        with self.assertRaises(ClientError) as error:
            validate_source_result(payload)
        self.assertEqual(error.exception.code, "UNCERTAINTY_EVIDENCE_INVALID")

    def test_review_iterates_source_and_company_occurrence_uncertainties(self) -> None:
        payload = {
            "outcome": "review",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "仍有两个位置需要核对。",
            "chain": [
                {
                    "name": "上游",
                    "children": [
                        {
                            "name": "锡粉",
                            "companies": ["甲公司"],
                            "uncertainties": [
                                {
                                    "company": "甲公司",
                                    "message": "归属连接不清楚。",
                                    "evidence": [
                                        {
                                            "locator": "PDF 第 17 页图 5",
                                            "description": "企业在图中出现。",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
            "uncertainties": [{"message": "无法确认是否遍历全部交互状态。"}],
        }
        validated = validate_source_result(payload)
        locations = list(iter_uncertainties(validated))
        self.assertEqual(((), None), locations[0][:2])
        self.assertEqual((("上游", "锡粉"), "甲公司"), locations[1][:2])

    def test_tree_compiler_emits_every_node_in_parent_first_order(self) -> None:
        rows = compile_tree_records(
            "锡膏",
            {"name": "研究院", "url": "https://example.com"},
            "来源说明",
            [{"name": "材料", "children": [{"name": "锡粉", "companies": ["A公司"]}]}],
        )
        self.assertEqual(2, len(rows))
        self.assertEqual("材料", rows[0]["分类1"])
        self.assertEqual("", rows[0]["分类2"])
        self.assertEqual("", rows[0]["公司"])
        self.assertEqual("来源说明", rows[0]["备注"])
        self.assertEqual("材料", rows[1]["分类1"])
        self.assertEqual("锡粉", rows[1]["分类2"])
        self.assertEqual("A公司", rows[1]["公司"])
        self.assertEqual("", rows[1]["备注"])

    def test_tree_compiler_rejects_a_fifth_category_level(self) -> None:
        chain = [{"name": "一", "children": [{"name": "二", "children": [{"name": "三", "children": [{"name": "四", "children": [{"name": "五", "companies": ["甲公司"]}]}]}]}]}]
        with self.assertRaises(ClientError) as error:
            compile_tree_records(
                "锡膏",
                {"name": "研究院", "url": "https://example.com"},
                "来源说明",
                chain,
            )
        self.assertEqual("TREE_DEPTH_EXCEEDED", error.exception.code)


if __name__ == "__main__":
    unittest.main()
