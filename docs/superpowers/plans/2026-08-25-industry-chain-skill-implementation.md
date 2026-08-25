# 产业链检索与解析 Skill 实施计划

> **供执行 Agent 使用：** 实施时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项执行。使用复选框（`- [ ]`）记录进度。

**目标：** 建立一个跨 Agent 的产业链检索与解析 Skill，以及支持 Runner、主题状态、来源组、审核修改和实时 XLSX 交付的 Python CLI Client。

**架构：** Agent 按通用 `SKILL.md`完成搜索、浏览器操作、视觉解析和九字段 JSON 生成。Python 包通过 CLI 管理只读主题快照、领取租约、数据操作、并发持久化和 XLSX；每个 Runner 使用独立 JSON 和 XLSX，不依赖现有产业链项目。

**技术栈：** Python 3.11+、PyYAML、jsonschema、openpyxl、filelock、pytest、argparse

**设计文档：** `docs/superpowers/specs/2026-08-25-industry-chain-skill-design.md`

## 全局约束

- 项目根目录固定为 `E:\industry-chain-paeser-skills`。
- 不导入、不复制、不调用 `E:\Industry-chain-parser-v3` 的代码、Skill 或配置。
- 只维护一份通用 `SKILL.md`，不写死 Codex、Trae 或浏览器插件名称。
- 模型业务输出只能是 `{"records": [{九字段记录}]}`。
- Client 只执行确定性校验和数据操作，不判断来源、节点或企业归属。
- 每个 Runner 使用独立目录、主题快照、状态 JSON 和九列 XLSX。
- 来源组按实际成功写入顺序获得 Runner 全局顺序。
- 所有 Runner 状态和数据操作显式传入 `runner_id`。
- `in_progress`主题的研究写入必须携带有效 `claim_token`。
- 默认租约60分钟；Skill 至少每20分钟续期一次。
- 每次成功数据修改同时更新当前 JSON 和 XLSX；URL 单元格设置超链接。
- 项目文档只描述当前业务、接口和使用方式，不记录修改历史或设计过程。
- 所有项目文档、SKILL、注释、docstring、错误信息、测试说明和用户可见文本使用中文；Python 关键字、依赖名、包名、模块名、代码标识符、CLI 命令和协议字段保留稳定英文形式。
- 实现任务只执行本任务的针对性测试；完整测试套件仅在最后执行一次。

---

## 文件职责

| 文件 | 职责 |
|---|---|
| `pyproject.toml` | 包元数据、依赖、CLI 入口和 pytest 配置 |
| `.gitignore` | 排除虚拟环境、缓存、构建产物和 Runner 运行数据 |
| `schemas/record.schema.json` | 模型 `records`九字段 Schema |
| `src/industry_chain_skills/errors.py` | 稳定错误代码和 JSON 错误结构 |
| `src/industry_chain_skills/identity.py` | YAML 读取、精确查询、模糊查询和主题快照 |
| `src/industry_chain_skills/excel.py` | 九列表头、全局来源顺序和 URL 超链接 |
| `src/industry_chain_skills/storage.py` | Runner 文件锁、状态 JSON 提交、数据 JSON/XLSX 提交和读取 |
| `src/industry_chain_skills/runner.py` | Runner 创建、状态、领取、租约、结束和失败 |
| `src/industry_chain_skills/dataset.py` | 三个作用域的 get、insert、patch、replace、remove |
| `src/industry_chain_skills/cli.py` | argparse 命令树、JSON 输入输出和退出码 |
| `tests/conftest.py` | 独立临时主题配置夹具 |
| `tests/` | 模块级测试和一条 CLI 闭环测试 |
| `SKILL.md` | Agent 运行时搜索、视觉解析和写入流程 |
| `AGENTS.md` | 项目业务背景、证据规则、Client 边界和开发约束 |
| `README.md` | 当前安装方式、CLI 入口、目录和交付文件 |

---

### 任务1：包基础、主题身份与记录 Schema

**文件：**
- 新建：`pyproject.toml`
- 新建：`.gitignore`
- 新建：`schemas/record.schema.json`
- 新建：`src/industry_chain_skills/__init__.py`
- 新建：`src/industry_chain_skills/errors.py`
- 新建：`src/industry_chain_skills/identity.py`
- 新建：`tests/conftest.py`
- 新建：`tests/test_identity.py`

**接口：**
- 提供：`ClientError(code: str, message: str, details: dict | None = None)`
- 提供：`TopicIdentity(topic: str, path: tuple[str, ...], aliases: tuple[str, ...], order: int)`
- 提供：`load_catalog(config_path: Path) -> list[TopicIdentity]`
- 提供：`get_identity(config_path: Path, topic: str) -> TopicIdentity`
- 提供：`search_identities(config_path: Path, query: str) -> list[TopicIdentity]`
- 依赖：不使用其他项目代码；测试只使用临时 YAML

- [ ] **步骤1：加入包元数据、忽略规则和失败的主题身份测试**

`pyproject.toml`使用以下依赖范围：

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "industry-chain-paeser-skills"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0,<7",
  "jsonschema>=4.23,<5",
  "openpyxl>=3.1,<4",
  "filelock>=3.16,<4"
]

[project.optional-dependencies]
test = ["pytest>=8.3,<9"]

[project.scripts]
industry-chain = "industry_chain_skills.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

在`.gitignore`中加入`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.egg-info/`、`build/`、`dist/`和`runs/`。

在`tests/test_identity.py`中使用包含两个有序主题的临时 YAML：

```python
from pathlib import Path

import pytest

from industry_chain_skills.errors import ClientError
from industry_chain_skills.identity import get_identity, load_catalog, search_identities


def write_config(path: Path) -> None:
    path.write_text(
        """themes:\n  半导体与精密装备:\n    path: [先进制造, 半导体与精密装备]\n    aliases: [半导体及设备]\n  存储芯片:\n    path: [先进制造, 半导体与精密装备, 半导体器件, 存储芯片]\n    aliases: [Memory Chip]\n""",
        encoding="utf-8",
    )


def test_catalog_preserves_order_and_searches_path_aliases(tmp_path: Path) -> None:
    """主题目录保持配置顺序，并支持路径和别名搜索。"""
    config = tmp_path / "topics.yaml"
    write_config(config)
    catalog = load_catalog(config)
    assert [item.topic for item in catalog] == ["半导体与精密装备", "存储芯片"]
    assert get_identity(config, "存储芯片").order == 2
    assert [item.topic for item in search_identities(config, "Memory")] == ["存储芯片"]
    assert [item.topic for item in search_identities(config, "半导体器件")] == ["存储芯片"]


def test_invalid_theme_structure_returns_stable_error(tmp_path: Path) -> None:
    """无效主题结构返回稳定错误代码。"""
    config = tmp_path / "topics.yaml"
    config.write_text("themes:\n  错误主题:\n    path: not-a-list\n", encoding="utf-8")
    with pytest.raises(ClientError) as exc:
        load_catalog(config)
    assert exc.value.code == "TOPIC_CONFIG_INVALID"
```

在`tests/conftest.py`中创建后续 Runner 和 CLI 测试共用的临时配置夹具：

```python
from pathlib import Path

import pytest


@pytest.fixture
def topic_config(tmp_path: Path) -> Path:
    path = tmp_path / "topic_identity.yaml"
    path.write_text(
        """themes:\n  测试主题:\n    path: [测试分类, 测试主题]\n    aliases: [测试别名]\n  第二主题:\n    path: [测试分类, 第二主题]\n    aliases: []\n""",
        encoding="utf-8",
    )
    return path
```

- [ ] **步骤2：运行主题身份测试并确认模块缺失失败**

运行：

```powershell
python -m pip install -e ".[test]"
python -m pytest tests/test_identity.py -q
```

预期：测试收集失败，原因是`industry_chain_skills.errors`和`identity`尚不存在。

- [ ] **步骤3：实现错误、主题身份读取和最小记录 Schema**

实现`ClientError`，供 CLI 输出稳定错误结构：

```python
class ClientError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict:
        error = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return error
```

在`identity.py`中按以下规则实现 YAML 校验：

- 根节点必须包含名为`themes`的映射
- 每个主题名称必须是非空字符串
- `path`和`aliases`必须是字符串列表
- 缺少`aliases`时使用空元组
- 目录顺序使用 YAML 插入顺序，从1开始
- 对正式主题、别名和每个路径片段执行不区分大小写的搜索
- 文件或解析失败使用`TOPIC_CONFIG_NOT_FOUND`或`TOPIC_CONFIG_INVALID`
- 精确主题不存在时使用`TOPIC_NOT_FOUND`

创建`schemas/record.schema.json`，只保留顶层`records`数组和设计文档规定的九个必填字符串字段，不加入描述、ID、证据、置信度、日期或内部状态字段。

- [ ] **步骤4：运行针对性测试**

运行：`python -m pytest tests/test_identity.py -q`

预期：主题身份测试全部通过。

- [ ] **步骤5：提交基础实现**

```powershell
git add pyproject.toml .gitignore schemas/record.schema.json src/industry_chain_skills/__init__.py src/industry_chain_skills/errors.py src/industry_chain_skills/identity.py tests/conftest.py tests/test_identity.py
git commit -m "feat: 添加主题身份基础"
```

---

### 任务2：Runner 存储与 XLSX 投影

**文件：**
- 新建：`src/industry_chain_skills/excel.py`
- 新建：`src/industry_chain_skills/storage.py`
- 新建：`tests/test_storage_excel.py`

**接口：**
- 依赖：`ClientError`
- 提供：`HEADERS: tuple[str, ...]`
- 提供：`write_workbook(state: dict, target: Path) -> None`
- 提供：`RunnerStore(runs_root: Path, lock_timeout: float = 10.0)`
- 提供：`RunnerStore.create(state: dict) -> Path`
- 提供：`RunnerStore.read(runner_id: str) -> dict`
- 提供：`RunnerStore.mutate_state(runner_id: str, mutation: Callable[[dict], T]) -> T`
- 提供：`RunnerStore.mutate_dataset(runner_id: str, mutation: Callable[[dict], T]) -> T`
- 提供：`RunnerStore.export(runner_id: str) -> Path`
- 提供：`RunnerStore.list_summaries() -> list[dict]`

- [ ] **步骤1：编写失败的存储与工作簿测试**

创建包含两个主题的夹具状态，两个来源组的全局顺序分别为2和1；断言 XLSX 按全局顺序输出，并使用精确表头和 URL 超链接：

```python
from pathlib import Path

import pytest
from openpyxl import load_workbook

from industry_chain_skills.errors import ClientError
from industry_chain_skills.storage import RunnerStore


def make_record(topic: str, url: str) -> dict[str, str]:
    return {
        "主题": topic,
        "信源主体": "测试研究院",
        "分类1": "上游",
        "分类2": "材料",
        "分类3": "",
        "分类4": "",
        "公司": "甲公司",
        "信源URL": url,
        "备注": "",
    }


def build_runner_state_with_out_of_order_groups() -> dict:
    timestamp = "2026-08-25T08:00:00+00:00"
    second_group = {
        "source_group_id": "source_second",
        "order": 2,
        "created_at": timestamp,
        "updated_at": timestamp,
        "rows": [{
            "row_id": "row_second",
            "order": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
            "record": make_record("后写入主题", "https://example.com/second"),
        }],
    }
    first_group = {
        "source_group_id": "source_first",
        "order": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
        "rows": [{
            "row_id": "row_first",
            "order": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
            "record": make_record("先写入主题", "https://example.com/first"),
        }],
    }
    return {
        "runner_id": "20260825-080000-test-a1b2c3",
        "name": "test",
        "topic_identity_path": "C:/tmp/topics.yaml",
        "created_at": timestamp,
        "updated_at": timestamp,
        "topics": [
            {"node_id": "node_0001", "主题": "后写入主题", "path": [],
             "aliases": [], "order": 1, "status": "completed",
             "last_error": None, "claim": None, "source_groups": [second_group]},
            {"node_id": "node_0002", "主题": "先写入主题", "path": [],
             "aliases": [], "order": 2, "status": "completed",
             "last_error": None, "claim": None, "source_groups": [first_group]},
        ],
    }


def test_store_writes_json_and_ordered_hyperlink_workbook(tmp_path: Path) -> None:
    """存储层按全局顺序生成带超链接的九列工作簿。"""
    state = build_runner_state_with_out_of_order_groups()
    store = RunnerStore(tmp_path / "runs")
    workbook_path = store.create(state)

    loaded = store.read(state["runner_id"])
    assert loaded["runner_id"] == state["runner_id"]

    workbook = load_workbook(workbook_path)
    sheet = workbook["交付数据"]
    assert [sheet.cell(1, column).value for column in range(1, 10)] == [
        "主题", "信源主体", "分类1", "分类2", "分类3",
        "分类4", "公司", "信源URL", "备注",
    ]
    assert sheet.cell(2, 1).value == "先写入主题"
    assert sheet.cell(2, 8).hyperlink.target == "https://example.com/first"
```

辅助函数使用完整字典，不使用模拟对象。加入以下回滚测试：

```python
def test_projection_failure_preserves_existing_pair(tmp_path, monkeypatch) -> None:
    """工作簿投影失败时保留原有 JSON 和 XLSX。"""
    state = build_runner_state_with_out_of_order_groups()
    store = RunnerStore(tmp_path / "runs")
    workbook_path = store.create(state)
    json_path = workbook_path.parent / "runner.json"
    before_json = json_path.read_bytes()
    before_xlsx = workbook_path.read_bytes()

    def fail_projection(state: dict, target: Path) -> None:
        raise OSError("投影失败")

    monkeypatch.setattr("industry_chain_skills.storage.write_workbook", fail_projection)
    with pytest.raises(ClientError):
        store.mutate_dataset(state["runner_id"], lambda current: current.update(name="changed"))

    assert json_path.read_bytes() == before_json
    assert workbook_path.read_bytes() == before_xlsx
```

- [ ] **步骤2：运行存储测试并确认模块缺失失败**

运行：`python -m pytest tests/test_storage_excel.py -q`

预期：测试收集失败，原因是`storage.py`和`excel.py`尚不存在。

- [ ] **步骤3：实现工作簿投影和加锁的双文件持久化**

使用固定表头元组：

```python
HEADERS = (
    "主题", "信源主体", "分类1", "分类2", "分类3",
    "分类4", "公司", "信源URL", "备注",
)


def iter_records_in_global_order(state: dict):
    groups = [
        group
        for topic in state["topics"]
        for group in topic["source_groups"]
    ]
    for group in sorted(groups, key=lambda item: item["order"]):
        for row in sorted(group["rows"], key=lambda item: item["order"]):
            yield row["record"]
```

`write_workbook`创建一个`交付数据`工作表，依次写入表头和记录；第8列 URL 非空时，同时设置`cell.hyperlink`和`Hyperlink`样式。

`RunnerStore`遵守以下规则：

- 锁文件位于`runs/.locks/<runner_id>.lock`
- `mutate_state`只生成并原子替换 JSON，不重建 XLSX
- `mutate_dataset`在 Runner 目录生成临时 JSON 和 XLSX
- 数据操作在替换正式文件前生成两个临时文件
- 数据操作保留备份直到两个正式文件替换成功
- 任一数据文件替换失败时恢复操作前文件对
- 成功或回滚后删除临时文件和备份文件
- 使用`RUNNER_NOT_FOUND`、`RUNNER_STATE_INVALID`、`RUNNER_LOCK_TIMEOUT`或`XLSX_LOCKED`
- `export`以`runner.json`为权威状态

- [ ] **步骤4：运行针对性的存储与 XLSX 测试**

运行：`python -m pytest tests/test_storage_excel.py -q`

预期：工作簿、超链接、顺序、回滚和读取测试通过。

- [ ] **步骤5：提交存储与投影实现**

```powershell
git add src/industry_chain_skills/excel.py src/industry_chain_skills/storage.py tests/test_storage_excel.py
git commit -m "feat: 添加 Runner 存储与 XLSX 导出"
```

---

### 任务3：Runner 生命周期、主题状态与租约

**文件：**
- 新建：`src/industry_chain_skills/runner.py`
- 新建：`tests/test_runner.py`

**接口：**
- 依赖：`load_catalog`、`RunnerStore`、`ClientError`
- 提供：`LEASE_SECONDS = 3600`
- 提供：`RENEW_INTERVAL_SECONDS = 1200`
- 提供：`RunnerService(store: RunnerStore, clock: Callable[[], datetime] | None = None, token_factory: Callable[[], str] | None = None)`
- 提供：`RunnerService.create(name: str, config_path: Path) -> dict`
- 提供：`RunnerService.status(runner_id: str) -> dict`
- 提供：`RunnerService.claim_next(runner_id: str) -> dict`
- 提供：`RunnerService.claim(runner_id: str, node_id: str, reopen: bool = False) -> dict`
- 提供：`RunnerService.renew(runner_id: str, node_id: str, claim_token: str) -> dict`
- 提供：`RunnerService.finish(runner_id: str, node_id: str, claim_token: str, outcome: str) -> dict`
- 提供：`RunnerService.fail(runner_id: str, node_id: str, claim_token: str, code: str, message: str) -> dict`
- 提供：`require_and_renew_claim(topic: dict, claim_token: str, now: datetime) -> None`

- [ ] **步骤1：编写失败的生命周期测试**

注入时钟和令牌工厂，测试中不使用等待：

```python
from datetime import datetime, timedelta, timezone

import pytest

from industry_chain_skills.errors import ClientError
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.storage import RunnerStore


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def test_claim_lease_expiry_reclaim_and_finish(tmp_path):
    """有效租约不可重复领取，过期后可以安全重领。"""
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    topic_config = tmp_path / "one-topic.yaml"
    topic_config.write_text(
        "themes:\n  唯一主题:\n    path: [测试分类, 唯一主题]\n    aliases: []\n",
        encoding="utf-8",
    )
    clock = MutableClock(now)
    tokens = iter(["token-a", "token-b"])
    service = RunnerService(
        RunnerStore(tmp_path / "runs"),
        clock=clock,
        token_factory=lambda: next(tokens),
    )
    created = service.create("测试批次", topic_config)
    runner_id = created["runner_id"]

    first = service.claim_next(runner_id)
    assert first["claim_token"] == "token-a"
    with pytest.raises(ClientError) as exc:
        service.claim_next(runner_id)
    assert exc.value.code == "NO_PENDING_TOPIC"

    clock.current = now + timedelta(seconds=3601)
    reclaimed = service.claim_next(runner_id)
    assert reclaimed["node_id"] == first["node_id"]
    assert reclaimed["claim_token"] == "token-b"

    with pytest.raises(ClientError) as exc:
        service.finish(runner_id, first["node_id"], "token-a", "completed")
    assert exc.value.code == "CLAIM_TOKEN_INVALID"

    with pytest.raises(ClientError) as exc:
        service.finish(runner_id, first["node_id"], "token-b", "completed")
    assert exc.value.code == "TOPIC_HAS_NO_SOURCE_GROUP"
```

在同一测试文件中加入以下生命周期断言：

```python
def test_snapshot_no_source_failure_counts_and_reopen(tmp_path, topic_config):
    """主题快照、无来源终态、失败统计和重开保持一致。"""
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    store = RunnerStore(tmp_path / "runs")
    service = RunnerService(store, clock=lambda: now, token_factory=lambda: "token-a")
    created = service.create("批次", topic_config)
    runner_id = created["runner_id"]

    topic_config.write_text("themes: {}\n", encoding="utf-8")
    claimed = service.claim_next(runner_id)
    service.finish(runner_id, claimed["node_id"], claimed["claim_token"], "no_qualified_source")
    status = service.status(runner_id)
    assert status["counts"]["no_qualified_source"] == 1
    assert status["total"] == 2

    reopened = service.claim(runner_id, claimed["node_id"], reopen=True)
    assert reopened["status"] == "in_progress"
    service.fail(runner_id, claimed["node_id"], reopened["claim_token"], "BROWSER_UNAVAILABLE", "浏览器不可用")
    status = service.status(runner_id)
    assert status["counts"]["failed"] == 1
    assert status["remaining"] == 2
```

- [ ] **步骤2：运行生命周期测试并确认失败**

运行：`python -m pytest tests/test_runner.py -q`

预期：测试收集失败，原因是`runner.py`尚不存在。

- [ ] **步骤3：实现 Runner 状态转换和租约辅助函数**

使用带时区的 ISO 字符串和以下领取字段：

```python
def new_claim(token: str, now: datetime) -> dict:
    expires_at = now + timedelta(seconds=LEASE_SECONDS)
    return {
        "token": token,
        "claimed_at": now.isoformat(),
        "lease_expires_at": expires_at.isoformat(),
    }


def require_and_renew_claim(topic: dict, claim_token: str, now: datetime) -> None:
    claim = topic.get("claim")
    if not claim or claim["token"] != claim_token:
        raise ClientError("CLAIM_TOKEN_INVALID", "主题领取令牌无效")
    if datetime.fromisoformat(claim["lease_expires_at"]) <= now:
        raise ClientError("CLAIM_LEASE_EXPIRED", "主题领取租约已过期")
    claim["lease_expires_at"] = (
        now + timedelta(seconds=LEASE_SECONDS)
    ).isoformat()
```

每个生命周期操作在一次加锁的`RunnerStore.mutate_state`调用中实现以下状态规则：

- Runner ID 使用本地时区，格式为`<YYYYMMDD-HHMMSS>-<safe-name>-<6-hex>`；替换 Windows 文件名非法字符，并保存配置绝对路径
- 创建时快照全部 YAML 主题，并分配`node_0001`序列 ID
- 创建响应使用与状态响应一致的总数、分类计数、剩余数量和下一个主题结构
- `claim-next`按顺序优先选择租约过期的`in_progress`主题，再选择`pending`主题
- 跳过租约仍有效的`in_progress`主题
- `claim`接受`pending`和`failed`；终态必须使用`reopen=True`
- `renew`、`finish`和`fail`要求有效且未过期的令牌
- `completed`要求至少一个来源组
- `no_qualified_source`要求零来源组
- `fail`只保存当前错误代码和信息，并清除领取信息
- `finish`清除领取信息和当前错误
- `status`实时计算分类计数、剩余数量、处理中主题、下一个待处理主题、过期主题和失败列表，不持久化汇总值

- [ ] **步骤4：运行针对性生命周期测试**

运行：`python -m pytest tests/test_runner.py -q`

预期：生命周期、租约、快照、重开和状态测试通过。

- [ ] **步骤5：提交 Runner 生命周期实现**

```powershell
git add src/industry_chain_skills/runner.py tests/test_runner.py
git commit -m "feat: 添加 Runner 生命周期与主题租约"
```

---

### 任务4：数据集校验与分级操作

**文件：**
- 新建：`src/industry_chain_skills/dataset.py`
- 新建：`tests/test_dataset.py`

**接口：**
- 依赖：`RunnerStore`、`ClientError`、`require_and_renew_claim`、`schemas/record.schema.json`
- 提供：`validate_source_payload(payload: dict) -> list[dict[str, str]]`
- 提供：`DatasetService(store: RunnerStore, clock: Callable[[], datetime] | None = None)`
- 提供：`DatasetService.get(runner_id: str, scope: str, target_id: str) -> dict`
- 提供：`DatasetService.insert(runner_id: str, scope: str, payload: dict, parent_id: str | None, before_id: str | None, after_id: str | None, claim_token: str | None) -> dict`
- 提供：`DatasetService.patch(runner_id: str, scope: str, target_id: str, changes: dict, claim_token: str | None) -> dict`
- 提供：`DatasetService.replace(runner_id: str, scope: str, target_id: str, payload: dict, claim_token: str | None) -> dict`
- 提供：`DatasetService.remove(runner_id: str, scope: str, target_id: str, claim_token: str | None) -> dict`

- [ ] **步骤1：编写失败的记录与操作测试**

使用一个包含`in_progress`主题和有效令牌的 Runner 夹具，在不重复所有作用域组合的前提下覆盖五种操作：

```python
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from industry_chain_skills.dataset import DatasetService, validate_source_payload
from industry_chain_skills.errors import ClientError
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.storage import RunnerStore


def source_payload(url: str = "https://example.com/report") -> dict:
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
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    store = RunnerStore(tmp_path / "runs")
    runner = RunnerService(store, clock=lambda: now, token_factory=lambda: "token-a")
    created = runner.create("测试批次", topic_config)
    claimed = runner.claim_next(created["runner_id"])
    dataset = DatasetService(store, clock=lambda: now)
    return dataset, runner, created["runner_id"], claimed["node_id"], claimed["claim_token"]


def test_source_group_insert_patch_replace_and_remove(tmp_path, topic_config):
    """来源组支持插入、共享字段修改、替换和删除。"""
    dataset, runner, runner_id, node_id, token = prepared_dataset(tmp_path, topic_config)
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
```

加入一个参数化校验测试：

```python
def unknown_field(payload):
    payload["records"][0]["未知字段"] = "值"


def category_gap(payload):
    payload["records"][0]["分类2"] = ""
    payload["records"][0]["分类3"] = "三级"


def second_remark(payload):
    payload["records"][1]["备注"] = "不应出现"


def no_company(payload):
    for record in payload["records"]:
        record["公司"] = ""


def metadata_mismatch(payload):
    payload["records"][1]["信源主体"] = "其他主体"


def invalid_url(payload):
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
def test_invalid_source_payloads_are_rejected(mutate, expected_code):
    """来源组业务结构错误返回对应错误代码。"""
    payload = deepcopy(source_payload())
    mutate(payload)
    with pytest.raises(ClientError) as exc:
        validate_source_payload(payload)
    assert exc.value.code == expected_code
```

加入一个状态与位置测试：

```python
def test_token_position_topic_propagation_and_terminal_guard(tmp_path, topic_config):
    """令牌、指定位置、主题传播和终态保护同时生效。"""
    dataset, runner, runner_id, node_id, token = prepared_dataset(tmp_path, topic_config)
    with pytest.raises(ClientError) as exc:
        dataset.insert(
            runner_id, "source_group", source_payload("https://example.com/wrong"),
            node_id, None, None, "wrong-token",
        )
    assert exc.value.code == "CLAIM_TOKEN_INVALID"

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
    with pytest.raises(ClientError) as exc:
        dataset.remove(runner_id, "source_group", second["source_group_id"], None)
    assert exc.value.code == "TOPIC_TERMINAL_DATA_CONFLICT"
```

- [ ] **步骤2：运行数据集测试并确认失败**

运行：`python -m pytest tests/test_dataset.py -q`

预期：测试收集失败，原因是`dataset.py`尚不存在。

- [ ] **步骤3：实现 Schema 校验和五种分级操作**

使用`Draft202012Validator`和来源组规则实现来源校验：

```python
import json
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "record.schema.json"
RECORD_VALIDATOR = Draft202012Validator(
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
)


def validate_source_payload(payload: dict) -> list[dict[str, str]]:
    errors = sorted(RECORD_VALIDATOR.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ClientError("RECORD_SCHEMA_INVALID", errors[0].message)
    records = payload["records"]
    required_values = ("主题", "信源主体", "分类1", "信源URL")
    for index, record in enumerate(records):
        if any(not record[field] for field in required_values):
            raise ClientError("RECORD_REQUIRED_VALUE_EMPTY", f"第{index + 1}行必填值为空")
        if record["分类3"] and not record["分类2"]:
            raise ClientError("CATEGORY_GAP", f"第{index + 1}行分类层级断层")
        if record["分类4"] and not record["分类3"]:
            raise ClientError("CATEGORY_GAP", f"第{index + 1}行分类层级断层")
    if any(record["备注"] for record in records[1:]):
        raise ClientError("REMARK_NOT_FIRST_ROW", "只有来源组第一行可以填写备注")
    if not any(record["公司"] for record in records):
        raise ClientError("SOURCE_GROUP_HAS_NO_COMPANY", "来源组至少一行必须包含企业")
    return records
```

补充主题、信源主体、URL一致性和 HTTP(S) URL 解析校验，并按以下确定性规则实现操作：

- 来源组顺序是 Runner 全局顺序，插入或删除后重新编号
- 数据行顺序是来源组内顺序，插入或删除后重新编号
- `before_id`和`after_id`必须属于同一作用域，且不能同时提供
- `in_progress`主题的数据修改调用`require_and_renew_claim`
- 所有数据操作通过`RunnerStore.mutate_dataset`提交，确保业务数据变化同步刷新 XLSX
- 终态审核修改在不破坏`completed`或`no_qualified_source`一致性时不要求令牌
- 来源组 Patch 只接受主题、信源主体、URL和首行备注
- 主题 Patch 修改主题、路径和别名，并把正式主题传播到全部数据行
- Replace 保留目标 ID和位置，但重新生成子对象 ID
- 主题 Replace 从旧主题最早的全局位置插入重建后的来源组
- 删除最后一行返回`REMOVE_SOURCE_GROUP_REQUIRED`

- [ ] **步骤4：运行针对性数据集测试**

运行：`python -m pytest tests/test_dataset.py -q`

预期：校验、位置、令牌、修改、替换、删除和传播测试通过。

- [ ] **步骤5：提交数据集操作**

```powershell
git add src/industry_chain_skills/dataset.py tests/test_dataset.py
git commit -m "feat: 添加分级数据集操作"
```

---

### 任务5：CLI 与一条 Client 端到端流程

**文件：**
- 新建：`src/industry_chain_skills/cli.py`
- 新建：`tests/test_cli.py`

**接口：**
- 依赖：主题身份函数、`RunnerService`、`DatasetService`、`RunnerStore`
- 提供：`main(argv: list[str] | None = None) -> int`
- 提供：安装后的`industry-chain`命令

- [ ] **步骤1：编写失败的 CLI 流程测试**

通过子进程调用测试一条完整 Client 流程：主题身份搜索、Runner 创建、主题领取、从 JSON 文件插入来源组、主题结束、Runner 状态和 XLSX 检查。

```python
import json
import subprocess
import sys

from openpyxl import load_workbook


def run_cli(*args: str, input_text: str | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "industry_chain_skills.cli", *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is (result.returncode == 0)
    return payload


def test_cli_create_claim_insert_finish_and_export(tmp_path, topic_config):
    """CLI 完成创建、领取、写入、结束和导出闭环。"""
    runs_root = tmp_path / "runs"
    source_json = tmp_path / "source.json"
    source_json.write_text(
        json.dumps({
            "records": [{
                "主题": "测试主题",
                "信源主体": "测试研究院",
                "分类1": "上游",
                "分类2": "材料",
                "分类3": "",
                "分类4": "",
                "公司": "甲公司",
                "信源URL": "https://example.com/report",
                "备注": "发布日期未识别",
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    created = run_cli(
        "--runs-root", str(runs_root),
        "runner", "create", "--name", "批次", "--config", str(topic_config),
    )["data"]
    claimed = run_cli(
        "--runs-root", str(runs_root),
        "topic", "claim-next", "--runner-id", created["runner_id"],
    )["data"]
    inserted = run_cli(
        "--runs-root", str(runs_root),
        "dataset", "insert", "--runner-id", created["runner_id"],
        "--scope", "source_group", "--parent-id", claimed["node_id"],
        "--claim-token", claimed["claim_token"], "--input", str(source_json),
    )["data"]
    assert inserted["source_group_id"].startswith("source_")
```

使用以下断言完成测试：

```python
    finished = run_cli(
        "--runs-root", str(runs_root),
        "topic", "finish", "--runner-id", created["runner_id"],
        "--node-id", claimed["node_id"], "--claim-token", claimed["claim_token"],
        "--outcome", "completed",
    )["data"]
    assert finished["status"] == "completed"
    status = run_cli(
        "--runs-root", str(runs_root),
        "runner", "status", "--runner-id", created["runner_id"],
    )["data"]
    assert status["counts"]["completed"] == 1
    workbook = load_workbook(status["xlsx_path"])
    assert workbook["交付数据"].cell(2, 8).hyperlink.target == "https://example.com/report"
```

加入一个并发测试：

```python
def test_concurrent_claim_next_has_one_winner(tmp_path):
    """同一待处理主题只有一个并发领取者成功。"""
    runs_root = tmp_path / "runs"
    topic_config = tmp_path / "one-topic.yaml"
    topic_config.write_text(
        "themes:\n  唯一主题:\n    path: [测试分类, 唯一主题]\n    aliases: []\n",
        encoding="utf-8",
    )
    created = run_cli(
        "--runs-root", str(runs_root),
        "runner", "create", "--name", "并发批次", "--config", str(topic_config),
    )["data"]
    command = [
        sys.executable, "-m", "industry_chain_skills.cli",
        "--runs-root", str(runs_root),
        "topic", "claim-next", "--runner-id", created["runner_id"],
    ]
    processes = [
        subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    responses = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert stderr == ""
        responses.append(json.loads(stdout))

    assert sum(response["ok"] for response in responses) == 1
    failed = next(response for response in responses if not response["ok"])
    assert failed["error"]["code"] == "NO_PENDING_TOPIC"
    winner = next(response["data"] for response in responses if response["ok"])
    topic = run_cli(
        "--runs-root", str(runs_root),
        "topic", "get", "--runner-id", created["runner_id"],
        "--node-id", winner["node_id"],
    )["data"]
    assert topic["claim"]["token"] == winner["claim_token"]
```

- [ ] **步骤2：运行 CLI 测试并确认失败**

运行：`python -m pytest tests/test_cli.py -q`

预期：子进程失败，原因是`industry_chain_skills.cli`尚不存在。

- [ ] **步骤3：实现 argparse 命令树和 JSON 协议**

使用全局`--runs-root`选项，默认值为`Path.cwd() / "runs"`。精确实现以下命令组：

```text
identity get|search
runner create|list|status|export
topic search|get|claim-next|claim|renew|finish|fail
dataset get|insert|patch|replace|remove
```

输入规则：

- `--input -`从标准输入读取一个 JSON 对象
- `--input`的其他值表示 UTF-8 JSON 文件路径
- 数据集 Insert 为来源组或数据行时要求`--parent-id`
- 数据集 Get、Patch、Replace、Remove 要求`--id`
- 所有 Runner 相关命令要求`--runner-id`

入口函数保持精简和确定：

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = dispatch(args)
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))
        return 0
    except ClientError as error:
        print(json.dumps({"ok": False, "error": error.as_dict()}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

不向标准输出写入进度或日志。未预期异常可以把堆栈写入标准错误，并返回退出码2。

- [ ] **步骤4：运行针对性 CLI 流程**

运行：`python -m pytest tests/test_cli.py -q`

预期：创建、领取、插入、结束、状态和 XLSX 闭环流程通过。

- [ ] **步骤5：提交 CLI**

```powershell
git add src/industry_chain_skills/cli.py tests/test_cli.py
git commit -m "feat: 添加产业链 CLI"
```

---

### 任务6：通用 Skill、项目指令、README 与最终验收

**文件：**
- 新建：`SKILL.md`
- 新建：`AGENTS.md`
- 新建：`README.md`
- 新建：`tests/test_skill_contract.py`

**接口：**
- 依赖：安装后的`industry-chain` CLI 和已批准设计文档
- 提供：供具备搜索、浏览器、截图、视觉和 CLI 能力的 Agent 使用的一份通用运行 Skill
- 提供：当前项目指令和安装使用文档

- [ ] **步骤1：编写失败的 Skill 契约测试**

测试只检查可执行契约标记，不检查文风：

```python
from pathlib import Path


def test_skill_contains_required_business_and_cli_gates() -> None:
    """Skill 包含视觉、搜索、租约、写入和结束硬约束。"""
    text = Path("SKILL.md").read_text(encoding="utf-8")
    required = [
        "topic claim-next",
        "claim_token",
        "视觉",
        "浏览器",
        "连续两个完整搜索轮次",
        "产业链图明确位置 > 企业列表 > 正文明确介绍",
        '"records"',
        "dataset insert",
        "topic finish",
    ]
    assert all(marker in text for marker in required)
    assert "Codex" not in text
    assert "Trae" not in text
```

- [ ] **步骤2：运行 Skill 契约测试并确认失败**

运行：`python -m pytest tests/test_skill_contract.py -q`

预期：测试失败，原因是`SKILL.md`尚不存在。

- [ ] **步骤3：编写当前状态的 Skill 和项目文档**

`SKILL.md`包含以下操作顺序：

1. 检查搜索、浏览器、截图、视觉和 CLI 能力
2. 新建、继续或指定 Runner
3. 领取主题并保存令牌
4. 长时间处理来源时至少每20分钟续期一次
5. 使用正式主题、别名、相关表达和产业链限定词搜索
6. 要求来源同时具备产业链结构和至少一组可归属企业
7. 隔离不同来源并排除同一底层文档的重复转载
8. 检查完整网页或报告，包括后续企业图
9. 对每张作为证据的图片执行实际视觉检查
10. 应用结构证据和企业证据优先级
11. 每个来源生成一组完整九字段`records`
12. 原子插入来源组并继续搜索
13. 只有搜索饱和后才能提交完成或无合格来源终态
14. 系统性能力或运行错误进入失败状态
15. 持续处理直到没有待处理主题

`AGENTS.md`描述业务背景、九字段数据行含义、来源隔离、来源资格、视觉硬门槛、证据优先级、行语义、Client 职责、Runner 状态、租约规则、文档风格和验收要求，并明确禁止加入数据库、知识图谱、来源评分平台、Agent SDK 依赖或模型推理字段。

`README.md`只包含：

- 项目用途
- Python 3.11+安装方式和`pip install -e ".[test]"`
- 必需的外部 Agent 能力
- CLI 命令组
- 新建、继续和指定补跑 Runner 示例
- Runner 目录和 XLSX 结构
- 指向`SKILL.md`、`AGENTS.md`和设计文档的链接

不写修改历史、设计方案比较、会话说明、路线图或宣传性语言。

- [ ] **步骤4：执行一次最终验收**

完整测试套件只运行一次：

```powershell
python -m pytest -q
git diff --check
```

预期：所有测试通过，`git diff --check`无输出。

只检查一次生成的测试 XLSX，确认工作表名称、九列表头、来源顺序和 URL 超链接；检查通过后不再运行第二次完整测试。

- [ ] **步骤5：提交通用 Skill 和项目文档**

```powershell
git add SKILL.md AGENTS.md README.md tests/test_skill_contract.py
git commit -m "feat: 添加通用产业链 Skill"
```

---

## 完成证据

六个任务提交全部存在，并且最终验收满足以下条件时，实施完成：

- 完整 pytest 套件一次通过
- `git diff --check`无输出
- Git 状态中没有未提交的项目文件
- 可以从外部 YAML 快照创建 Runner
- 可以通过 CLI JSON 领取、续期、写入、结束、重开和删除主题
- 两个并发领取不能同时拥有同一活动主题
- Runner XLSX 只包含九个业务列和可点击 URL
- `SKILL.md`保持 Agent 中立，并要求实际使用浏览器和视觉能力
