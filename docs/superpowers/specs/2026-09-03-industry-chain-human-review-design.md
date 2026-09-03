# 产业链 Agent Human-in-the-loop 审核系统设计文档 v1

## 1. 目的

本文定义 `researching-industry-chains` 的 HITL 审核系统。

核心原则：

> **Agent 负责研究语义，Client 负责协议工程。**

Agent 只负责：找来源、读取来源、判断资格、理解产业链、建立 Tree、判断是否可靠闭环，并在需要人工时说明“不确定在哪里、去哪里看、为什么”。

Client / Service 负责：Tree → 九字段、内部 ID、状态机、租约、review_item、并发、持久化、原子写入和 XLSX。

最终正式交付仍是固定九字段：

```text
主题, 信源主体, 分类1, 分类2, 分类3, 分类4, 公司, 信源URL, 备注
```

---

## 2. 总体边界

```text
CLI / Core Services
  │ work claim-next
  ▼
Agent
  │ SourceResult
  ▼
SourceResult Compiler
  ├─ accept → Tree → records → source_group → XLSX
  └─ review → review_item → Web → approve → records → XLSX
```

职责：

- **Agent**：研究员，只输出业务语义。
- **Skill**：定义搜索、Probe、视觉读取、资格判断和 SourceResult 提交规则。
- **CLI / Core**：调度、状态机、租约、校验、原子写入。
- **Web**：展示和人工编辑，不自行维护状态机。
- **Runner JSON**：任务事实源。
- **XLSX**：正式 `source_groups` 的九字段投影。

未经批准的 review 不进入正式 `source_groups`，也不进入 XLSX。

---

## 3. 搜索候选与 SourceResult

明确不合格的搜索候选不提交给 Client，Agent 直接跳过并继续搜索。

`source submit` 只有两种 outcome：

```text
accept
review
```

不新增 `reject` SourceResult。

Agent 不提交 topic；当前主题由 work context / claim 决定。

Agent 也不输出：

```text
九字段 records
source_group_id
review_item_id
evidence_id
focus_item_id
stage
reason
status
version
events
order
```

---

## 4. Agent-facing SourceResult

### 4.1 accept

```json
{
  "outcome": "accept",
  "source": {
    "name": "某研究院",
    "url": "https://example.com/report"
  },
  "description": "该来源通过产业链图展示锡膏上游原材料、中游制造和下游应用，并明确列出部分节点对应企业。",
  "chain": [
    {
      "name": "上游",
      "children": [
        {
          "name": "锡粉",
          "companies": ["华光新材", "康普锡威"]
        }
      ]
    }
  ]
}
```

规则：

- `source.name` 必填；
- `source.url` 必填；
- `description` 必填，通常 1～3 句话；
- `chain` 非空；
- SourceResult 任意位置都不得存在 uncertainty；
- 最终 Tree 至少包含一个企业。

### 4.2 review

```json
{
  "outcome": "review",
  "source": {
    "name": "某研究院",
    "url": "https://example.com/report"
  },
  "description": "该来源能够确认主要产业链结构，但部分企业与具体节点的直接归属关系无法可靠确认。",
  "chain": [
    {
      "name": "上游",
      "children": [
        {
          "name": "锡粉",
          "companies": ["华光新材"],
          "uncertainties": [
            {
              "company": "华光新材",
              "message": "当前企业归属缺少足够直接证据。",
              "evidence": [
                {
                  "locator": "PDF 第17页 · 图5",
                  "description": "图中出现华光新材，但与锡粉节点之间的直接连接不清楚。"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

规则：

- `chain` 可以为空；
- 全部来源中至少存在一个 uncertainty；
- 每个 uncertainty 的 `message` 必填；
- `evidence` 可省略；
- 如果提供 evidence，可以有多条；每条只包含必填的 `locator + description`。

`chain=[]` 表示 Agent 确认来源可能有价值，但当前无法形成可供人工直接修正的可靠 Tree。

---

## 5. 稀疏 Tree

节点统一使用对象，不混用字符串节点。

最小节点：

```json
{"name": "上游"}
```

企业：

```json
{
  "name": "锡粉",
  "companies": ["华光新材", "康普锡威"]
}
```

子节点：

```json
{
  "name": "上游",
  "children": [
    {"name": "锡粉"},
    {"name": "助焊剂"}
  ]
}
```

空字段可以省略：

```text
children: []
companies: []
uncertainties: []
```

### 5.1 企业

Tree 只表示“哪些企业直接属于当前节点”。

企业始终是独立字符串：

```json
"companies": ["华光新材", "康普锡威"]
```

不保留企业组层级。最终 Client 将同节点企业按当前顺序用 `、` 合并到 XLSX `公司` 字段。

### 5.2 顺序

数组顺序即业务顺序，也是最终 records 稳定输出顺序：

```text
父节点先于后代
同级保持当前数组顺序
移动后的子树整体出现在新位置
```

不新增第二套 `node_order` 事实源。

### 5.3 Client 确定性校验

Client 负责：

- 节点 `name` 非空；
- 正式分类深度最多 4；
- 同父节点拒绝完全相同的重复节点；
- 企业名非空；
- company uncertainty 必须引用当前节点 `companies` 中已有企业；
- accept 不得包含 uncertainty；
- review 至少包含一个 uncertainty；
- 正式通过来源至少存在一个企业；
- source URL 合法；
- Tree → records 后继续执行现有 DatasetService 的主题一致性、来源去重和九字段校验。

Agent 不需要自己模拟这些校验。

---

## 6. uncertainty 就地挂载

不使用独立全局 `target`。

### 6.1 来源级

整个来源的问题放在 SourceResult 根级：

```json
{
  "message": "无法可靠确认是否已经遍历全部必要交互状态。",
  "evidence": [
    {
      "locator": "Supply Chain Explorer → Materials → 展开子节点",
      "description": "点击节点后内容变化，但页面没有完整节点总数。"
    }
  ]
}
```

### 6.2 节点级

当前节点或父子结构的问题放在节点内部，不填写 company：

```json
{
  "name": "锡粉",
  "uncertainties": [
    {
      "message": "无法确认锡粉与上级金属材料是否为直接父子关系。"
    }
  ]
}
```

Client 通过递归位置天然获得完整 root-to-node path。

### 6.3 企业 occurrence

企业问题挂在所在节点，只补企业名：

```json
{
  "name": "锡粉",
  "companies": ["华光新材"],
  "uncertainties": [
    {
      "company": "华光新材",
      "message": "无法可靠确认其直接属于当前锡粉节点。"
    }
  ]
}
```

内部目标天然是：

```text
节点路径 + 企业名
```

因此同一家企业出现在多个节点也不会混淆。

如果发现了企业但连候选节点都无法确定，可以使用**来源级 uncertainty**说明“发现该企业但无法归属”，不要求 Agent 为了挂 uncertainty 而伪造节点归属。

---

## 7. Evidence：定位提示，不是资产系统

Evidence 只帮助审核员回答：

```text
去哪里看？
为什么看这里？
```

结构：

```json
{
  "locator": "PDF 第17页 · 图5",
  "description": "图中能看到华光新材，但与锡粉节点的直接关系不清晰。"
}
```

一个 uncertainty 可以没有 evidence，也可以有多条 evidence，例如产业链结构和企业归属分别来自不同位置。

`locator` 使用自由文本，可以表示：

- PDF 页码 / 图号；
- 正文段落；
- 表格；
- 网页章节；
- Canvas / SVG / 动态图位置；
- 浏览器交互路径。

v1 不要求：

```text
evidence_id
kind
asset_ref
图片 URL
截图文件名
bounding box
OCR
截图上传
Evidence DB
Evidence 目录
图片 serving API
Lightbox
```

Agent 可以截图完成视觉读取，但截图只是研究手段，不是系统必须持久化的业务数据。

---

## 8. description = 最终备注

`description` 是来源级业务说明，同时就是九字段 `备注` 的来源内容。

不维护独立 `remark` 字段。

```text
SourceResult.description
↓
Tree → records
↓
来源组第一行.备注 = description
↓
XLSX
```

Full Review 可以修改 description。

Client 不根据 Tree 自动改写自然语言 description，只保存 Agent / 人工最终确认版本。

如果人工确认“企业确实在来源中出现，但无法可靠归属任何节点”，可以把：

```text
发现但无法归属：A公司、B公司
```

保留在最终 description 中；它随第一行备注交付。为此不新增 `unresolved_companies` 第二事实源。

---

## 9. Tree → 九字段 Compiler

字段来源：

```text
主题       ← 当前 work item topic
信源主体   ← source.name
分类1~4    ← 当前节点 root-to-node path
公司       ← 当前节点 companies 用 、 合并
信源URL    ← source.url
备注       ← description，仅第一行
```

每个可读节点都生成一行，包括无企业的父节点。

示例：

```text
上游
└─ 锡粉
   ├ 华光新材
   └ 康普锡威
```

投影：

```text
上游 / ""
上游 / 锡粉 / 华光新材、康普锡威
```

正式写入流程：

```text
SourceResult / 人工 final chain
↓
Tree validate
↓
Tree → records
↓
DatasetService validate
↓
原子写 Runner JSON
↓
刷新 XLSX
```

任一步失败都不能留下半个 source_group。

---

## 10. source submit

### accept

```text
Agent source submit accept
↓
Client 校验
↓
Tree → 九字段
↓
正式 source_group
↓
XLSX
↓
accepted
```

### review

```text
Agent source submit review
↓
Client 校验
↓
不写正式 source_group / XLSX
↓
创建或更新 review_item
↓
queued_for_review
```

首次来源和“交回 AI 继续”统一使用同一个 `source submit`。

- 首次 review → 创建 review_item；
- review work 返回 accept → 更新原 review_item、写正式来源并闭环；
- review work 再返回 review → 用最新完整 SourceResult 替换同一个 review_item 草稿并重新待审。

Agent 返回**完整快照**，不是 patch。再次 review 时只提交当前仍存在的不确定性。

---

## 11. ReviewItem

建议保持轻量：

```json
{
  "review_item_id": "review_ab12cd",
  "status": "pending_review",
  "version": 3,
  "source": {"name": "某研究院", "url": "https://example.com/report"},
  "description": "...",
  "chain": [],
  "uncertainties": [],
  "agent_claim": null,
  "events": []
}
```

规则：

- `chain` 就是审核草稿，不维护 `draft_records + draft_tree`；
- uncertainty 和 evidence 保持就地结构；
- `focus_items` 可由 Web ViewModel 动态派生，不要求持久化；
- `stage / reason` 若保留，只是 Client best-effort 派生的展示辅助 metadata，推不出来就是 `other`，不得参与核心业务判断；
- Agent 不输出任何这些内部字段。

`chain=[]` 是合法 review，但 v1 不允许从零人工构建完整产业链，只能交回 AI 或驳回来源。

---

## 12. 人工审核

来源级动作只有：

```text
采用当前结果
修正后通过
交回 AI 继续
驳回来源
```

### 12.1 approve

人工最终提交完整：

```text
final chain
final description
expected_version
```

Client 再执行完整 Tree → records → source_group → XLSX。

人工可修改：

- 节点名称；
- 新增根 / 同级 / 子节点；
- 删除节点；
- 节点顺序；
- 父子关系；
- 新增 / 删除 / 重命名企业；
- 企业归属；
- Agent 遗漏节点和企业；
- description。

### 12.2 交回 AI

作用域仅当前 review_item 的当前 version 和当前来源。

不建立域名白名单，不修改 Skill，不影响其他来源。

同一 review version 只能 return 一次；Agent 重新提交后产生新 version，人工才能基于新结果再次决定。

### 12.3 驳回

来源闭环为 rejected，不产生正式 source_group，不写 XLSX。

---

## 13. Tree 人工编辑语义

Full Review 是唯一 Tree 编辑面。

支持：

```text
rename
add root
add sibling
add child
delete
change parent
同父节点拖拽排序
跨父节点拖拽整棵子树
企业增删改和跨节点移动
```

跨父节点移动整棵子树递归跟随。

必须拒绝：

- 节点移动到自己下面；
- 节点移动到自己的后代下面；
- 移动后正式分类深度超过 4。

删除有后代的节点必须明确提示影响，不能静默丢失子树。

---

## 14. Agent 工作协议

Agent-facing CLI 只保留：

```text
work claim-next
source submit
work done
work fail
```

### topic work

```text
work claim-next
↓
搜索多个来源
↓
不合格候选直接跳过
↓
source submit accept / review × N
↓
达到停止规则
↓
work done
```

`work done` 只表示 topic 本轮自动搜索阶段结束，不代表 Agent 直接设置 topic 状态。

### review work

```text
work claim-next
↓
取得 review source + description + chain + uncertainties + 人工交回上下文
↓
继续研究
↓
source submit accept / review
↓
本轮自动结束
```

review work 不需要额外 `work done`。

### fail

只用于真实执行异常。来源不合格不是 fail。

`source submit` 成功即视为 Client 接管，Agent 不需要再读 Runner 校验 ID 或补一个“已保存”动作。

---

## 15. Source Probe 与 Capability Gate

不以固定 parser type 驱动。

Agent 应先判断：

> 要取得完整业务证据，我需要做什么？

包括正文、渲染浏览器、视觉读图、PDF、表格、折叠区、Tab、筛选、点击和多状态遍历等。

Capability Gate：

```text
PASS      → source submit accept
FAIL      → 明确不合格 / 不可用，直接跳过
UNCERTAIN → 有业务价值且人工可能改变结果，source submit review
```

`UNCERTAIN` 不等于“没见过这种网站”。Agent 应先主动探索。

`https://chipexplorer.eto.tech/` 继续作为 generalized test：Agent 不得靠域名特例，应自主发现交互需求；只有主动遍历后仍无法确认完整性才 review，并提供自然语言 locator / description。

---

## 16. Topic 与 Review 状态

Topic：

```text
pending
in_progress
awaiting_review
completed
no_qualified_source
failed
```

Agent 不直接设置状态。

```text
pending → claim → in_progress
in_progress → work done
  ├─ 有 open review → awaiting_review
  ├─ 无 open review + 有正式来源 → completed
  └─ 无 open review + 无正式来源 → no_qualified_source

awaiting_review → 最后一个 review 闭环
  ├─ 有正式来源 → completed
  └─ 无正式来源 → no_qualified_source
```

一个来源进入 review 不暂停 topic 搜索；Agent 继续处理其他来源直到 `work done`。

ReviewItem：

```text
pending_review
returned_to_agent
in_agent
approved
rejected
```

```text
pending_review
├─ approve → approved
├─ reject → rejected
└─ return → returned_to_agent → claim → in_agent
                                     ├─ accept → approved
                                     └─ review → pending_review
```

---

## 17. 调度、并发与原子性

统一领取：

```text
industry-chain work claim-next
```

优先级：

```text
returned_to_agent review work
↓
pending topic work
```

CLI 管 claim、lease、续租、过期恢复。

Review 使用整数 `version`；人工写动作携带 `expected_version`，不一致返回：

```text
409 REVIEW_VERSION_CONFLICT
```

Runner JSON 是任务事实源；XLSX 只投影正式 source_groups。

---

## 18. Web focus 派生

Web 不需要 Agent 生成 focus ID。

```text
根级 uncertainty
→ source focus

node uncertainty 无 company
→ node focus，目标 = 当前 root-to-node path

node uncertainty 有 company
→ company occurrence focus，目标 = node path + company
```

`stage / reason` 如果存在，只能作为展示 metadata，不影响 approve、return、reject 或状态推导。

---

## 19. 正式数据与审核数据边界

正式交付：

```text
source
final description
final chain
↓
九字段 source_group
↓
XLSX
```

审核过程：

```text
uncertainties
evidence locator / description
review events
```

uncertainty 和 Evidence 不进入正式九字段。人工解决不确定性后，不把旧 uncertainty 自动写入最终备注。

---

## 20. v1 非目标

不做：

- 所有来源都人工审核；
- Agent 输出 `reject`；
- Agent 直接输出九字段；
- Agent 生成内部 ID / 状态；
- `draft_records + draft_tree` 双模型；
- Evidence Asset / Evidence DB / 截图归档；
- 图片 serving API / Lightbox / OCR；
- 数据库、Redis、消息队列；
- parser 注册中心；
- 复杂置信度体系；
- 域名白名单；
- 自动修改 Skill；
- 从 `chain=[]` 纯人工从零建链；
- 完整 chain-of-thought / Prompt / token 持久化。

---

## 21. 验收标准

1. `accept + source + description + chain` 可直接由 Client 原子编译为九字段 XLSX。
2. 明确不合格候选不会在 Runner 中产生对象。
3. 节点 uncertainty 由 Tree path 唯一定位。
4. 同名企业多节点时，通过 `node path + company` 定位具体 occurrence。
5. uncertainty 的 evidence 可为空，也可有多个 `locator + description`。
6. `review + chain=[] + uncertainty` 合法，但 Web 不能从零人工建链。
7. 人工修改 Tree 和 description 后，最终 XLSX 只包含修正后的正式数据。
8. 企业最终无法归属时可写入最终 description 的 `发现但无法归属：...`，不新增第二事实源。
9. 同一 review_item 交回 Agent 后仍使用同一个 `source submit`，不创建 review 链。
10. topic 可连续提交多个来源，只有搜索结束时调用一次 `work done`。
11. review work 一次 `source submit` 即结束，不要求额外 finish。
12. Tree / records / XLSX 任一步失败都不留下半个 source_group。
13. Chip Explorer 在无域名专用规则下能主动探索；无法确认完整性时 review 并给 locator / description。

---

## 22. 核心结论

```text
Agent
= 找 + 读 + 理解 + 表达

Client
= 验证 + 转换 + 编号 + 调度 + 持久化 + 审核编排 + XLSX
```

Agent-facing 协议最终只需要理解：

```text
outcome
source.name
source.url
description
chain
review 时就地 uncertainties
可选 evidence: locator + description
```

这条职责边界优先于继续增加 HITL 内部字段。