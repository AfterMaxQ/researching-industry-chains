# 产业链 Agent Human-in-the-loop 审核系统设计文档 v1

## 1. 文档目的

本文定义 `researching-industry-chains` 的 Human-in-the-loop（HITL）审核系统。

目标不是把 Agent 变成工作流工程师，而是在保留自动研究能力的前提下，为真正无法可靠闭环的来源提供人工审核通道。

核心原则：

> **Agent 负责研究语义，Client 负责协议工程。**

Agent 只负责找来源、读取来源、理解产业链、判断是否可靠完成，以及在需要审核时说明不确定点和审核依据。

Client / Service 负责 Tree → 九字段、ID、状态机、租约、review_item、持久化、原子写入和 XLSX。

最终正式业务交付仍然是九字段 XLSX：

```text
主题
信源主体
分类1
分类2
分类3
分类4
公司
信源URL
备注
```

---

## 2. 设计目标

v1 需要做到：

1. 正常合格来源继续自动写入，不强制人工确认。
2. 明确不合格的搜索候选由 Agent 直接跳过，不进入 Runner。
3. 只有有业务价值但无法可靠闭环的来源进入 HITL。
4. Agent 不再直接展开九字段 records，而是提交产业链 Tree。
5. Agent 不生成 `review_item_id`、`evidence_id`、`focus_item_id`、`stage`、`reason`、`status`、`version`、`events` 等内部协议字段。
6. Agent 不重复提交 topic；当前主题由 work item / claim context 决定。
7. 人工审核单位是来源，不是 Excel 单行。
8. 人工可以直接修改 Tree 和来源说明，最终再由 Client 确定性投影为九字段。
9. Runner JSON 继续作为任务事实源；XLSX 继续作为正式交付投影。
10. 不引入数据库、消息队列、Evidence DB、长期 Memory、独立 Agent SDK 或复杂状态平台。

---

## 3. 总体架构

```text
┌──────────────────────────────┐
│ CLI / Core Services          │
│ 调度、状态机、租约、持久化  │
└──────────────┬───────────────┘
               │ work claim-next
               ▼
┌──────────────────────────────┐
│ Agent                        │
│ Codex / Claude Code / Trae   │
│ 搜索、浏览、判断、读图、建树│
└──────────────┬───────────────┘
               │ SourceResult
               ▼
┌──────────────────────────────┐
│ SourceResult Compiler        │
│ 校验、Tree→records、HITL编排 │
└──────────────┬───────────────┘
               │
      ┌────────┴─────────┐
      ▼                  ▼
formal source_group   review_item
      │                  │
      ▼                  ▼
    XLSX              Web 审核
```

职责：

- **Agent**：研究员，只输出业务语义。
- **Skill**：告诉 Agent 如何搜索、Probe、解析、判断可靠性和提交 SourceResult。
- **CLI / Core Service**：统一工作入口、状态机、租约、原子写入和错误处理。
- **SourceResult Compiler**：把 Agent 的稀疏 Tree 编译成正式九字段或 review_item。
- **Web**：展示、人工编辑和提交审核动作，不直接改 Runner 状态。
- **Runner JSON**：任务事实源。
- **XLSX**：正式九字段交付投影，只包含已经正式通过的来源。

---

## 4. Agent-facing SourceResult

### 4.1 只有 `accept` 和 `review`

Agent 处理一个值得提交的来源时，只提交一种统一 SourceResult：

```text
outcome = accept
outcome = review
```

明确不合格的搜索候选不提交给 Client，Agent 直接跳过并继续搜索。

不新增：

```text
outcome = reject
```

搜索过程中的无关页面、新闻、无产业链内容页面等不成为 Runner 对象。

### 4.2 `accept`

当 Agent 认为当前来源已经可靠闭环：

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
- `chain` 必须非空；
- `accept` 中不允许存在任何来源级、节点级或企业级 uncertainty。

### 4.3 `review`

当来源有业务价值，但存在 Agent 无法可靠闭环的判断：

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

`review` 允许 `chain` 为空，例如 Agent 已确认来源有价值，但当前无法形成可靠 Tree。

`review` 必须至少存在一个 uncertainty，可以位于来源级或 Tree 内部。

---

## 5. 稀疏 Tree 协议

### 5.1 节点结构

Tree 节点统一使用对象，不混用字符串和对象。

最小节点：

```json
{
  "name": "上游"
}
```

有企业时：

```json
{
  "name": "锡粉",
  "companies": ["华光新材", "康普锡威"]
}
```

有子节点时：

```json
{
  "name": "上游",
  "children": [
    {"name": "锡粉"},
    {"name": "助焊剂"}
  ]
}
```

空数组允许省略：

```text
children: []
companies: []
uncertainties: []
```

Agent 不需要机械补齐。

### 5.2 企业表达

Tree 只表达：

> 哪些企业直接属于当前节点。

企业始终是独立字符串：

```json
"companies": ["华光新材", "康普锡威"]
```

不保存“企业组”层级，不使用二维数组。

最终写 XLSX 时，Client 将同节点企业按当前顺序用 `、` 合并。

### 5.3 Tree 顺序

数组顺序就是来源中的业务顺序，也作为最终 records 的稳定输出顺序。

Client 使用稳定 Tree traversal：

```text
父节点先于后代
同级节点保持当前数组顺序
整个子树作为一个连续块输出
```

不新增第二套 `node_order` 事实源。

### 5.4 Tree 确定性校验

Client 负责：

- `name` 必须是非空字符串；
- 最大正式分类深度为 4；
- 同一父节点下拒绝完全相同的重复节点；
- `companies` 中企业名必须非空；
- `company` uncertainty 必须引用当前节点 `companies` 中已有企业；
- `accept` 不得带 uncertainty；
- `review` 至少存在一个 uncertainty；
- 正式通过的来源最终至少存在一个企业。

Agent 不需要先手工模拟这些校验。

---

## 6. 不确定性就地挂载

不使用全局 `target` 字符串。

原因：

- `target` 可能是节点，也可能是企业；
- 同一家企业可能出现在多个节点；
- 仅靠名字无法唯一定位企业 occurrence。

因此 uncertainty 直接挂在问题发生的位置。

### 6.1 来源级 uncertainty

属于整个来源的问题放在 SourceResult 根级：

```json
{
  "message": "无法可靠确认是否已经遍历全部必要交互状态。",
  "evidence": [
    {
      "locator": "Supply Chain Explorer → Materials → 展开子节点",
      "description": "点击节点后业务内容变化，但页面没有完整节点总数。"
    }
  ]
}
```

Client 自动理解为 source scope。

### 6.2 节点级 uncertainty

属于当前节点或当前结构关系的问题，放在节点内部，不填写 company：

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

Client 通过递归位置天然知道完整节点路径。

### 6.3 企业 occurrence uncertainty

企业问题仍挂在所在节点，只额外填写企业名：

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

内部目标由 Client 确定为：

```text
节点路径 + 企业名
```

因此即使同一家企业出现在多个节点，也不会混淆。

---

## 7. Evidence：只保留定位和审核依据

v1 不建设 Evidence Asset 系统。

Evidence 只是帮助审核员快速找到来源位置并理解审核依据的轻量描述：

```json
{
  "locator": "PDF 第17页 · 图5",
  "description": "图中能看到华光新材，但与锡粉节点的直接关系不清晰。"
}
```

字段：

- `locator`：去哪里看；
- `description`：为什么这里值得看、它支持或不能支持什么判断。

一个 uncertainty 可以有多个 evidence，例如产业链结构证据与企业归属证据分别来自不同位置。

允许 locator 使用自由文本，因为来源可能是：

- PDF 页码 / 图号；
- 正文段落；
- 表格；
- 网页某章节；
- Canvas / SVG / 动态图；
- 需要浏览器点击的交互状态。

v1 不要求：

- `evidence_id`；
- `kind`；
- `asset_ref`；
- 图片 URL；
- 截图文件名；
- bounding box；
- OCR；
- 截图上传；
- Evidence DB；
- Evidence 目录；
- Lightbox / 图片渲染 API。

Agent 可以使用截图作为自己的视觉读取手段，但不需要把截图持久化为系统资产。

---

## 8. `description` 与 XLSX `备注`

`description` 是来源级业务说明，也是最终九字段 `备注` 的来源内容。

不再同时维护：

```text
description
remark
```

规则：

```text
SourceResult.description
        ↓
Tree → records
        ↓
来源组第一行.备注 = description
        ↓
XLSX
```

Full Review 中人工可以修改 `description`。

如果人工修改了 Tree，应允许同步修改来源说明，避免最终 Tree 与备注语义不一致。

Client 不根据 Tree 自动重写自然语言 description，只保存最终人工确认版本。

如果未来有确定性的必要补充，也应合并进同一最终备注，不新增第二个交付字段。

---

## 9. Tree → 九字段 Compiler

Agent 不再直接输出九字段。

Client 对 `accept` 或人工批准后的最终 Tree 做确定性投影。

### 9.1 字段来源

```text
主题       ← 当前 work item 的 topic
信源主体   ← source.name
分类1~4    ← 当前节点 root-to-node path
公司       ← 当前节点 companies 用 、 合并
信源URL    ← source.url
备注       ← description，仅来源组第一行填写
```

### 9.2 行生成

每个可读节点都生成一行 root-to-node record，即使当前节点没有企业。

例如：

```text
上游
└─ 锡粉
   ├─ 华光新材
   └─ 康普锡威
```

投影为：

```text
分类1=上游，公司=""
分类1=上游，分类2=锡粉，公司="华光新材、康普锡威"
```

### 9.3 正式写入复用 DatasetService

Compiler 生成 records 后继续走现有确定性校验和原子来源组写入：

```text
SourceResult
↓
validate Tree
↓
Tree → records
↓
DatasetService validate
↓
原子写 Runner JSON
↓
刷新 XLSX
```

来源组九字段仍是最终正式业务协议；只是机械展开从 Agent 移到了 Client。

---

## 10. SourceResult 提交流程

### 10.1 `accept`

```text
Agent source submit accept
↓
Client 校验 SourceResult / Tree
↓
Tree → 九字段
↓
DatasetService 原子写正式 source_group
↓
刷新 XLSX
↓
CLI 返回 accepted
```

### 10.2 `review`

```text
Agent source submit review
↓
Client 校验 SourceResult
↓
不写 source_group
不写 XLSX
↓
创建或更新 review_item
↓
进入人工审核
↓
CLI 返回 queued_for_review
```

未经批准的 Tree 不属于正式交付数据。

### 10.3 首次来源与交回 AI 使用同一个 `source submit`

Agent 不学习两套协议。

普通 topic work 与人工交回的 review work 最后都提交完整 SourceResult 快照。

Client 根据当前 work context 自动判断：

- 首次 `review`：创建 review_item；
- review work 返回 `accept`：更新原 review_item、正式写入 source_group 并闭环；
- review work 再次返回 `review`：更新同一个 review_item 的最新完整快照，重新进入人工审核。

不因为反复交回 AI 创建 `review_01 → review_02 → review_03` 链。

Agent 再次提交 `review` 时，只提交当前仍然存在的不确定性，不做 patch，也不需要显式 resolve 旧 uncertainty。

---

## 11. ReviewItem 内部模型

review_item 保持轻量，不复制 Agent-facing 协议以外的复杂结构：

```json
{
  "review_item_id": "review_ab12cd",
  "status": "pending_review",
  "version": 3,
  "source": {
    "name": "某研究院",
    "url": "https://example.com/report"
  },
  "description": "...",
  "chain": [],
  "uncertainties": [],
  "agent_claim": null,
  "events": []
}
```

说明：

- `chain` 就是当前审核草稿，不再维护 `draft_records` + `draft_tree` 双事实源；
- `uncertainties` 与 evidence 保持就地结构，不生成独立 Evidence Asset；
- `focus_items` 不要求持久化，可由 Web ViewModel 根据 uncertainty 所在位置动态派生；
- `stage / reason` 如保留，只能作为 Client best-effort 派生的展示辅助元数据，推导失败即 `other`，不得影响核心审核流程；
- Agent 不输出这些内部字段。

`chain=[]` 是合法 review，但 v1 不允许人工从零构建完整产业链；此时只能交回 AI 继续或驳回来源。

---

## 12. 人工审核动作

review 级业务动作只有：

### 12.1 采用当前结果

当前 working copy 未修改且 Tree 非空：

```text
approve
↓
最终 chain + description
↓
Tree → records
↓
正式 source_group
↓
XLSX
```

### 12.2 修正后通过

人工可修改：

- 节点名称；
- 新增根节点、同级节点、子节点；
- 删除节点；
- 节点顺序；
- 父子关系；
- 企业；
- 企业归属；
- Agent 遗漏的节点 / 企业；
- `description`。

最终提交完整 `chain + description`，不是 row patch。

### 12.3 交回 AI 继续

作用域仅当前 review_item 的当前版本和当前来源。

不创建域名白名单，不修改 Skill，不影响其他来源。

同一 review version 只能执行一次 return-to-agent；Agent 重新提交后产生新 version，人工才可基于新结果再次决定是否交回。

### 12.4 驳回来源

当前来源闭环为 rejected，不产生正式 source_group，不写 XLSX。

---

## 13. Tree 人工编辑语义

Full Review 是唯一 Tree 编辑入口。

支持：

- rename；
- add root；
- add sibling；
- add child；
- delete；
- change parent；
- 同父节点拖拽排序；
- 跨父节点拖拽整棵子树；
- 新增遗漏企业；
- 删除企业；
- 将企业移动到其他节点。

跨父节点移动时：

```text
A
└─ B
   ├─ C
   └─ D
```

将 B 拖到 X 下：

```text
X
└─ B
   ├─ C
   └─ D
```

B 的全部后代递归跟随。

Client / UI 必须拒绝：

- 节点拖到自己下面；
- 节点拖到自己的后代下面；
- 移动后正式分类深度超过 4。

删除带子节点的节点必须明确展示影响，不允许静默丢失子树。

---

## 14. Agent 工作协议

Agent-facing CLI 只保留极少动作：

```text
work claim-next
source submit
work done
work fail
```

### 14.1 topic work

```text
work claim-next
↓
搜索多个候选来源
↓
明显不合格 → 直接跳过
↓
合格 → source submit accept
↓
边界来源 → source submit review
↓
继续搜索直到满足停止规则
↓
work done
```

`work done` 只表示：

> 当前 topic 的本轮自动搜索阶段结束。

它不代表 Agent 直接设置 `completed`。

### 14.2 review work

```text
work claim-next
↓
取得当前 review source + chain + description + uncertainties + 人工交回上下文
↓
继续研究
↓
source submit accept | review
↓
本轮 review work 自动结束
```

review work 不需要额外 `work done`。

### 14.3 fail

`work fail` 只表示真正执行异常，例如浏览器无法继续、环境损坏等。

来源不合格不是 fail。

### 14.4 submit 成功即 Client 接管

Agent 不需要提交后再读 Runner 校验 ID，也不需要再发送“已保存”。

CLI 返回：

```text
accepted
queued_for_review
```

即表示 Client 已接管。

结构错误则返回可直接修正的确定性错误，例如：

```text
TREE_DEPTH_EXCEEDED
当前节点位于第 5 层，正式分类最多支持 4 层
```

---

## 15. Source Probe 与 Capability Gate

HITL 不以固定 parser type 驱动。

Agent 对候选来源首先判断：

> 要取得完整业务证据，我需要做什么？

可能需要：

- 静态正文；
- 浏览器实际渲染；
- 视觉读图；
- PDF 指定页；
- 表格；
- 展开折叠区；
- 点击节点；
- 切换 Tab；
- 改变筛选条件；
- 遍历多个交互状态。

Capability Gate 仍使用：

```text
PASS
FAIL
UNCERTAIN
```

- `PASS` → `source submit` with `outcome=accept`；
- `FAIL` → 明确不合格 / 不可用，Agent 直接跳过，不提交；
- `UNCERTAIN` → 有业务价值且人工可能改变结论，`source submit` with `outcome=review`。

`UNCERTAIN` 不等于“没见过这种网站”。Agent 应先自主探索。

---

## 16. Chip Explorer 泛化验收

`https://chipexplorer.eto.tech/` 继续作为 generalized test。

预期 Agent：

```text
打开候选来源
↓
发现静态正文不足
↓
使用浏览器实际查看
↓
发现节点可交互
↓
尝试点击并观察业务状态变化
↓
推断需要交互遍历
↓
尝试覆盖全部必要状态
```

理想结果是自主完成并 `accept`。

只有已经理解交互规律、主动尝试后，仍不能可靠确认例如遍历完整性，才 `review`，并用自然语言 uncertainty + locator + description 告诉审核员去哪里看。

Skill 不允许增加域名专用特例。

---

## 17. Topic 状态机

正式 topic 状态：

```text
pending
in_progress
awaiting_review
completed
no_qualified_source
failed
```

Agent 不直接设置任何状态。

### 17.1 自动阶段

```text
pending
  ↓ claim
in_progress
  ↓ work done
  ├─ 有 open review_item → awaiting_review
  ├─ 无 open review + 有 source_group → completed
  └─ 无 open review + 无 source_group → no_qualified_source
```

### 17.2 review 闭环

```text
awaiting_review
  ↓ 最后一个 review_item 闭环
  ├─ 有 source_group → completed
  └─ 无 source_group → no_qualified_source
```

### 17.3 review 不暂停 topic 自动搜索

一个来源 `review` 后，Agent 继续搜索该 topic 的其他来源，直到显式 `work done`。

因此 review 只暂停当前来源，不暂停整个主题。

---

## 18. ReviewItem 状态机

持久化状态：

```text
pending_review
returned_to_agent
in_agent
approved
rejected
```

典型流转：

```text
pending_review
├─ approve → approved
├─ reject → rejected
└─ return-to-agent → returned_to_agent
                       ↓ claim
                    in_agent
                       ↓ source submit
                 ┌─────┴─────┐
              accept         review
                ↓              ↓
             approved      pending_review
```

Agent 只提交 SourceResult，不直接写 review status。

---

## 19. 调度

统一：

```text
industry-chain work claim-next
```

优先级：

```text
可领取的 returned_to_agent review work
↓
普通 pending topic work
```

CLI 返回 work context，Agent 不自己扫描 Runner JSON 决定下一项任务。

review claim 与 topic claim 都有租约；租约、续租和过期恢复由 CLI 管理。

---

## 20. 并发与原子性

### 20.1 Runner JSON

Runner JSON 是唯一任务事实源。

### 20.2 XLSX

XLSX 只投影正式 source_groups。

review 草稿、uncertainty、evidence 描述不得提前进入 XLSX。

### 20.3 来源组原子写入

一个 `accept` 或人工 approve 必须：

```text
完整 Tree 校验
↓
完整 records 投影
↓
完整来源组业务校验
↓
原子写 Runner
↓
刷新 XLSX
```

任一步失败不得留下半个 source_group。

### 20.4 Review 乐观并发

每个 review_item 有整数 `version`。

人工提交必须带 `expected_version`。

如果版本不一致：

```text
HTTP 409 / REVIEW_VERSION_CONFLICT
```

不允许静默覆盖 Agent 或另一次人工操作产生的新版本。

---

## 21. Web ViewModel 派生规则

Web 可以从 review_item 动态派生 focus，不要求 Agent 或 Runner 持久化 focus ID。

派生规则：

```text
根级 uncertainty
→ source focus

node.uncertainties[] 且无 company
→ node focus，目标由当前 root-to-node path 决定

node.uncertainties[] 且有 company
→ company occurrence focus，目标 = 当前 node path + company
```

`stage / reason` 如保留，只用于展示和筛选的 best-effort metadata：

- 能简单确定就归类；
- 无法确定就 `other`；
- 不参与是否可 approve、是否进入 review、是否能回 Agent 等核心判断。

---

## 22. 审核完成后的数据边界

最终正式来源只保留对业务交付有意义的内容：

```text
source
final description
final chain
↓
九字段 source_group
↓
XLSX
```

审核中的：

```text
uncertainties
evidence locator / description
review events
```

属于 review workflow 信息，不进入正式九字段。

人工修改解决了某个 uncertainty 后，不需要把旧不确定性写进最终备注。

---

## 23. v1 非目标

明确不做：

- 所有来源都人工审核；
- `reject` SourceResult；
- Agent 直接输出九字段；
- Agent 生成内部 ID；
- Agent 管理 topic / review 状态；
- `draft_records` 与 `draft_tree` 双模型；
- 独立 `focus_items` 持久化要求；
- 独立 Evidence DB；
- Evidence Asset / 截图归档；
- 图片 serving API / Lightbox；
- OCR 编辑器；
- 全量浏览器录像；
- 数据库、Redis、消息队列；
- 复杂置信度体系；
- parser 注册中心；
- 域名白名单；
- 自动修改 Skill；
- 从空白 review 纯人工构造完整产业链；
- 完整 chain-of-thought、Prompt、token 记录。

---

## 24. v1 验收标准

### A. 正常自动来源

Agent 提交 `accept + source + description + chain`；Client 自动 Tree → 九字段、原子写来源组并刷新 XLSX。

### B. 明确不合格候选

Agent 直接跳过；Runner 中不产生 reject 对象。

### C. 节点不确定性

uncertainty 挂在具体节点；Client 能通过 Tree path 唯一定位。

### D. 同名企业多节点

同一企业出现在两个节点，其中只有一个 occurrence 有 uncertainty；Client 能通过 `node path + company` 唯一定位，不串到另一个节点。

### E. 多证据

一个 uncertainty 可提供多个 `locator + description`，不要求 evidence ID 或截图资产。

### F. 无草稿 review

`review + chain=[] + uncertainty` 合法；Web 只允许交回 AI 或驳回，不允许直接 approve / 从零人工建链。

### G. 人工修正

人工修改 Tree 和 description 后 approve；Client 重新完整投影九字段，最终 XLSX 只包含修正后的正式来源。

### H. 交回 AI

同一个 review_item 被交回后，Agent 仍使用同一 `source submit`；`accept` 则闭环，`review` 则更新同一 review_item 快照，不新建 review 链。

### I. topic 完成

Agent 搜索期间可连续 `source submit` 多个来源，最终只调用一次 `work done`；Client 自行推导 `awaiting_review / completed / no_qualified_source`。

### J. review work 完成

review work 只需一次 `source submit`，不要求额外 finish。

### K. 原子性

Tree 校验、records 校验或 XLSX 刷新失败时，不留下半写 source_group。

### L. Chip Explorer

Agent 在没有域名专用规则的情况下能主动发现交互需求并探索；无法确认遍历完整时，提交 `review` 并给出自然语言 locator / evidence description。

---

## 25. 核心结论

系统边界最终收敛为：

```text
Agent
= 找 + 读 + 理解 + 表达

Client
= 验证 + 转换 + 编号 + 调度 + 持久化 + 审核编排 + XLSX
```

Agent-facing 协议只需要理解：

```text
outcome
source.name
source.url
description
chain
review 时的就地 uncertainties
uncertainty 的 locator + description
```

其余全部属于 Client 内部实现。

这条边界优先级高于继续扩展 HITL 内部字段。