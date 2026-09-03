# 产业链 HITL Core 与 Agent 协议 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Agent 的交付协议从“手工九字段 + 手工审核协议”收敛为 `SourceResult(Tree)`，并在 Python Core 中实现 Tree→九字段、review_item、统一 work 调度、Human review 状态机和原子 XLSX 写入。

**Architecture:** 保留 Runner JSON 事实源、XLSX 九字段投影、现有 `DatasetService` 确定性校验和 `RunnerStore` 原子文件事务；新增 `source_result.py`、`review.py`、`work.py`、`source_service.py` 四个聚焦模块。Agent 只通过 `work claim-next`、`source submit`、topic 结束时的 `work done` 和异常时的 `work fail` 工作；Core 根据当前 work context 自动补主题、内部 ID、状态和审核数据。

**Tech Stack:** Python 3.11+、标准库、jsonschema 4.x、openpyxl 3.x、filelock 3.x、unittest、Runner JSON、XLSX。

**Spec:** `docs/superpowers/specs/2026-09-03-industry-chain-human-review-design.md`

## Global Constraints

- 最终正式交付固定为九字段：`主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注`。
- Agent 不直接输出九字段 records；Agent-facing SourceResult 只包含 `outcome + source.name/url + description + chain + review 时的 uncertainties + 可选 evidence`。
- 明确不合格候选不提交 Client，不新增 `reject` SourceResult。
- `accept` 的 chain 必须非空且完全不含 uncertainty；`review` 可 `chain=[]`，但整个 SourceResult 至少存在一个 uncertainty。
- Tree 正式分类深度最多 4；不再把第五级及以后合并到 `分类4`。
- 企业只以 `companies: string[]` 表达；同节点企业由 Client 按当前顺序用 `、` 合并。
- `description` 就是最终来源组第一行 `备注`；不建立独立 `remark` 或 `unresolved_companies` 第二事实源。
- uncertainty 就地挂载：根级表示来源、node 内无 company 表示节点、node 内带 company 表示该节点下的企业 occurrence。
- Evidence 只允许 `locator + description`，可省略或多条；不建设 Evidence Asset、截图目录、图片接口、OCR、Lightbox 或 Evidence DB。
- `source_groups` 只保存正式来源；未批准 review 不得进入 XLSX。
- Runner JSON 继续是任务事实源；任何正式业务数据变化必须通过 `RunnerStore.mutate_dataset()` 同步原子刷新 XLSX。
- 不引入数据库、Redis、消息队列、Agent SDK、模型调用日志、置信度体系或长期 Memory。
- 用户可见文档、docstring、错误信息和测试说明用中文；Python 标识符和 CLI 命令保持英文兼容名称。

---

## 文件结构与职责

| 文件 | 动作 | 单一职责 |
| --- | --- | --- |
| `skills/researching-industry-chains/src/industry_chain_skills/source_result.py` | Create | 校验 Agent-facing SourceResult、递归 Tree 校验、uncertainty 定位校验、Tree→九字段编译、剥离审核 metadata |
| `skills/researching-industry-chains/src/industry_chain_skills/dataset.py` | Modify | 暴露可在现有事务中复用的“把 records 插入正式 source_group”状态级 helper，继续承担九字段与重复校验 |
| `skills/researching-industry-chains/src/industry_chain_skills/runner.py` | Modify | 新增 `awaiting_review`、`auto_phase_finished`、`review_items` 初始化和 topic 终态派生 helper |
| `skills/researching-industry-chains/src/industry_chain_skills/review.py` | Create | review_item 模型、人工 approve/return/reject、review claim 校验、version 冲突 |
| `skills/researching-industry-chains/src/industry_chain_skills/work.py` | Create | 统一领取 topic/review work、优先级、work done/fail 和租约恢复 |
| `skills/researching-industry-chains/src/industry_chain_skills/source_service.py` | Create | 根据当前 work context 接收完整 SourceResult，并原子路由到正式来源或同一个 review_item |
| `skills/researching-industry-chains/src/industry_chain_skills/cli.py` | Modify | Agent-facing `work` / `source` 命令；保留 runner、identity、dataset 管理能力 |
| `skills/researching-industry-chains/tests/test_source_result.py` | Create | SourceResult 与 Tree 编译纯单元测试 |
| `skills/researching-industry-chains/tests/test_dataset_state_insert.py` | Create | 正式来源状态级插入 helper 回归测试 |
| `skills/researching-industry-chains/tests/test_runner_hitl.py` | Create | topic 新字段、awaiting_review、终态派生测试 |
| `skills/researching-industry-chains/tests/test_review_service.py` | Create | Human review 状态机、version、approve 原子写入测试 |
| `skills/researching-industry-chains/tests/test_work_service.py` | Create | work 优先级、claim、done、fail、过期恢复测试 |
| `skills/researching-industry-chains/tests/test_source_service.py` | Create | topic/review 两种 work 下 accept/review 路由测试 |
| `skills/researching-industry-chains/tests/test_hitl_integration.py` | Create | Runner JSON + XLSX 端到端业务闭环 |
| `AGENTS.md` | Modify | 更新稳定职责边界和状态合同 |
| `skills/researching-industry-chains/SKILL.md` | Modify | 从九字段生成器改为 SourceResult 研究协议 |
| `README.md` | Modify | 更新当前 CLI 与产品架构 |
| `USAGE.md` | Modify | 更新当前 Agent 执行闭环和 Human review 入口说明 |

---

### Task 1: 建立 SourceResult 与 Tree→九字段纯领域层

**Files:**
- Create: `skills/researching-industry-chains/src/industry_chain_skills/source_result.py`
- Create: `skills/researching-industry-chains/tests/test_source_result.py`

**Interfaces:**
- Consumes: Agent 提交的 `dict` SourceResult、Runner 中的正式 topic 名称。
- Produces:
  - `validate_source_result(payload: dict) -> dict`
  - `strip_uncertainties(chain: list[dict]) -> list[dict]`
  - `compile_tree_records(topic_name: str, source: dict, description: str, chain: list[dict]) -> list[dict[str, str]]`
  - `iter_uncertainties(payload: dict) -> Iterator[tuple[tuple[str, ...], str | None, dict]]`

- [ ] **Step 1: 写 accept/review 最小合同的失败测试**

```python
class SourceResultValidationTests(unittest.TestCase):
    def test_accept_rejects_any_uncertainty(self) -> None:
        payload = {
            "outcome": "accept",
            "source": {"name": "示例研究院", "url": "https://example.com/a"},
            "description": "来源完整展示产业链。",
            "chain": [{"name": "上游", "uncertainties": [{"message": "仍不确定"}]}],
        }
        with self.assertRaises(ClientError) as caught:
            validate_source_result(payload)
        self.assertEqual("SOURCE_RESULT_ACCEPT_HAS_UNCERTAINTY", caught.exception.code)

    def test_review_requires_at_least_one_uncertainty(self) -> None:
        payload = {
            "outcome": "review",
            "source": {"name": "示例研究院", "url": "https://example.com/a"},
            "description": "需要人工确认。",
            "chain": [{"name": "上游"}],
        }
        with self.assertRaises(ClientError) as caught:
            validate_source_result(payload)
        self.assertEqual("SOURCE_RESULT_REVIEW_HAS_NO_UNCERTAINTY", caught.exception.code)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_source_result.SourceResultValidationTests -v
```

Expected: FAIL because `industry_chain_skills.source_result` does not exist.

- [ ] **Step 3: 实现稀疏 Tree 与 uncertainty 递归校验**

核心约束按下面的函数边界实现，不使用 LLM/NLP：

```python
def validate_source_result(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ClientError("SOURCE_RESULT_INVALID", "SourceResult 顶层必须是对象")
    if payload.get("outcome") not in ("accept", "review"):
        raise ClientError("SOURCE_RESULT_OUTCOME_INVALID", "outcome 必须是 accept 或 review")
    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != {"name", "url"}:
        raise ClientError("SOURCE_RESULT_SOURCE_INVALID", "source 必须且只能包含 name 和 url")
    if not isinstance(source["name"], str) or not source["name"].strip():
        raise ClientError("SOURCE_RESULT_SOURCE_INVALID", "source.name 不能为空")
    if not isinstance(source["url"], str) or not source["url"].strip():
        raise ClientError("SOURCE_RESULT_SOURCE_INVALID", "source.url 不能为空")
    if not isinstance(payload.get("description"), str) or not payload["description"].strip():
        raise ClientError("SOURCE_RESULT_DESCRIPTION_INVALID", "description 不能为空")
    chain = payload.get("chain")
    if not isinstance(chain, list):
        raise ClientError("SOURCE_RESULT_CHAIN_INVALID", "chain 必须是数组")
    _validate_nodes(chain, depth=1)
    uncertainties = list(iter_uncertainties(payload))
    if payload["outcome"] == "accept" and uncertainties:
        raise ClientError("SOURCE_RESULT_ACCEPT_HAS_UNCERTAINTY", "accept 不允许包含 uncertainty")
    if payload["outcome"] == "accept" and not chain:
        raise ClientError("SOURCE_RESULT_ACCEPT_EMPTY_CHAIN", "accept 的 chain 不能为空")
    if payload["outcome"] == "review" and not uncertainties:
        raise ClientError("SOURCE_RESULT_REVIEW_HAS_NO_UNCERTAINTY", "review 至少需要一个 uncertainty")
    return copy.deepcopy(payload)
```

节点允许字段只包括 `name`、`companies`、`children`、`uncertainties`；Evidence 允许字段只包括 `locator`、`description`。`company` uncertainty 必须能在当前节点 `companies` 中找到同名企业。

- [ ] **Step 4: 增加四层深度、企业 occurrence 和 Evidence 测试**

```python
def test_fifth_level_is_rejected(self) -> None:
    chain = [{"name": "1", "children": [{"name": "2", "children": [{"name": "3", "children": [{"name": "4", "children": [{"name": "5"}]}]}]}]}]
    with self.assertRaises(ClientError) as caught:
        compile_tree_records("锡膏", {"name": "研究院", "url": "https://example.com/a"}, "说明", chain)
    self.assertEqual("TREE_DEPTH_EXCEEDED", caught.exception.code)

def test_company_uncertainty_must_reference_current_node_company(self) -> None:
    payload = review_payload(
        chain=[{
            "name": "锡粉",
            "companies": ["甲公司"],
            "uncertainties": [{"company": "乙公司", "message": "归属不清"}],
        }]
    )
    with self.assertRaises(ClientError) as caught:
        validate_source_result(payload)
    self.assertEqual("UNCERTAINTY_COMPANY_NOT_IN_NODE", caught.exception.code)
```

- [ ] **Step 5: 实现 Tree→九字段 DFS 编译**

```python
def compile_tree_records(topic_name: str, source: dict, description: str, chain: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def visit(node: dict, path: tuple[str, ...]) -> None:
        current = (*path, node["name"].strip())
        if len(current) > 4:
            raise ClientError("TREE_DEPTH_EXCEEDED", "产业链正式分类最多支持 4 层")
        categories = list(current) + [""] * (4 - len(current))
        rows.append({
            "主题": topic_name,
            "信源主体": source["name"].strip(),
            "分类1": categories[0],
            "分类2": categories[1],
            "分类3": categories[2],
            "分类4": categories[3],
            "公司": "、".join(node.get("companies", [])),
            "信源URL": source["url"].strip(),
            "备注": "",
        })
        for child in node.get("children", []):
            visit(child, current)

    for root in chain:
        visit(root, ())
    if rows:
        rows[0]["备注"] = description.strip()
    return rows
```

`strip_uncertainties()` 递归复制 Tree，只保留 `name/companies/children`，供 Human approve 后形成正式业务 Tree。

- [ ] **Step 6: 运行纯领域测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_source_result -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/source_result.py skills/researching-industry-chains/tests/test_source_result.py
git commit -m "feat(hitl): add source result compiler"
```

---

### Task 2: 让 DatasetService 的正式来源插入能力可在同一事务中复用

**Files:**
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/dataset.py`
- Create: `skills/researching-industry-chains/tests/test_dataset_state_insert.py`

**Interfaces:**
- Consumes: 已编译的 `{"records": [...]}` 和当前内存 state/topic。
- Produces: `DatasetService.insert_source_group_in_state(state: dict, topic: dict, payload: dict, timestamp: str) -> dict`。

- [ ] **Step 1: 写状态级插入 helper 的失败测试**

```python
def test_insert_source_group_in_state_reuses_duplicate_guard(self) -> None:
    state = make_state_with_existing_source()
    service = DatasetService(MemoryStore(state))
    topic = state["topics"][0]
    with self.assertRaises(ClientError) as caught:
        service.insert_source_group_in_state(
            state,
            topic,
            {"records": duplicate_records()},
            STAMP,
        )
    self.assertEqual("SOURCE_GROUP_DUPLICATE_CONTENT", caught.exception.code)
```

- [ ] **Step 2: 运行测试确认 helper 尚不存在**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_dataset_state_insert -v
```

Expected: FAIL with missing method.

- [ ] **Step 3: 抽出最小状态级正式来源插入逻辑**

在 `DatasetService` 中加入：

```python
def insert_source_group_in_state(
    self,
    state: dict,
    topic: dict,
    payload: dict,
    timestamp: str,
) -> dict:
    records = _validate_source_group_for_topic(topic, payload)
    group = self._new_group(records, timestamp)
    topic["source_groups"].append(group)
    ordered = self._ordered_groups(state)
    self._renumber(ordered)
    return group
```

然后把现有 `insert(... scope="source_group" ...)` 的“追加到末尾”分支改为调用此 helper；`before_id/after_id` 的人工精确插入能力仍走现有位置逻辑，不删除。

- [ ] **Step 4: 增加全局 order 与旧接口回归测试**

验证：已有 source_group order 不变、新 group 追加到全局末尾、旧 `DatasetService.insert()` 重复检测行为不变。

- [ ] **Step 5: 运行 Dataset 测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_dataset_duplicates tests.test_dataset_state_insert -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/dataset.py skills/researching-industry-chains/tests/test_dataset_state_insert.py
git commit -m "refactor(dataset): expose atomic source insertion"
```

---

### Task 3: 扩展 Runner topic 状态与终态派生

**Files:**
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/runner.py`
- Create: `skills/researching-industry-chains/tests/test_runner_hitl.py`

**Interfaces:**
- Produces:
  - `OPEN_REVIEW_STATUSES = {"pending_review", "returned_to_agent", "in_agent"}`
  - `refresh_topic_status(topic: dict) -> str`
  - 新 topic 字段 `auto_phase_finished: bool`、`review_items: list`
  - topic 状态新增 `awaiting_review`

- [ ] **Step 1: 写新 Runner 初始状态失败测试**

```python
def test_new_topic_initializes_hitl_fields(self) -> None:
    result = service.create("锡膏", topic="锡膏")
    state = store.read(result["runner_id"])
    topic = state["topics"][0]
    self.assertFalse(topic["auto_phase_finished"])
    self.assertEqual([], topic["review_items"])
```

- [ ] **Step 2: 写终态派生表测试**

```python
def test_finished_topic_with_open_review_becomes_awaiting_review(self) -> None:
    topic = make_topic(auto_phase_finished=True, source_groups=[], review_status="pending_review")
    self.assertEqual("awaiting_review", refresh_topic_status(topic))

def test_finished_topic_with_source_and_no_open_review_completes(self) -> None:
    topic = make_topic(auto_phase_finished=True, source_groups=[{"source_group_id": "source_1"}], review_status="approved")
    self.assertEqual("completed", refresh_topic_status(topic))
```

同时覆盖 `no_qualified_source`。

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_runner_hitl -v
```

Expected: FAIL.

- [ ] **Step 4: 实现状态枚举与纯派生 helper**

```python
STATUSES = (
    "pending",
    "in_progress",
    "awaiting_review",
    "completed",
    "no_qualified_source",
    "failed",
)
OPEN_REVIEW_STATUSES = {"pending_review", "returned_to_agent", "in_agent"}


def refresh_topic_status(topic: dict) -> str:
    if not topic.get("auto_phase_finished"):
        return topic["status"]
    has_open_review = any(
        item["status"] in OPEN_REVIEW_STATUSES
        for item in topic.get("review_items", [])
    )
    if has_open_review:
        topic["status"] = "awaiting_review"
    elif topic.get("source_groups"):
        topic["status"] = "completed"
    else:
        topic["status"] = "no_qualified_source"
    return topic["status"]
```

Runner 创建 topic 时显式加入 `auto_phase_finished=False` 和 `review_items=[]`。

- [ ] **Step 5: 更新 Runner status 统计测试**

确认 `counts` 包含 `awaiting_review`，`next_topic` 不把 `awaiting_review` 当成普通 pending。

- [ ] **Step 6: 运行测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_runner_hitl -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/runner.py skills/researching-industry-chains/tests/test_runner_hitl.py
git commit -m "feat(hitl): add awaiting review topic state"
```

---

### Task 4: 实现 ReviewService 与 Human review 状态机

**Files:**
- Create: `skills/researching-industry-chains/src/industry_chain_skills/review.py`
- Create: `skills/researching-industry-chains/tests/test_review_service.py`
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/dataset.py` only if a tiny public helper signature from Task 2 needs reuse; do not duplicate Dataset validation.

**Interfaces:**
- `ReviewService.create_in_state(topic: dict, source_result: dict, timestamp: str) -> dict`
- `ReviewService.replace_from_agent_in_state(review: dict, source_result: dict, timestamp: str) -> dict`
- `ReviewService.approve(runner_id: str, review_id: str, expected_version: int, description: str, chain: list[dict]) -> dict`
- `ReviewService.return_to_agent(runner_id: str, review_id: str, expected_version: int) -> dict`
- `ReviewService.reject(runner_id: str, review_id: str, expected_version: int) -> dict`
- `find_review(state: dict, review_id: str) -> tuple[dict, dict]`

- [ ] **Step 1: 写 review_item 轻量模型失败测试**

期望 shape：

```python
{
    "review_item_id": "review_...",
    "order": 1,
    "status": "pending_review",
    "version": 1,
    "created_at": STAMP,
    "updated_at": STAMP,
    "source": {"name": "研究院", "url": "https://example.com/a"},
    "description": "来源说明",
    "chain": [...],
    "uncertainties": [...],
    "agent_claim": None,
    "events": [...],
}
```

不持久化 `draft_records`、`draft_tree`、`focus_item_id`、`evidence_id`、`stage`、`reason`。

- [ ] **Step 2: 写 version conflict 与 chain=[] approve 失败测试**

```python
def test_approve_rejects_stale_version(self) -> None:
    with self.assertRaises(ClientError) as caught:
        service.approve("runner_test", "review_1", 2, "最终说明", valid_chain())
    self.assertEqual("REVIEW_VERSION_CONFLICT", caught.exception.code)

def test_empty_chain_cannot_be_approved(self) -> None:
    with self.assertRaises(ClientError) as caught:
        service.approve("runner_test", "review_1", 3, "最终说明", [])
    self.assertEqual("REVIEW_EMPTY_CHAIN", caught.exception.code)
```

- [ ] **Step 3: 实现 create/replace/find/version helper**

`replace_from_agent_in_state()` 必须更新同一个 `review_item_id`，把最新 `source/description/chain/uncertainties` 作为完整快照替换，`status=pending_review`、`agent_claim=None`、`version += 1`。

- [ ] **Step 4: 实现 approve 原子正式写入**

伪代码必须保持同一个 `mutate_dataset()`：

```python
def approve(...):
    now = self._now()
    def mutation(state: dict) -> dict:
        topic, review = find_review(state, review_id)
        _require_version(review, expected_version)
        if review["status"] != "pending_review":
            raise ClientError("REVIEW_ACTION_NOT_ALLOWED", "当前审核状态不能通过")
        clean_chain = strip_uncertainties(chain)
        records = compile_tree_records(topic["主题"], review["source"], description, clean_chain)
        group = self.dataset.insert_source_group_in_state(
            state, topic, {"records": records}, now.isoformat()
        )
        review["status"] = "approved"
        review["description"] = description
        review["chain"] = clean_chain
        review["version"] += 1
        review["updated_at"] = now.isoformat()
        refresh_topic_status(topic)
        state["updated_at"] = now.isoformat()
        return {"review": copy.deepcopy(review), "source_group": copy.deepcopy(group)}
    return self.store.mutate_dataset(runner_id, mutation)
```

如果重复来源、XLSX 被占用或 Tree 校验失败，整个 review 状态和 source_group 都不能半提交。

- [ ] **Step 5: 实现 return/reject**

`return_to_agent`：只允许 `pending_review`，校验 expected_version，设 `returned_to_agent`，清空 `agent_claim`，`version += 1`。同一 version 因状态变化不能再次 return。

`reject`：设 `rejected`、`version += 1`、不写 XLSX，然后 `refresh_topic_status(topic)`。

- [ ] **Step 6: 运行 ReviewService 测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_review_service -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/review.py skills/researching-industry-chains/tests/test_review_service.py
git commit -m "feat(hitl): add human review service"
```

---

### Task 5: 实现统一 WorkService、review 优先领取和自动阶段结束

**Files:**
- Create: `skills/researching-industry-chains/src/industry_chain_skills/work.py`
- Create: `skills/researching-industry-chains/tests/test_work_service.py`
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/runner.py`
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/review.py`

**Interfaces:**
- `WorkService.claim_next(runner_id: str, worker_label: str | None = None) -> dict`
- `WorkService.done(runner_id: str, work_id: str, claim_token: str) -> dict`
- `WorkService.fail(runner_id: str, work_id: str, claim_token: str, code: str, message: str) -> dict`
- claim response shape：

```python
{
    "work_type": "topic" | "review",
    "work_id": "node_0001" | "review_ab12cd",
    "claim_token": "...",
    "lease_expires_at": "...",
    "topic": {"node_id": "node_0001", "主题": "锡膏", "path": ["锡膏"], "aliases": []},
    "review": None | {"source": {...}, "description": "...", "chain": [...], "uncertainties": [...]},
}
```

- [ ] **Step 1: 写领取优先级失败测试**

```python
def test_returned_review_is_claimed_before_pending_topic(self) -> None:
    state = state_with_returned_review_and_pending_topic()
    work = service.claim_next("runner_test", "Codex")
    self.assertEqual("review", work["work_type"])
    self.assertEqual("review_1", work["work_id"])
```

- [ ] **Step 2: 写 topic done 派生状态测试**

```python
def test_topic_done_with_open_review_becomes_awaiting_review(self) -> None:
    work = claim_topic()
    result = service.done("runner_test", work["work_id"], work["claim_token"])
    self.assertEqual("awaiting_review", result["topic"]["status"])
```

另测：无 review + 有 source → completed；无 review + 无 source → no_qualified_source；review work 调 `done` → `WORK_DONE_NOT_ALLOWED`。

- [ ] **Step 3: 实现原子 claim-next**

同一 `store.mutate_state()` 内按以下优先级选一个：

```text
1. returned_to_agent review
2. lease 已过期的 in_agent review
3. lease 已过期的 in_progress topic
4. pending topic
```

review claim 写 `agent_claim` 并设 `status=in_agent`；topic claim 继续使用 `claim` 并设 `status=in_progress`。`worker_label` 只作为 claim 中可选观察字段，不参与业务判断。

- [ ] **Step 4: 实现 work done**

仅 topic work：校验有效 topic claim，设置：

```python
topic["auto_phase_finished"] = True
topic["claim"] = None
refresh_topic_status(topic)
```

Agent 不传 `completed/no_qualified_source` outcome。

- [ ] **Step 5: 实现 work fail**

- topic work：设 `failed`，释放 topic claim，保存 `last_error`。
- review work：释放 `agent_claim`，回到 `returned_to_agent`，保存一条 review event 与简短 `last_error`，不新增 `failed` review 状态。

来源资格失败、候选无关或重复来源都不是 `work fail`。

- [ ] **Step 6: 运行 WorkService 测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_work_service -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/work.py skills/researching-industry-chains/src/industry_chain_skills/runner.py skills/researching-industry-chains/src/industry_chain_skills/review.py skills/researching-industry-chains/tests/test_work_service.py
git commit -m "feat(hitl): add unified work scheduler"
```

---

### Task 6: 实现 source submit 的完整 SourceResult 路由

**Files:**
- Create: `skills/researching-industry-chains/src/industry_chain_skills/source_service.py`
- Create: `skills/researching-industry-chains/tests/test_source_service.py`

**Interfaces:**
- `SourceService.submit(runner_id: str, work_id: str, claim_token: str, payload: dict) -> dict`
- 返回：

```python
{"result": "accepted", "source_group_id": "source_..."}
```

或：

```python
{"result": "queued_for_review", "review_item_id": "review_...", "version": 1}
```

- [ ] **Step 1: 写 topic work 四种关键行为测试**

覆盖：

```text
topic + accept → source_group + XLSX transaction path
topic + review → 新 review_item，不写 source_group
topic + accept/review 成功 → topic claim 续租，不结束 topic
topic + invalid SourceResult → state 完全不变
```

- [ ] **Step 2: 写 review work 重用同一 review_item 测试**

```python
def test_review_work_review_result_reuses_same_item(self) -> None:
    before_id = "review_1"
    result = service.submit("runner_test", before_id, claim_token, review_payload())
    self.assertEqual("queued_for_review", result["result"])
    self.assertEqual(before_id, result["review_item_id"])
```

再测 review work + accept → 原 review approved + 正式来源 + topic 终态刷新。

- [ ] **Step 3: 实现 work context 解析和 claim 校验**

按 `work_id` 前缀和 state 查找：`node_...` 解析为 topic，`review_...` 解析为 review；必须同时校验对应 claim token。不存在或 claim 不匹配返回稳定业务错误，不让 Agent传额外 `work_type`。

- [ ] **Step 4: 实现 topic + accept/review 两条事务**

`accept` 使用 `mutate_dataset()`：验证 SourceResult、编译 records、调用 Task 2 helper、续 topic claim。

`review` 使用 `mutate_state()`：验证 SourceResult、创建 review_item、续 topic claim。topic 继续 `in_progress`，`auto_phase_finished` 仍为 false。

- [ ] **Step 5: 实现 review + accept/review 两条事务**

`accept`：同一 `mutate_dataset()` 中验证 review claim、编译正式 Tree、插入 source_group、把原 review 设 approved、清 claim、version+1、刷新 topic 状态。

`review`：同一 `mutate_state()` 中把 SourceResult 作为**完整快照**替换原 review 的 source/description/chain/uncertainties，设 pending_review、清 claim、version+1；不创建第二个 review_item。

- [ ] **Step 6: 运行 SourceService 测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_source_service -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/source_service.py skills/researching-industry-chains/tests/test_source_service.py
git commit -m "feat(hitl): route source results by work context"
```

---

### Task 7: 把 CLI 收敛为 Agent-facing work/source 协议

**Files:**
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/cli.py`
- Modify: `skills/researching-industry-chains/tests/test_local_cli_launcher.py`
- Create: `skills/researching-industry-chains/tests/test_hitl_cli.py`

**Interfaces:**
- Agent-facing commands：

```text
industry-chain work claim-next --runner-id RUNNER [--worker-label Codex]
industry-chain source submit --runner-id RUNNER --work-id WORK --claim-token TOKEN --input RESULT.json
industry-chain work done --runner-id RUNNER --work-id WORK --claim-token TOKEN
industry-chain work fail --runner-id RUNNER --work-id WORK --claim-token TOKEN --code CODE --message MESSAGE
```

- 保留 `identity`、`runner`、`topic search|get`、`dataset get|insert|patch|replace|remove` 作为人工/维护入口。
- 移除 Agent 主流程中的 `topic claim-next|claim|renew|finish|fail` parser，避免两套调度协议并存。

- [ ] **Step 1: 写 CLI parser 失败测试**

```python
def test_work_and_source_commands_are_exposed(self) -> None:
    parser = build_parser()
    args = parser.parse_args(["work", "claim-next", "--runner-id", "runner_test"])
    self.assertEqual("work", args.command)
    self.assertEqual("claim-next", args.action)
```

- [ ] **Step 2: 写本地 launcher 端到端 CLI 测试**

测试流程：创建单主题 Runner → `work claim-next` → 把一个 accept JSON 通过 stdin 交给 `source submit` → `work done` → runner status 显示 completed。

- [ ] **Step 3: 修改 parser 与 dispatch**

实例化：

```python
review = ReviewService(store)
work = WorkService(store)
source = SourceService(store)
```

`source submit` 继续复用 `_read_input()`，标准输出仍保持：

```json
{"ok": true, "data": {}}
```

业务错误仍是：

```json
{"ok": false, "error": {"code": "...", "message": "..."}}
```

- [ ] **Step 4: 确认 review work 不需要 work done**

CLI 集成测试：人工 return 后 `work claim-next` 返回 review；一次 `source submit review` 之后该 claim 已释放并回 pending_review；调用 `work done` 应失败。

- [ ] **Step 5: 运行 CLI 测试**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_hitl_cli tests.test_local_cli_launcher -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/cli.py skills/researching-industry-chains/tests/test_hitl_cli.py skills/researching-industry-chains/tests/test_local_cli_launcher.py
git commit -m "feat(cli): add work and source commands"
```

---

### Task 8: 做 Runner JSON + XLSX 的端到端原子性验收

**Files:**
- Create: `skills/researching-industry-chains/tests/test_hitl_integration.py`
- Modify production files only when this test exposes a real contract bug; do not add new architecture to satisfy the test.

**Interfaces:**
- Consumes: Tasks 1–7 的真实 `RunnerStore/RunnerService/WorkService/SourceService/ReviewService`。
- Produces: 可证明 SourceResult→review→Human→XLSX 的真实业务闭环。

- [ ] **Step 1: 写完整 happy path**

测试使用 `tempfile.TemporaryDirectory()`：

```text
create Runner(锡膏)
→ claim topic
→ submit accept 来源 A
→ submit review 来源 B
→ submit accept 来源 C
→ work done
→ topic = awaiting_review
→ Human return B
→ claim-next 得到 B review
→ Agent submit accept B
→ topic = completed
```

- [ ] **Step 2: 验证 XLSX 在 review 未批准前没有 B**

使用 openpyxl 读取 `<runner_id>_交付数据.xlsx`：只应看到 A/C 对应 rows；B 的 description/Tree 不得泄漏进交付表。

- [ ] **Step 3: 验证 review 批准后九字段投影**

断言：

```text
headers == 9 个固定业务列
父节点行先于子节点
同节点企业 == "甲公司、乙公司"
只有来源组第一行备注 == final description
URL cell 有 hyperlink
```

- [ ] **Step 4: 写 chain=[] review + reject 场景**

若 topic 没有其它正式来源：`review(chain=[]) → work done → awaiting_review → reject → no_qualified_source`，XLSX 只有表头。

- [ ] **Step 5: 写原子失败场景**

构造两个 review 最终批准为同 URL/同内容来源，第二次 approve 触发 `SOURCE_GROUP_DUPLICATE_*`；断言失败后第二 review 仍未 approved，正式 source_group 数量和 XLSX 行数不变。

- [ ] **Step 6: 运行完整 Python 测试集**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/tests/test_hitl_integration.py
git commit -m "test(hitl): cover source review xlsx flow"
```

---

### Task 9: 把 Skill 与公开文档切到当前 SourceResult 合同

**Files:**
- Modify: `AGENTS.md`
- Modify: `skills/researching-industry-chains/SKILL.md`
- Modify: `README.md`
- Modify: `USAGE.md`

**Interfaces:**
- Consumes: 已实现的 CLI `work/source` 合同。
- Produces: 没有旧行为、迁移说明或版本历史的当前文档。

- [ ] **Step 1: 更新 AGENTS.md 稳定边界**

必须改掉当前与批准 spec 冲突的规则：

```text
Agent 生成九字段 → Agent 生成 SourceResult Tree
Client 只接受 records → Client 编译 Tree 并复用九字段 Dataset 校验
topic 状态无 awaiting_review → 加 awaiting_review
超过四级合并到分类4 → 超过四级拒绝 SourceResult/人工 Tree
Runner 只有 source_groups → topic 还包含 review_items + auto_phase_finished
```

继续保留来源资格、视觉证据、一文一链、企业直接归属和九字段最终交付约束。

- [ ] **Step 2: 重写 SKILL.md 的“单来源输出与提交”部分**

Agent 运行时只需要记住：

```text
明确不合格 → 跳过
可靠闭环 → source submit outcome=accept
有价值但无法可靠闭环 → source submit outcome=review
topic 搜索完成 → work done
```

删除“建立 records 清单、手工填分类1~4、手工 dataset insert、手工 topic finish outcome”的 Agent 指令。保留来源扫描、Source Probe、视觉读图、企业归属和搜索停止规则。

SourceResult 示例必须用当前稀疏 Tree：

```json
{
  "outcome": "accept",
  "source": {"name": "示例研究院", "url": "https://example.com/report"},
  "description": "该来源完整展示上游原材料和中游制造，并列出直接对应企业。",
  "chain": [
    {"name": "上游", "children": [{"name": "锡粉", "companies": ["甲公司", "乙公司"]}]}
  ]
}
```

- [ ] **Step 3: 更新 README.md 当前命令列表**

Agent 主流程写成：

```text
work claim-next
source submit
work done / work fail
```

同时说明 `dataset` 是低层人工精确维护接口，最终 XLSX 仍固定九列。

- [ ] **Step 4: 更新 USAGE.md 真实使用闭环**

至少给出：创建 Runner、claim topic、accept source、review source、topic done、Human return 后重新 claim review 的完整示例。文档不记录“以前怎么做”。

- [ ] **Step 5: 运行文档合同检查**

Run:

```bash
python - <<'PY'
from pathlib import Path
skill = Path('skills/researching-industry-chains/SKILL.md').read_text(encoding='utf-8')
assert 'source submit' in skill
assert 'work claim-next' in skill
assert 'work done' in skill
assert '生成九字段 records' not in skill
assert 'dataset insert --runner-id' not in skill
print('docs contract ok')
PY
```

Expected: `docs contract ok`.

- [ ] **Step 6: 跑全量回归**

Run:

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest discover -s tests -v
python run_cli.py --help
python run_cli.py work --help
python run_cli.py source --help
```

Expected: tests PASS; help 中存在当前 work/source 命令。

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md README.md USAGE.md skills/researching-industry-chains/SKILL.md
git commit -m "docs(hitl): switch agent workflow to source results"
```

---

## Final Verification

- [ ] 从干净 checkout 安装 editable package：

```bash
python -m pip install -e ./skills/researching-industry-chains
```

- [ ] 运行完整测试：

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest discover -s tests -v
```

- [ ] 运行最小 CLI smoke：

```bash
python run_cli.py --runs-root /tmp/industry-chain-hitl-smoke runner create --name smoke --topic 锡膏
```

从响应取 runner_id 后执行 `work claim-next`；用一个两层 accept SourceResult 调 `source submit`；最后 `work done`，再 `runner status`。期望 topic 为 completed，Runner 目录只有 `runner.json` 与交付 XLSX，没有 screenshot/evidence 目录。

- [ ] 打开 XLSX，确认只有九个业务列，备注来自 SourceResult.description。
- [ ] 确认明确不合格候选没有对应 Runner 对象或 reject review。
- [ ] 确认 `review(chain=[])` 不写 XLSX且可以被 return/reject。
- [ ] 确认同一个 review 被 Agent 再次提交时只增加 version，不产生第二个 review_item。
