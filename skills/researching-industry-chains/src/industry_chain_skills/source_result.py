"""Agent SourceResult 协议、Tree 校验和九字段编译。"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterator
from urllib.parse import urlsplit

from .errors import ClientError


CATEGORY_FIELDS = ("分类1", "分类2", "分类3", "分类4")
_SOURCE_FIELDS = {"name", "url"}
_NODE_FIELDS = {"name", "companies", "children", "uncertainties"}
_UNCERTAINTY_FIELDS = {"message", "company", "evidence"}
_EVIDENCE_FIELDS = {"locator", "description"}


def _require(condition: bool, code: str, message: str) -> None:
    """在条件不满足时抛出稳定业务错误。"""
    if not condition:
        raise ClientError(code, message)


def _is_nonempty_string(value: object) -> bool:
    """判断值是否为去除空白后仍非空的字符串。"""
    return isinstance(value, str) and bool(value.strip())


def _validate_source(source: object) -> None:
    """校验来源主体和 URL。"""
    _require(
        isinstance(source, dict) and set(source) == _SOURCE_FIELDS,
        "SOURCE_RESULT_SOURCE_INVALID",
        "source 必须且只能包含 name 和 url",
    )
    _require(
        _is_nonempty_string(source["name"]),
        "SOURCE_RESULT_SOURCE_INVALID",
        "source.name 不能为空",
    )
    _require(
        _is_nonempty_string(source["url"]),
        "SOURCE_RESULT_SOURCE_INVALID",
        "source.url 不能为空",
    )
    parsed = urlsplit(source["url"].strip())
    _require(
        parsed.scheme in {"http", "https"} and bool(parsed.netloc),
        "SOURCE_RESULT_SOURCE_INVALID",
        "source.url 必须是有效 HTTP(S) URL",
    )


def _validate_evidence(evidence: object) -> None:
    """校验可选的人工定位依据。"""
    _require(
        isinstance(evidence, list),
        "UNCERTAINTY_EVIDENCE_INVALID",
        "uncertainty.evidence 必须是数组",
    )
    for item in evidence:
        _require(
            isinstance(item, dict) and set(item) == _EVIDENCE_FIELDS,
            "UNCERTAINTY_EVIDENCE_INVALID",
            "evidence 必须且只能包含 locator 和 description",
        )
        _require(
            _is_nonempty_string(item["locator"])
            and _is_nonempty_string(item["description"]),
            "UNCERTAINTY_EVIDENCE_INVALID",
            "evidence 的 locator 和 description 不能为空",
        )


def _validate_uncertainty(
    uncertainty: object,
    companies: list[object] | None,
) -> None:
    """校验来源级或节点级不确定性。"""
    _require(
        isinstance(uncertainty, dict)
        and set(uncertainty).issubset(_UNCERTAINTY_FIELDS)
        and "message" in uncertainty,
        "UNCERTAINTY_INVALID",
        "uncertainty 只能包含 message、company 和 evidence，且必须有 message",
    )
    _require(
        _is_nonempty_string(uncertainty["message"]),
        "UNCERTAINTY_INVALID",
        "uncertainty.message 不能为空",
    )
    if "company" in uncertainty:
        _require(
            companies is not None,
            "UNCERTAINTY_COMPANY_AT_SOURCE",
            "来源级 uncertainty 不能指定 company",
        )
        _require(
            _is_nonempty_string(uncertainty["company"]),
            "UNCERTAINTY_INVALID",
            "uncertainty.company 不能为空",
        )
        _require(
            uncertainty["company"] in companies,
            "UNCERTAINTY_COMPANY_NOT_IN_NODE",
            "企业不确定性必须引用当前节点中的企业",
        )
    if "evidence" in uncertainty:
        _validate_evidence(uncertainty["evidence"])


def _validate_nodes(
    nodes: object,
    depth: int,
    allow_uncertainties: bool,
) -> bool:
    """递归校验稀疏 Tree，并返回是否存在至少一家企业。"""
    _require(isinstance(nodes, list), "SOURCE_RESULT_CHAIN_INVALID", "chain 必须是数组")
    _require(
        depth <= len(CATEGORY_FIELDS),
        "TREE_DEPTH_EXCEEDED",
        "产业链正式分类最多支持 4 层",
    )
    names: set[str] = set()
    has_company = False
    for node in nodes:
        _require(
            isinstance(node, dict) and set(node).issubset(_NODE_FIELDS),
            "TREE_NODE_INVALID",
            "Tree 节点包含无效字段",
        )
        _require(
            _is_nonempty_string(node.get("name")),
            "TREE_NODE_INVALID",
            "Tree 节点 name 不能为空",
        )
        name = node["name"].strip()
        _require(
            name not in names,
            "TREE_DUPLICATE_SIBLING",
            "同一父节点下不能有同名节点",
        )
        names.add(name)

        companies = node.get("companies", [])
        _require(
            isinstance(companies, list)
            and all(_is_nonempty_string(company) for company in companies),
            "TREE_COMPANIES_INVALID",
            "companies 必须是非空字符串数组",
        )
        has_company = has_company or bool(companies)

        if "uncertainties" in node:
            _require(
                allow_uncertainties,
                "SOURCE_RESULT_ACCEPT_HAS_UNCERTAINTY",
                "accept 结果不能包含 uncertainties",
            )
            _require(
                isinstance(node["uncertainties"], list),
                "UNCERTAINTY_INVALID",
                "node.uncertainties 必须是数组",
            )
            for uncertainty in node["uncertainties"]:
                _validate_uncertainty(uncertainty, companies)

        children = node.get("children", [])
        _require(
            isinstance(children, list),
            "TREE_CHILDREN_INVALID",
            "children 必须是数组",
        )
        if children:
            has_company = (
                _validate_nodes(children, depth + 1, allow_uncertainties)
                or has_company
            )
    return has_company


def iter_uncertainties(payload: dict) -> Iterator[tuple[tuple[str, ...], str | None, dict]]:
    """按来源、节点和企业 occurrence 的位置遍历 uncertainty。"""

    def walk(
        nodes: list[dict], path: tuple[str, ...]
    ) -> Iterator[tuple[tuple[str, ...], str | None, dict]]:
        for node in nodes:
            current = path + (node["name"].strip(),)
            for item in node.get("uncertainties", []):
                yield current, item.get("company"), item
            yield from walk(node.get("children", []), current)

    for item in payload.get("uncertainties", []):
        yield (), None, item
    yield from walk(payload.get("chain", []), ())


def validate_source_result(payload: dict) -> dict:
    """校验 Agent-facing SourceResult，并返回独立快照。"""
    _require(isinstance(payload, dict), "SOURCE_RESULT_INVALID", "SourceResult 必须是对象")
    outcome = payload.get("outcome")
    _require(
        outcome in {"accept", "review"},
        "SOURCE_RESULT_OUTCOME_INVALID",
        "outcome 必须是 accept 或 review",
    )
    allowed_fields = {"outcome", "source", "description", "chain"}
    if outcome == "review":
        allowed_fields.add("uncertainties")
    _require(
        set(payload).issubset(allowed_fields)
        and {"outcome", "source", "description", "chain"}.issubset(payload),
        "SOURCE_RESULT_FIELD_INVALID",
        "SourceResult 包含无效或缺失字段",
    )

    _validate_source(payload["source"])
    _require(
        _is_nonempty_string(payload["description"]),
        "SOURCE_RESULT_DESCRIPTION_INVALID",
        "description 不能为空",
    )
    chain = payload["chain"]
    has_company = _validate_nodes(chain, depth=1, allow_uncertainties=outcome == "review")

    if outcome == "review" and "uncertainties" in payload:
        _require(
            isinstance(payload["uncertainties"], list),
            "UNCERTAINTY_INVALID",
            "uncertainties 必须是数组",
        )
        for uncertainty in payload["uncertainties"]:
            _validate_uncertainty(uncertainty, companies=None)

    uncertainties = list(iter_uncertainties(payload))
    if outcome == "accept":
        _require(
            bool(chain),
            "SOURCE_RESULT_ACCEPT_EMPTY_CHAIN",
            "accept 的 chain 不能为空",
        )
        _require(
            not uncertainties,
            "SOURCE_RESULT_ACCEPT_HAS_UNCERTAINTY",
            "accept 结果不能包含 uncertainty",
        )
        _require(
            has_company,
            "SOURCE_RESULT_ACCEPT_HAS_NO_COMPANY",
            "accept 的 chain 至少需要一家企业",
        )
    else:
        _require(
            bool(uncertainties),
            "SOURCE_RESULT_REVIEW_HAS_NO_UNCERTAINTY",
            "review 必须包含 uncertainty",
        )
    return deepcopy(payload)


def strip_uncertainties(chain: list[dict]) -> list[dict]:
    """移除审核字段，生成可进入正式来源组的 Tree。"""
    _validate_nodes(chain, depth=1, allow_uncertainties=True)

    def clean(node: dict) -> dict:
        result = {"name": node["name"]}
        if node.get("companies"):
            result["companies"] = list(node["companies"])
        if node.get("children"):
            result["children"] = [clean(child) for child in node["children"]]
        return result

    return [clean(node) for node in chain]


def compile_tree_records(
    topic_name: str,
    source: dict,
    description: str,
    chain: list[dict],
) -> list[dict[str, str]]:
    """把经过确认的 Tree 编译为正式九字段记录。"""
    validated = validate_source_result(
        {
            "outcome": "accept",
            "source": source,
            "description": description,
            "chain": chain,
        }
    )
    _require(
        _is_nonempty_string(topic_name),
        "SOURCE_RESULT_TOPIC_INVALID",
        "正式主题不能为空",
    )
    records: list[dict[str, str]] = []

    def walk(node: dict, path: tuple[str, ...]) -> None:
        current = path + (node["name"].strip(),)
        categories = (*current, *("" for _ in range(len(CATEGORY_FIELDS) - len(current))))
        records.append(
            {
                "主题": topic_name.strip(),
                "信源主体": validated["source"]["name"].strip(),
                "分类1": categories[0],
                "分类2": categories[1],
                "分类3": categories[2],
                "分类4": categories[3],
                "公司": "、".join(company.strip() for company in node.get("companies", [])),
                "信源URL": validated["source"]["url"].strip(),
                "备注": validated["description"].strip() if not records else "",
            }
        )
        for child in node.get("children", []):
            walk(child, current)

    for root in validated["chain"]:
        walk(root, ())
    return records
