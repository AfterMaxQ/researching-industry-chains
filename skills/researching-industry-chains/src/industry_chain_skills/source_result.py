"""Agent SourceResult 协议与 Tree 到九字段编译。"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterator

from .errors import ClientError


CATEGORY_FIELDS = ("分类1", "分类2", "分类3", "分类4")


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ClientError(code, message)


def iter_uncertainties(payload: dict) -> Iterator[tuple[tuple[str, ...], str | None, dict]]:
    """遍历来源结果中的 uncertainty 位置。"""

    def walk(nodes: list[dict], path: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], str | None, dict]]:
        for node in nodes:
            name = str(node.get("name", ""))
            current = path + (name,)
            for item in node.get("uncertainties", []):
                yield current, node.get("company"), item
            for company in node.get("companies", []):
                for item in node.get("company_uncertainties", []):
                    yield current, company, item
            yield from walk(node.get("children", []), current)

    for item in payload.get("uncertainties", []):
        yield (), None, item
    yield from walk(payload.get("chain", []), ())


def validate_source_result(payload: dict) -> dict:
    """校验 Agent-facing SourceResult。"""
    _require(isinstance(payload, dict), "SOURCE_RESULT_INVALID", "SourceResult 必须是对象")
    _require(payload.get("outcome") in {"accept", "review"}, "SOURCE_RESULT_OUTCOME_INVALID", "outcome 必须是 accept 或 review")

    source = payload.get("source")
    _require(isinstance(source, dict), "SOURCE_RESULT_SOURCE_INVALID", "source 必须存在")
    _require(set(source) == {"name", "url"}, "SOURCE_RESULT_SOURCE_INVALID", "source 只能包含 name 和 url")
    _require(bool(payload.get("chain") or payload.get("outcome") == "review"), "SOURCE_RESULT_CHAIN_INVALID", "chain 不能为空")

    uncertainties = list(iter_uncertainties(payload))
    if payload["outcome"] == "accept" and uncertainties:
        raise ClientError("SOURCE_RESULT_ACCEPT_HAS_UNCERTAINTY", "accept 结果不能包含 uncertainty")
    if payload["outcome"] == "review" and not uncertainties:
        raise ClientError("SOURCE_RESULT_REVIEW_HAS_NO_UNCERTAINTY", "review 必须包含 uncertainty")

    return deepcopy(payload)


def strip_uncertainties(chain: list[dict]) -> list[dict]:
    """移除审核字段，生成正式 Tree。"""
    def clean(node: dict) -> dict:
        result = {"name": node["name"]}
        if node.get("companies"):
            result["companies"] = list(node["companies"])
        if node.get("children"):
            result["children"] = [clean(child) for child in node["children"]]
        return result

    return [clean(node) for node in chain]


def compile_tree_records(topic_name: str, source: dict, description: str, chain: list[dict]) -> list[dict[str, str]]:
    """把 Tree 编译为正式九字段记录。"""
    records: list[dict[str, str]] = []

    def walk(node: dict, path: list[str]) -> None:
        current = path + [node["name"]]
        companies = node.get("companies", [])
        if companies:
            row = {
                "主题": topic_name,
                "信源主体": source["name"],
                "分类1": current[0] if len(current) > 0 else "",
                "分类2": current[1] if len(current) > 1 else "",
                "分类3": current[2] if len(current) > 2 else "",
                "分类4": current[3] if len(current) > 3 else "",
                "公司": "、".join(companies),
                "信源URL": source["url"],
                "备注": description if not records else "",
            }
            records.append(row)
        for child in node.get("children", []):
            walk(child, current)

    for root in chain:
        walk(root, [])
    return records
