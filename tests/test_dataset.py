"""分级数据集操作测试。"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from industry_chain_skills.dataset import DatasetService, validate_source_payload
from industry_chain_skills.errors import ClientError
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.storage import RunnerStore


def source_payload(url: str = "https://example.com/report") -> dict:
    """创建有效来源组载荷。"""
    return {
        "records": [
            {
                "主题": "测试主题",
                "信源主体": "测试研究院",
                "分类1": "上游",
                "分类2": "材料",
                "分类3": "",
                "分类4": "",
                "公司": "甲公司",
                "信源URL": url,
                "备注": "发布日期未识别",
            },
            {
                "主题": "测试主题",
                "信源主体": "测试研究院",
                "分类1": "中游",
                "分类2": "制造",
                "分类3": "",
                "分类4": "",
                "公司": "",
                "信源URL": url,
                "备注": "",
            },
        ]
    }


def prepared_dataset(tmp_path, topic_config):
    """创建已领取首个主题的数据集服务。"""
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    store = RunnerStore(tmp_path / "runs")
    runner = RunnerService(store, clock=lambda: now, token_factory=lambda: "token-a")
    created = runner.create("测试批次", topic_config)
    claimed = runner.claim_next(created["runner_id"])
    dataset = DatasetService(store, clock=lambda: now)
    return dataset, runner, created["runner_id"], claimed["node_id"], claimed["claim_token"]


def test_source_group_insert_patch_replace_and_remove(tmp_path, topic_config) -> None:
    """来源组支持插入、共享字段修改、替换和删除。"""
    dataset, _, runner_id, node_id, token = prepared_dataset(tmp_path, topic_config)
    inserted = dataset.insert(
        runner_id, "source_group", source_payload(), node_id,
        None, None, token,
    )
    group_id = inserted["source_group_id"]
    patched = dataset.patch(
        runner_id, "source_group", group_id,
        {"信源主体": "新主体", "备注": "范围变化；发布日期未识别"},
        token,
    )
    assert all(row["record"]["信源主体"] == "新主体" for row in patched["rows"])
    assert patched["rows"][1]["record"]["备注"] == ""

    replaced = dataset.replace(
        runner_id, "source_group", group_id,
        {"records": [source_payload()["records"][0]]}, token,
    )
    assert replaced["source_group_id"] == group_id
    assert len(replaced["rows"]) == 1

    dataset.remove(runner_id, "source_group", group_id, token)
    assert dataset.get(runner_id, "topic", node_id)["source_groups"] == []


def unknown_field(payload):
    """加入 Schema 外字段。"""
    payload["records"][0]["未知字段"] = "值"


def category_gap(payload):
    """制造分类断层。"""
    payload["records"][0]["分类2"] = ""
    payload["records"][0]["分类3"] = "三级"


def second_remark(payload):
    """在非首行填写备注。"""
    payload["records"][1]["备注"] = "不应出现"


def no_company(payload):
    """清空来源组全部企业。"""
    for record in payload["records"]:
        record["公司"] = ""


def metadata_mismatch(payload):
    """制造组内共享字段不一致。"""
    payload["records"][1]["信源主体"] = "其他主体"


def invalid_url(payload):
    """把来源地址改为无效值。"""
    for record in payload["records"]:
        record["信源URL"] = "not-a-url"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (unknown_field, "RECORD_SCHEMA_INVALID"),
        (category_gap, "CATEGORY_GAP"),
        (second_remark, "REMARK_NOT_FIRST_ROW"),
        (no_company, "SOURCE_GROUP_HAS_NO_COMPANY"),
        (metadata_mismatch, "SOURCE_GROUP_METADATA_MISMATCH"),
        (invalid_url, "SOURCE_URL_INVALID"),
    ],
    ids=["额外字段", "分类断层", "非首行备注", "无企业", "组内元数据不一致", "无效URL"],
)
def test_invalid_source_payloads_are_rejected(mutate, expected_code) -> None:
    """来源组业务结构错误返回对应错误代码。"""
    payload = deepcopy(source_payload())
    mutate(payload)
    with pytest.raises(ClientError) as error:
        validate_source_payload(payload)
    assert error.value.code == expected_code


def test_token_position_topic_propagation_and_terminal_guard(tmp_path, topic_config) -> None:
    """令牌、指定位置、主题传播和终态保护同时生效。"""
    dataset, runner, runner_id, node_id, token = prepared_dataset(tmp_path, topic_config)
    with pytest.raises(ClientError) as error:
        dataset.insert(
            runner_id, "source_group", source_payload("https://example.com/wrong"),
            node_id, None, None, "wrong-token",
        )
    assert error.value.code == "CLAIM_TOKEN_INVALID"

    first = dataset.insert(
        runner_id, "source_group", source_payload("https://example.com/first"),
        node_id, None, None, token,
    )
    second = dataset.insert(
        runner_id, "source_group", source_payload("https://example.com/second"),
        node_id, first["source_group_id"], None, token,
    )
    topic = dataset.get(runner_id, "topic", node_id)
    assert [group["source_group_id"] for group in topic["source_groups"]] == [
        second["source_group_id"], first["source_group_id"],
    ]

    patched = dataset.patch(
        runner_id, "topic", node_id, {"主题": "修正主题"}, token,
    )
    assert all(
        row["record"]["主题"] == "修正主题"
        for group in patched["source_groups"]
        for row in group["rows"]
    )

    runner.finish(runner_id, node_id, token, "completed")
    dataset.remove(runner_id, "source_group", first["source_group_id"], None)
    with pytest.raises(ClientError) as error:
        dataset.remove(runner_id, "source_group", second["source_group_id"], None)
    assert error.value.code == "TOPIC_TERMINAL_DATA_CONFLICT"
