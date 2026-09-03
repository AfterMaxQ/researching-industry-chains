from industry_chain_skills.source_group_compiler import build_source_group_payload
from industry_chain_skills.errors import ClientError


def test_accept_source_result_compiles_to_records():
    payload = build_source_group_payload(
        {
            "outcome": "accept",
            "source": {"name": "研究院", "url": "https://example.com"},
            "description": "展示上下游结构。",
            "chain": [
                {
                    "name": "上游",
                    "children": [
                        {
                            "name": "锡粉",
                            "companies": ["A公司", "B公司"],
                        }
                    ],
                }
            ],
        },
        "锡膏",
    )

    assert payload["records"][0]["主题"] == "锡膏"
    assert payload["records"][0]["信源主体"] == "研究院"
    assert payload["records"][0]["备注"] == "展示上下游结构。"
    assert payload["records"][1]["公司"] == "A公司、B公司"


def test_review_cannot_be_compiled_as_formal_group():
    try:
        build_source_group_payload(
            {
                "outcome": "review",
                "source": {"name": "研究院", "url": "https://example.com"},
                "chain": [],
            },
            "锡膏",
        )
    except ClientError as exc:
        assert exc.code == "SOURCE_RESULT_NOT_ACCEPTED"
    else:
        raise AssertionError("review should not compile to formal source group")
