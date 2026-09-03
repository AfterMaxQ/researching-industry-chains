# 产业链 Agent Human-in-the-loop 审核系统设计文档 v1

## 1. 文档目的

本文定义 `researching-industry-chains` 项目的 Human-in-the-loop（HITL）审核子系统 v1。

目标不是把现有产业链 Skill 改造成“所有结果都要人工确认”的半自动系统，而是在保留当前自动化能力的前提下，为 Agent 无法可靠闭环的边界来源提供一个明确、可恢复、可人工修正的处理通道。

核心原则：

> 正常来源继续自动通过；只有 Agent 主动判断为 `needs_review` 的边界来源进入人工审核。

审核不是异常兜底页，而是正式业务流程的一部分。

---

## 2. 背景与问题

现有 Skill 已能处理多种常见来源：

- 普通网页正文；
- 网页产业链图片；
- PDF；
- 表格；
- 多张图；
- 正文补充；
- 企业归属；
- 节点和企业覆盖；
- 图文关系与冲突。

但未来来源不可能被提前穷举。

典型例子是：

`https://chipexplorer.eto.tech/`

该页面不是普通文章，也没有一张完整的产业链图或静态表格。其核心信息通过交互式 Supply Chain Explorer 展示，Agent 必须实际使用浏览器点击不同节点，观察页面状态变化，逐步获取完整产业链信息。

如果系统只按“网页 / 图片 / PDF / 表格”等固定解析类型工作，就会不断增加特例，并且仍然无法覆盖新型数据源。

因此 v1 不把问题定义为：

> 这个来源属于哪一种已知 parser type？

而定义为：

> Agent 能否自主发现取得完整来源证据所需要的能力和操作，并可靠完成该 Retrieval Plan？

---

## 3. 设计目标

v1 需要解决以下问题：

1. Agent 能识别自己是否已经可靠完成当前来源，而不是被迫输出答案。
2. Agent 遇到新型来源时，应先主动探索，而不是因为“没见过”就立即送人工。
3. 只有真正无法可靠闭环、且人工介入有机会解决的问题才进入审核。
4. 人工审核对象是一篇来源 / 一个来源工作单元，而不是 Excel 单行。
5. 人工能够直接修正 Agent 草稿，包括新增 Agent 完全遗漏的节点和企业。
6. 人工认为“这里其实不需要人工判断”时，可以把当前 URL 一次性交回 Agent 继续。
7. 人工退回来源必须能重新被 Codex、Claude Code、Trae 等主窗口 Agent 领取并继续处理。
8. 调度、队列、状态机、租约和持久化全部由 CLI 负责，Agent 不自行调度。
9. Runner JSON 继续作为事实源；XLSX 继续作为正式九字段交付投影。
10. 不因为加入审核系统而引入数据库、消息队列、独立 Review DB、长期 Memory 或复杂 Agent SDK。

---

## 4. 非目标

v1 明确不做：

- 所有自动结果都进入人工审核；
- 自动学习并直接修改 `SKILL.md`；
- 一次人工放行自动升级为整个域名白名单；
- 独立数据库 / 向量数据库 / 审核数据库；
- 完整审计平台；
- 置信度打分体系；
- Parser 类型注册中心；
- 模型调用记录、token 统计、完整推理过程持久化；
- 自动根据人工修改重训模型；
- 人工审核结果被未来 AI 自动覆盖；
- 为 Codex / Claude Code / Trae 分别维护业务实现分支。

v1 只解决：**Agent 边界来源 → 人工判断 → 必要时返回 Agent → 最终正式数据**。

---

## 5. 总体架构

系统分为四个职责明确的部分。

```text
┌─────────────────────────────┐
│ CLI / Runner                │
│ 调度、状态机、租约、持久化 │
└──────────────┬──────────────┘
               │ 领取 Work Item
               ▼
┌─────────────────────────────┐
│ Agent                       │
│ Codex / Claude Code / Trae  │
│ 按 Skill 执行业务任务       │
└──────────────┬──────────────┘
               │ 事实与结果
               ▼
┌─────────────────────────────┐
│ Runner JSON                 │
│ source_groups + review_items│
└──────────────┬──────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ Web 审核端   │  │ XLSX         │
│ 人工决策     │  │ 正式数据投影 │
└──────────────┘  └──────────────┘
```

职责定义：

- **CLI**：流水线调度器、状态机、租约管理器、持久化入口。
- **Agent**：无状态执行器，只处理 CLI 当前领取的工作。
- **Skill**：定义 Agent 如何搜索、Probe、解析、判断是否需要审核。
- **Web 审核端**：只负责展示与提交人工业务动作，不自行维护 Runner 状态机。
- **Runner JSON**：唯一任务事实源。
- **XLSX**：只包含正式 `source_groups` 的九字段交付投影。

---

## 6. 核心架构原则

### 6.1 Agent 报告事实，CLI 推导状态

Agent 不应该决定：

- 下一项任务是谁；
- `returned_to_agent` 是否比普通 topic 优先；
- topic 是否应该进入 `awaiting_review`；
- topic 是否可以 `completed`；
- review_item 应切换到哪个内部状态。

Agent 只执行业务动作，例如：

- 提交正式来源；
- 提交 `needs_review`；
- 完成当前自动阶段；
- 完成人工退回来源；
- 报告当前 work 失败。

状态转换由 CLI Service 完成。

### 6.2 source_groups 与 review_items 严格分离

`source_groups` 表示已经成为正式交付数据的来源。

`review_items` 表示尚未成为正式数据、需要人工或再次 Agent 处理的来源。

因此：

> 未审核的来源不得提前写入正式 `source_groups`。

这保证 XLSX 永远只投影正式数据。

### 6.3 人工审核单位是来源，不是 Excel 行

一个来源对应：

```text
文章 / PDF / Explorer
        ↓
产业链结构
        ↓
节点
        ↓
企业归属
        ↓
多行九字段 records
```

因此审核主对象必须是 `review_item` / 来源级工作单元。

九字段 records 是数据协议，不是主要审核心智模型。

### 6.4 人工是最终编辑者

人类不仅能确认 AI 草稿，还可以：

- 修改节点名称；
- 修改父子关系；
- 新增节点；
- 删除节点；
- 新增 Agent 完全未发现的企业；
- 删除错误企业；
- 调整企业归属；
- 最终提交修正后的来源组。

v1 不限制人工修改必须是 Agent 原草稿的子集。

---

## 7. Source Probe 与 Capability Gate

### 7.1 不使用固定 parser type 驱动

系统不维护以下硬编码逻辑作为核心：

```text
普通网页
图片
PDF
表格
交互式网站
...
```

这些可以是来源表现形式，但不能成为系统能力边界。

### 7.2 Source Probe

Agent 对候选来源首先回答：

> 要取得完整业务证据，我需要做什么？

Probe 可能发现：

- 静态正文已经充分；
- 需要浏览器实际渲染；
- 需要读取图片；
- 需要打开 PDF 指定页面；
- 需要展开折叠区；
- 需要点击节点；
- 需要切换 Tab；
- 需要改变筛选条件；
- 需要遍历多个交互状态。

Agent 根据 Probe 形成 Retrieval Plan，并尝试自主完成。

### 7.3 Capability Contract

只有所有必要条件都可靠满足，来源才自动通过。

| 能力维度 | 自动处理条件 |
| --- | --- |
| 内容获取 | Agent 能找到并执行取得完整业务内容的方法，不限定正文、图片或交互 |
| 普通网页正文 | Agent 能完整读取所需正文 |
| 网页产业链视觉内容 | 浏览器能实际看到并清楚读取 |
| PDF | 能打开相关页并实际视觉读取 |
| 表格 | 节点与企业关系清楚 |
| 多张图 | 来源内部关系明确，可以确定各图用途 |
| 浏览器交互 | 如证据依赖交互，Agent 能识别并稳定操作 |
| 遍历完整性 | Agent 能判断需要访问哪些状态，并确认覆盖完成 |
| 正文补充 | 能明确挂到已有节点 |
| 企业归属 | 有来源内部直接证据 |
| 节点覆盖 | 所有发现节点均已处理 |
| 企业覆盖 | 所有发现企业均已处理 |
| 图文 / 多证据关系 | 不存在无法消解的关键冲突 |

### 7.4 三值判断

Capability Gate 使用三类业务结果：

```text
PASS
FAIL
UNCERTAIN
```

- `PASS`：可以可靠继续并自动完成。
- `FAIL`：已经明确不满足来源准入或不可用条件，直接排除，不浪费人工。
- `UNCERTAIN`：Agent 已主动探索，但关键判断无法可靠闭环，并且人工介入有现实机会解决，进入 `needs_review`。

`needs_review` 不等于“没见过这种网站”。

---

## 8. Chip Explorer 验收案例

`https://chipexplorer.eto.tech/` 作为 v1 的关键 generalized test。

预期 Agent 行为：

```text
打开候选来源
↓
普通正文无法取得完整产业链
↓
不能立即判定“无产业链”
↓
使用浏览器实际查看
↓
发现存在可交互节点
↓
尝试点击
↓
观察点击后业务内容变化
↓
推断该来源需要交互遍历
↓
形成 Retrieval Plan
↓
尝试枚举并处理全部必要状态
```

理想结果是 Agent 自主完成并自动通过。

只有当 Agent 已经理解交互规律，但仍无法可靠确认例如：

- 是否存在未发现的隐藏节点；
- 是否已经遍历完整；
- 某些关键节点关系仍不明确；

才进入 `needs_review`。

Skill 不允许添加：

```text
if domain == chipexplorer.eto.tech:
    使用特殊规则
```

否则该测试失去泛化意义。

---

## 9. Topic 状态机

v1 新增正式 topic 状态：

```text
awaiting_review
```

完整状态：

```text
pending
in_progress
awaiting_review
completed
no_qualified_source
failed
```

语义：

- `pending`：尚未被 Agent 领取。
- `in_progress`：Agent 正在执行主题自动阶段，有 claim / lease。
- `awaiting_review`：Agent 已结束主题自动阶段并释放 claim，但还有未闭环 review_item。
- `completed`：自动处理与人工审核均闭环，且存在正式来源。
- `no_qualified_source`：所有流程闭环后不存在正式来源。
- `failed`：主题自动阶段出现无法继续的执行异常。

状态流：

```text
pending
  ↓ claim
in_progress
  ↓ Agent 完成自动阶段
  ├─ 有 open review_item → awaiting_review
  ├─ 无 open review + 有 source_group → completed
  └─ 无 open review + 无 source_group → no_qualified_source

awaiting_review
  ↓ 最后一个 review_item 闭环
  ├─ 有 source_group → completed
  └─ 无 source_group → no_qualified_source
```

### 9.1 needs_review 不暂停整个主题

如果当前主题：

```text
来源 A → auto pass
来源 B → needs_review
来源 C → auto pass
来源 D → needs_review
来源 E → reject
```

Agent 不因 B 停止整个主题。

正确行为：

```text
B 创建 review_item
↓
继续处理 C / D / E
↓
完成搜索与当前自动阶段
↓
仍有 review_item
↓
主题进入 awaiting_review
```

因此 `needs_review` 是：

> 当前来源暂停。

不是：

> 当前主题暂停。

---

## 10. Topic 数据模型

在现有 topic 基础上新增：

```json
{
  "node_id": "node_0001",
  "主题": "锡膏",
  "path": ["锡膏"],
  "aliases": [],
  "order": 1,

  "status": "awaiting_review",
  "last_error": null,
  "claim": null,

  "auto_phase_finished": true,

  "source_groups": [],
  "review_items": []
}
```

### 10.1 auto_phase_finished

该字段区分两种情况：

1. Agent 已创建 review_item，但主题搜索还在继续；
2. Agent 已完成该主题自动阶段，只剩人工审核。

例如：

```text
status = in_progress
auto_phase_finished = false
review_items > 0
```

表示 Agent 仍需继续搜索和处理其它来源。

Agent 完成当前主题搜索后，只报告“自动阶段结束”。CLI 设置：

```text
auto_phase_finished = true
```

再根据实际 `review_items` 与 `source_groups` 推导 topic 状态。

---

## 11. ReviewItem 数据模型

v1 的 review_item 保持轻量：

```json
{
  "review_item_id": "review_ab12cd",
  "order": 1,

  "status": "pending_review",

  "created_at": "...",
  "updated_at": "...",

  "source": {
    "url": "https://chipexplorer.eto.tech/",
    "source_name": "Emerging Technology Observatory"
  },

  "decision": {
    "stage": "source_navigation",
    "reason": "interaction_scope_uncertain",
    "summary": "该来源需要点击节点取得完整产业链信息，目前无法可靠确认是否已经遍历全部节点。",
    "confirmed": [
      "静态正文不足以还原完整产业链",
      "浏览器中存在可点击产业链节点",
      "点击后页面展示内容发生业务意义变化"
    ],
    "uncertain": [
      "是否已经发现全部必须访问的节点"
    ]
  },

  "focus_items": [],
  "draft_records": [],

  "agent_claim": null,
  "override": null,

  "events": []
}
```

### 11.1 draft_records 可以为空

允许：

```json
"draft_records": []
```

审核队列表示“需要人工决策的来源”，不是“必须已经存在九字段草稿的来源”。

例如 Agent 能判断：

- 页面很可能有价值；
- 页面需要特殊交互；
- 但当前无法可靠形成任何产业链 records；

仍可以创建 review_item。

### 11.2 decision

`decision` 只保留对人工有帮助的结论，不持久化完整思维过程。

建议高层 `stage`：

```text
source_access
source_qualification
source_navigation
visual_parse
structure_parse
company_mapping
coverage_check
evidence_conflict
```

建议高层 `reason` 示例：

```text
visual_unreadable
interaction_scope_uncertain
structure_ambiguous
company_mapping_ambiguous
source_incomplete
evidence_conflict
other
```

这些是内部语义，前端展示应翻译成人话。

### 11.3 focus_items

用于告诉审核员：

> 本次真正需要你判断哪些点。

例如：

```json
[
  {
    "type": "company_mapping",
    "target": "华光新材",
    "message": "无法确认该企业是否直接归属于锡焊膏生产制造"
  }
]
```

它只服务审核体验，不属于正式九字段数据。

### 11.4 不新增独立 draft_tree

v1 不在 Runner 中同时维护：

```text
draft_tree
draft_records
```

避免双事实源。

规则：

```text
draft_records
↓ 前端加载时投影
Tree View
↓ 人工编辑
Tree → records
↓ CLI 校验
正式 source_group
```

---

## 12. ReviewItem 状态机

持久化状态：

```text
pending_review
returned_to_agent
in_agent
approved
rejected
```

状态流：

```text
                   ┌───────────────┐
                   │pending_review │
                   └───────┬───────┘
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
      人工采用         人工修正后采用      交回 Agent
          │                │                 │
          ▼                ▼                 ▼
      approved         approved      returned_to_agent
                                             │
                                             │ work claim
                                             ▼
                                          in_agent
                                             │
                                  ┌──────────┴──────────┐
                                  │                     │
                             Agent成功            新的不确定问题
                                  │                     │
                                  ▼                     ▼
                              approved           pending_review

pending_review
   └─ 人工驳回 → rejected
```

`approved` 表示该 review 工作已经闭环并形成正式业务结果。

如果 Agent 在人工放行后成功完成当前来源，也最终进入 `approved`，不新增 `resolved_by_agent` 状态。

---

## 13. 同一 URL 的重复送审

同一 URL 在同一轮处理中只维护一个 review_item。

例如：

```text
第一次：
interaction_scope_uncertain
↓
人工交回 Agent
↓
Agent继续
↓
出现新的：company_mapping_ambiguous
```

不创建 `review_2`。

而是：

```text
复用原 review_item
↓
更新 decision
↓
status 重新 pending_review
```

旧过程通过 `events` 保留。

### 13.1 极简 events

只记录动作事实，不记录完整推理：

```json
[
  {
    "at": "...",
    "actor": "agent",
    "action": "submitted",
    "reason": "interaction_scope_uncertain"
  },
  {
    "at": "...",
    "actor": "human",
    "action": "returned_to_agent"
  },
  {
    "at": "...",
    "actor": "agent",
    "action": "resubmitted",
    "reason": "company_mapping_ambiguous"
  }
]
```

目的仅是让审核员知道：

> 为什么这篇文章又回来了？

不是建设审计系统。

---

## 14. Human Override

人工认为：

> 这篇来源不需要人在当前问题上判断，Agent 可以继续。

前端动作：

```text
交回 AI 继续
```

CLI 将当前 review_item 设置为：

```text
returned_to_agent
```

并保存一次性 override：

```json
{
  "bypass_reason": "interaction_scope_uncertain",
  "instruction": "人工确认当前来源可以继续自主遍历",
  "created_at": "..."
}
```

### 14.1 Override 范围

只作用于：

```text
当前 review_item
+
当前 URL
+
当前被放行 reason
```

不作用于：

- 同域名其它 URL；
- 未来 Runner；
- 未来任务；
- 其它 review_item；
- 新出现的其它不确定问题。

### 14.2 防止审核死循环

Agent 领取该 review work 后：

> 不得因为同一个 `bypass_reason` 原样再次送审。

但如果出现真正的新问题，例如：

```text
company_mapping_ambiguous
```

仍然可以重新进入 `pending_review`。

旧 override 消费后失效。

---

## 15. 人工审核动作

v1 前端核心只需要四类业务动作。

### 15.1 采用当前结果

适用于 Agent 草稿已经足够可靠。

```text
review approve
↓
校验 draft_records
↓
转为正式 source_group
↓
刷新 Runner / XLSX
```

如果 `draft_records=[]`，该动作不可用。

### 15.2 修正后通过

人工可以修改完整来源结果，包括 Agent 未识别出的节点和企业。

流程：

```text
Tree View 编辑
↓
生成九字段 records
↓
CLI 使用现有 Dataset 确定性规则校验
↓
正式 source_group
↓
review approved
```

### 15.3 交回 AI 继续

含义不是“数据通过”，而是：

> 当前问题不需要人工判断，允许 Agent 对当前 URL 继续探索。

```text
pending_review
↓
returned_to_agent
↓
进入 Agent work queue
```

### 15.4 驳回来源

人认为该来源不应进入正式数据。

```text
pending_review
↓
rejected
```

不写入 `source_groups`，不进入 XLSX。

---

## 16. 审核前端设计原则

### 16.1 第一屏先告诉人“为什么你要看它”

审核卡片优先展示：

```text
需要人工判断：交互遍历范围

AI 已确认：
✓ 静态正文不足
✓ 浏览器存在产业链节点
✓ 节点可点击
✓ 点击后业务内容变化

AI 卡在：
? 无法确认是否已经发现全部节点

本次需要你：
确认是否允许 Agent 继续自主遍历
```

而不是先展示 JSON 或九字段表格。

### 16.2 尽量把人工工作压缩成“决策”

例如 30 个节点中只有 2 个企业归属不确定：

```text
本次只需要确认 2 处
```

前端默认定位到 `focus_items`，而不是要求人从头审完整产业链。

### 16.3 Tree View 为主，九字段为底层协议

审核页面主要展示：

```text
上游
├─ 锡粉
│  └ 康普锡威
├─ 助焊剂

中游
└─ 锡焊膏生产制造
   ├─ 唯特偶
   └─ 华光新材
```

支持：

- 修改节点；
- 新增 / 删除节点；
- 调整父子关系；
- 新增 / 删除企业；
- 修改企业挂载。

提交时转换为当前九字段 records。

### 16.4 无草稿时不展示空编辑器

如果：

```text
draft_records = []
```

页面重点显示来源、AI 已做的探索、当前卡点和：

```text
[交回 AI 继续]
[驳回来源]
```

不强迫用户面对一张空表。

---

## 17. CLI 架构

现有 CLI 包含：

```text
identity
runner
topic
dataset
```

v1 增加两个职责层。

### 17.1 review 命令组

用于审核业务动作与调试：

```text
review list
review get
review submit
review approve
review return-to-agent
review reject
```

原则：

> Agent 和前端只能调用业务动作，不允许直接 patch review 内部状态字段。

也就是说不允许：

```text
dataset patch review.status=approved
```

状态机只能在 ReviewService 内部迁移。

### 17.2 work 命令组

`work` 是 Agent 使用的统一调度 facade，不是新的持久化业务实体。

建议：

```text
work claim-next
work renew
work finish
work fail
```

Agent 主窗口日常只需要：

```text
work claim-next --runner-id ...
```

CLI 返回统一 Work Item。

---

## 18. Work 调度

### 18.1 调度优先级

默认：

```text
1. returned_to_agent review work
2. pending / 可重领 topic work
3. 无 Agent 工作
```

人工已经介入并退回的任务优先闭环，不长期积压在普通 topic 后面。

### 18.2 NO_AGENT_WORK

如果：

- 没有 `returned_to_agent` review；
- 没有可领取 topic；
- 但存在 `pending_review`；

CLI 返回：

```text
NO_AGENT_WORK
runner_status = awaiting_review
```

含义是：

> Agent 当前无需继续工作，系统正在等人。

---

## 19. Unified Work Item

### 19.1 Topic Work

```json
{
  "work_type": "topic",
  "runner_id": "...",
  "node_id": "node_0003",
  "topic": {
    "name": "锡膏",
    "path": ["锡膏"],
    "aliases": []
  },
  "claim_token": "...",
  "lease_expires_at": "..."
}
```

Skill 入口：

```text
完整主题流程
```

包括：

- 搜索；
- Source Probe；
- Retrieval Plan；
- 来源判断；
- 来源级事务；
- 需要时 review submit；
- 搜索饱和；
- 自动阶段结束。

### 19.2 Review Work

```json
{
  "work_type": "review",
  "runner_id": "...",
  "node_id": "node_0003",
  "review_item_id": "review_123",
  "topic": {
    "name": "芯片产业链"
  },
  "source": {
    "url": "https://chipexplorer.eto.tech/"
  },
  "previous_attempt": {
    "stage": "source_navigation",
    "reason": "interaction_scope_uncertain",
    "summary": "..."
  },
  "human_override": {
    "bypass_reason": "interaction_scope_uncertain",
    "instruction": "允许继续自主遍历当前来源"
  },
  "draft_records": [],
  "claim_token": "...",
  "lease_expires_at": "..."
}
```

Skill 入口：

```text
人工退回来源继续流程
```

该流程禁止：

- 重新开放主题搜索；
- 新找其它来源；
- 自行领取别的 topic；
- 忽略 human override；

只处理当前固定 URL。

---

## 20. Agent 主窗口协议

Codex、Claude Code、Trae 不分别实现不同业务流程。

统一要求：

1. 读取当前仓库 `SKILL.md`。
2. 对指定 Runner 调用 CLI `work claim-next`。
3. 根据 `work_type` 选择 Skill 对应入口。
4. 严格只处理当前 Work Item。
5. 将业务结果提交回 CLI。
6. 再领取下一 Work Item。

典型用户操作：

```text
继续处理这个 Runner。
```

Agent 内部：

```text
work claim-next
↓
处理
↓
work finish / fail
↓
work claim-next
↓
...
```

任务状态必须全部存在 Runner 中，不依赖聊天上下文。

因此可以：

```text
Claude Code 跑一半关闭
↓
稍后用 Codex 打开同仓库
↓
继续同一个 Runner
```

新 Agent 从 CLI 恢复工作状态。

---

## 21. Lease 与并发

Topic Work 与 Review Work 都必须支持：

```text
claim_token
claimed_at
lease_expires_at
renew
```

原因：

多个 Codex / Claude Code / Trae 窗口可能同时执行同一个 Runner。

如果 Review Work 无租约，多个 Agent 可能同时处理同一个人工退回 URL。

因此 `work claim-next` 必须原子领取。

Review Work 的 Agent 执行失败应尽量局部化：

- 释放 / 恢复 review work；
- 不因为某个 review work 的浏览器异常直接抹掉已经存在的正式来源；
- topic 仍保持可恢复状态。

---

## 22. 正式数据写入

正式来源只有两条路径进入 `source_groups`。

### 22.1 Agent 自动通过

```text
Source Probe / Parse
↓
Capability Contract PASS
↓
完整 records
↓
dataset source_group insert
↓
source_groups
```

### 22.2 Review 闭环

```text
review_item
↓
人工采用 / 修正后采用
OR
人工退回 Agent 后 Agent 成功完成
↓
完整 records
↓
现有 Dataset 校验
↓
source_groups
```

所有正式数据仍遵守项目原有规则：

- 一文一链；
- 不跨来源融合；
- 九字段约束；
- 来源组 topic 一致；
- 去重规则；
- 公司归属规则；
- 节点层级规则；
- 备注位置规则；
- Runner JSON 与 XLSX 投影规则。

---

## 23. XLSX 行为

XLSX 永远只投影：

```text
source_groups
```

不投影：

```text
pending_review
returned_to_agent
in_agent
```

因此不会发生：

```text
待审核来源先进入交付 Excel
↓
人工发现错误
↓
再删除
```

人工审核最终产生正式来源后，由现有 Runner 数据持久化流程刷新 XLSX。

---

## 24. 前端与 CLI 的职责边界

前端不直接计算状态。

例如人点击：

```text
采用当前结果
```

前端只提交：

```text
review approve
```

CLI 负责：

```text
校验 records
↓
建立 source_group
↓
review → approved
↓
检查该 topic 其它 open review
↓
必要时 topic → completed
↓
刷新 XLSX
```

人点击：

```text
交回 AI 继续
```

前端只提交：

```text
review return-to-agent
```

CLI 负责：

```text
写入一次性 override
↓
review → returned_to_agent
↓
进入 Agent work queue
```

状态 bookkeeping 不暴露给审核员。

---

## 25. v1 推荐代码边界

基于当前项目结构，推荐保持现有职责并增加小而明确的模块。

现有：

```text
runner.py
    topic / runner 生命周期

dataset.py
    正式数据校验与 source_group / row 操作

storage.py
    Runner JSON + XLSX 原子持久化

cli.py
    CLI 命令入口
```

建议新增：

```text
review.py
    ReviewService
    review_item 创建、人工动作、状态转换、override

work.py
    WorkService
    统一 Agent 调度、claim / renew / finish / fail
```

`work.py` 不保存独立 work 数据库，只从 Runner 当前状态推导并领取 topic / review 工作。

前端作为独立薄层调用 CLI / 后续轻量 API，不复制业务状态机。

---

## 26. Skill 需要增加的核心规则

Skill 需要从“尽量给答案”转为：

> 能可靠闭环则自动完成；不能可靠闭环则允许把当前来源交给人。

关键新增：

### 26.1 Source Probe

候选来源不能只做静态正文判断。

Agent 应根据实际页面主动判断：

- 是否需要浏览器；
- 是否存在交互；
- 点击 / 展开是否产生业务数据；
- 是否需要遍历多个页面状态；
- 如何判断遍历结束。

### 26.2 不因“陌生”直接送审

陌生页面首先触发自主探索。

只有自主探索后仍无法形成可靠闭环，才 `needs_review`。

### 26.3 当前来源送审后继续主题

review submit 成功后：

```text
当前来源结束
↓
继续搜索 / 处理其它候选来源
```

不得因为一个 review_item 阻塞整个 topic。

### 26.4 Review Work 严格限定当前 URL

领取 `work_type=review` 后：

- 只处理 CLI 返回的 URL；
- 从上一次卡点继续；
- 执行 human override；
- 不因为相同 bypass_reason 原样再次送审；
- 新问题可以重新送审；
- 不扩展为新主题搜索。

---

## 27. MVP 前端页面

v1 只需要一个审核工作台，不需要建设完整运营后台。

### 27.1 列表页

展示：

- 待审核数量；
- 主题；
- 来源主体；
- 当前需要人工判断的问题；
- review 状态；
- 简短 AI summary。

只重点展示 `pending_review`。

### 27.2 详情页

从上到下：

1. 主题与来源；
2. 打开原网页；
3. 为什么送审；
4. AI 已确认什么；
5. AI 仍不确定什么；
6. 本次 focus_items；
7. 如有草稿，展示产业链 Tree View；
8. 人工编辑；
9. 四类业务动作。

核心按钮：

```text
采用当前结果
修正后通过
交回 AI 继续
驳回来源
```

根据当前数据状态动态禁用不适用按钮。

---

## 28. MVP 验收场景

### Case 1：普通清晰产业链图

预期：

```text
PASS
↓
直接 source_group
↓
不进入 review
```

### Case 2：图片关键连接关系模糊

Agent 已主动查看、必要时有限放大，但关键父子关系仍无法判断。

预期：

```text
UNCERTAIN
↓
pending_review
```

前端直接提示需要确认的连接关系。

### Case 3：明确不合格来源

例如主题不一致 / 非产业链 / 没有企业证据且已可明确判断。

预期：

```text
FAIL
↓
直接排除
```

不进入人工队列。

### Case 4：Chip Explorer

Agent 事先没有站点专属规则。

预期至少能自主识别：

```text
静态正文不足
↓
需要浏览器
↓
存在点击式交互
↓
点击改变业务内容
↓
需要交互遍历
```

如果可以完整遍历：自动完成。

如果无法判断遍历完整性：创建 `needs_review`。

不得错误判定：

```text
没有普通正文 → 没有产业链
```

### Case 5：人工交回 Agent

```text
interaction_scope_uncertain
↓
pending_review
↓
人工“交回 AI 继续”
↓
returned_to_agent
↓
work claim-next 优先领取
↓
Agent 不得因同一 reason 再次原样送审
```

### Case 6：人工放行后出现新问题

第一次：

```text
interaction_scope_uncertain
```

人工放行后出现：

```text
company_mapping_ambiguous
```

预期：

- 不创建第二个 review_item；
- 更新原 review_item decision；
- 重新 `pending_review`；
- events 能看到第一次人工放行。

### Case 7：人工新增 Agent 漏掉节点

人工在 Tree View 新增节点 / 企业并通过。

预期：

- 能转换为九字段 records；
- 通过 Dataset 确定性校验；
- 成为正式 source_group；
- XLSX 更新。

### Case 8：主题部分来源送审

```text
A auto pass
B needs_review
C auto pass
```

预期：

- B 不阻塞 C；
- A/C 先进入正式 source_groups；
- 自动阶段结束后 topic = awaiting_review；
- B 闭环后自动进入 completed。

### Case 9：多 Agent 并发领取

两个主窗口同时 `work claim-next`。

预期：

- 同一 topic 不被重复领取；
- 同一 returned review 不被重复领取；
- lease 过期后可以恢复。

---

## 29. v1 成功标准

系统上线后应达到：

1. 普通来源的自动处理路径基本不增加人工操作。
2. Agent 明确知道“可以交给人”，不再为了完成任务强行猜测。
3. 新型来源先自主 Probe，而不是依赖不断增加站点特例。
4. 审核员一打开卡片就知道为什么需要自己介入。
5. 审核员主要处理少量决策点，而不是重新研究整篇来源。
6. 人工可以完全修正 Agent 结果。
7. 人工可以把当前 URL 一次性交回 Agent。
8. 同一个来源可以经历多轮 Agent ↔ Human，但只保留一个审核卡片。
9. Codex / Claude Code / Trae 可中途切换，任务状态不依赖聊天窗口。
10. CLI 能独立管理工作优先级、状态机、租约和完成判定。
11. 待审数据不污染 XLSX 正式交付。
12. Chip Explorer 类交互网站能作为未知解析能力测试，而不是域名特例。

---

## 30. 明确推迟到 v1 之后的问题

以下内容不作为 v1 实现前置条件：

### 30.1 站点专属规则建议

未来可以：

```text
同类来源多次被人工以相同方式处理
↓
AI 提示是否形成站点规则
↓
人明确批准
```

但 v1 不自动学习域名规则。

### 30.2 人工修改统计与模型优化

未来可以分析：

- Agent 直接正确比例；
- 人工修改比例；
- 人工新增比例；
- 高频 review_reason。

v1 的极简 events 可以为未来留下基础，但不建设分析平台。

### 30.3 人工修改的额外证据持久化

现有产业链业务规则仍要求来源内部证据，但 v1 不新增强制的逐行 evidence 数据库 / evidence schema。

是否在后续版本要求人工新增节点或企业显式绑定段落、截图、页码等额外证据，是独立设计问题。

### 30.4 已人工确认数据的再次 AI 分析

未来可以让升级后的 Agent 对人工结果提出 diff 建议，但：

```text
人工正式结果 > 后续 AI 建议
```

v1 不包含 re-analysis 流程。

---

## 31. 最终设计总结

v1 的本质不是“给产业链项目加一个审核网页”。

它真正增加的是一个明确的业务闭环：

```text
Candidate Source
       ↓
Source Probe
       ↓
Retrieval Plan
       ↓
Capability Gate
       ↓
┌─────────────┬─────────────┬──────────────┐
│ PASS        │ FAIL        │ UNCERTAIN    │
│             │             │              │
│ 自动完成    │ 自动排除    │ review_item  │
└──────┬──────┴─────────────┴───────┬──────┘
       │                            │
       │                      Human Review
       │                 ┌──────────┼──────────┐
       │                 │          │          │
       │               采用       修正      交回 AI
       │                 │          │          │
       │                 └────┬─────┘          │
       │                      │                │
       │                      │         returned_to_agent
       │                      │                │
       │                      │        Agent Work Queue
       │                      │                │
       └──────────────────────┴────────────────┘
                              ↓
                        source_groups
                              ↓
                         Runner JSON
                              ↓
                             XLSX
```

整个系统坚持：

> CLI 调度，Agent 执行，Skill 约束，人类决策，Runner 记忆，XLSX 交付。

这使自动化能力可以继续扩展，同时为真正的边界情况留下一个不会破坏正式数据、不会卡死流水线、也不会把人工重新变成“从头研究员”的安全出口。
