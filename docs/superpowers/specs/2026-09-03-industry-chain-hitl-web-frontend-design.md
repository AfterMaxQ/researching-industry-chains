# 产业链 HITL 审核前端与本地 Web 架构设计 v1

## 1. 文档目的

本文定义 `researching-industry-chains` 项目的 Human-in-the-loop（HITL）审核前端与本地 Web 接入方式。

本文是以下核心设计的配套文档：

- `docs/superpowers/specs/2026-09-03-industry-chain-human-review-design.md`

核心设计回答“什么时候进入人工审核、Runner / review_item / work 如何流转”；本文只回答：

> 人如何高效审核，以及 localhost Web 如何在不绕开 CLI 状态机的前提下接入现有 Python Client。

v1 定位为**单机 localhost 研究审核工作台**，不是多人 SaaS，也不是传统数据管理后台。

---

## 2. 产品目标

前端需要做到：

1. 用户先选择一个 Runner，再进入该 Runner 的独立工作空间。
2. 只显示当前 Runner 的工作台、待审核、任务进度和已完成数据。
3. 审核员一眼看懂：为什么来源被送审、Agent 已完成什么、现在只需要人判断什么。
4. 简单 review 可以在 Queue 中快速处理，复杂 review 再进入完整审核 Workbench。
5. 完整审核以“产业链树 + 企业归属”为主要心智模型，不以九字段 Excel 表为主要编辑界面。
6. 人工可修正 Agent 草稿，也可新增 Agent 完全遗漏的节点和企业。
7. 无草稿的 `review_item` 也能正常展示和处理。
8. `交回 AI 继续` 的语义清楚：只放行当前 `review_item / 当前 URL / 当前 reason`，不建立域名规则。
9. Runner 页面能看清 Codex / Claude Code / Trae 等 Agent 主窗口当前领取了什么工作，但 Web 不负责 Agent 调度。
10. Web 与 CLI 必须共用同一套 Python Service、RunnerStore、锁和状态机。
11. 前端不能直接修改 `runner.json`，也不能直接修改 review 内部状态字段。
12. v1 保持本地、轻量：无账号、无数据库、无 WebSocket、无消息队列。

最终体验目标不是“展示 AI 很智能”，而是：

> Agent 已经做完绝大多数工作，人只处理剩下的少量决策。

---

## 3. 非目标

v1 明确不做：

- 跨用户、多角色、多权限；
- 公网部署；
- 登录注册；
- 多人同时审核同一条数据的协同编辑；
- 数据库、Redis、消息队列；
- WebSocket 实时推送；
- 独立 Review 数据库；
- Web 端直接启动 Codex / Claude Code / Trae；
- Web 端替 Agent 领取普通 topic work；
- 在线编辑 `SKILL.md`；
- 自动根据人工修正学习站点规则；
- 完整审计平台；
- 复杂权限与审批流；
- 回收站；
- Dark Mode；
- 无限画布式知识图谱编辑器；
- 把 XLSX 整体搬成网页表格；
- 针对某个站点写前端特例。

---

## 4. 产品信息架构

### 4.1 顶层结构

启动后先进入 Runner Picker，而不是跨 Runner 总 Inbox。

```text
Runner Picker
    ↓
Runner Workspace
    ├─ 工作台
    ├─ 待审核
    │   ├─ Quick Review
    │   └─ 来源审核详情
    ├─ 任务进度
    └─ 已完成
```

Runner 是整个 Web 工作空间的边界。

进入某个 Runner 后：

- 工作台只统计该 Runner；
- 待审核只显示该 Runner；
- 任务进度只显示该 Runner；
- 已完成只显示该 Runner；
- 来源审核详情必须位于该 Runner URL 空间下。

推荐路由：

```text
/runners
/runners/{runner_id}
/runners/{runner_id}/reviews
/runners/{runner_id}/reviews/{review_id}
/runners/{runner_id}/progress
/runners/{runner_id}/completed
```

路由本身表达当前 Runner 上下文，不依赖隐藏的全局 `selectedRunner` 才能恢复页面。

---

## 5. 视觉方向

### 5.1 产品气质

采用克制的 **Research Workbench / Research SaaS** 风格。

参考心智是：

- Linear 的信息密度与状态表达；
- Notion 的阅读层级；
- IDE Inspector 的局部编辑体验；
- Diff / Review 工具的“只强调需要人工处理的地方”。

不采用传统企业后台“大量蓝色按钮 + 表格 + 弹窗”的默认风格，也不采用赛博或知识图谱大画布。

### 5.2 基础视觉原则

- 页面背景：极浅灰；
- 主内容面板：白色；
- 正文：高对比深灰；
- 次要信息：低对比灰；
- 主交互强调：低饱和 Indigo / Blue；
- `needs_review`：暖橙 / Amber；
- `completed`：柔和绿色；
- `failed`：低饱和红；
- 颜色用于表达状态，不用于装饰；
- 避免满屏彩色 Tag 和重边框；
- 使用留白、字号和字重建立信息层级；
- 不在普通页面暴露内部 enum 和错误码。

例如底层：

```text
company_mapping_ambiguous
```

UI 应显示：

```text
2 家企业归属需要确认
```

### 5.3 页面文案原则

优先告诉人：

> 你现在需要做什么？

而不是：

> Agent 出现了什么内部状态？

例如：

```text
AI 已可靠处理 26 个节点，仅剩 2 家企业需要确认。
```

优于：

```text
stage=company_mapping
reason=company_mapping_ambiguous
status=pending_review
```

---

## 6. Runner Picker

### 6.1 页面目的

Runner Picker 是本地 Web 的第一层入口，同时承担 Runner 生命周期管理。

Runner 默认按最近活跃时间倒序排列。

“已闭环主题”明确指 topic 终态为：

```text
completed
no_qualified_source
```

`failed`、`awaiting_review`、`in_progress` 和 `pending` 均不计入闭环数量。

每张 Runner 卡展示：

- Runner 名称；
- 已闭环主题数 / 总主题数；
- 整体进度；
- 待审核数量；
- AI 处理中数量；
- 等待处理数量；
- 最近活动；
- 进入入口；
- `...` 菜单。

示意：

```text
┌──────────────────────────────────────────────┐
│ 锡膏专项研究                             ⋯ │
│                                              │
│ 82 / 100 已闭环                              │
│ ███████████████████████████████░░░░░         │
│                                              │
│ 待审核 6   AI处理中 4   等待处理 12          │
│                                              │
│ 最近活动 · 2分钟前                           │
│                                  进入 →      │
└──────────────────────────────────────────────┘
```

### 6.2 Runner 切换

进入 Runner Workspace 后，左上角提供 Runner selector：

```text
锡膏专项研究 ▾
```

下拉展示其他 Runner 及其待审核数量，并提供“查看所有 Runner”。

浏览器可记住上一次访问的 Runner ID，用于提供“继续上次研究”的便捷入口；该本地偏好不属于业务事实源。

### 6.3 Runner 删除

Runner 支持永久删除，不做回收站。

删除入口放在 Runner 卡或 Workspace 的 `...` 菜单中，不使用显眼的主按钮。

删除前必须满足：

- 当前 Runner 不存在有效 topic claim；
- 当前 Runner 不存在有效 review work claim。

存在 active work 时禁止删除，不提供 v1 强制删除。

二次确认内容需要明确：

- 将删除整个 Runner；
- 将删除 `runner.json`；
- 将删除该 Runner 的交付 XLSX；
- 将删除尚未处理的 review 数据；
- 不影响项目源码。

最终确认要求用户输入“删除”即可，不要求手输完整 Runner ID。

删除成功后：

- 当前 Workspace 跳回 `/runners`；
- 清除浏览器保存的 `last_runner_id`；
- Runner 从列表消失。

若 XLSX 被 Excel 等程序占用而导致删除失败，前端必须明确提示关闭文件后重试，不得显示假成功。

---

## 7. Runner Workspace 导航

进入 Runner 后左侧导航保持克制：

```text
锡膏专项研究 ▾

◉ 工作台
△ 待审核      6
◇ 任务进度
✓ 已完成

────────────
切换 Runner
```

v1 不增加大量管理菜单。

---

## 8. 工作台

### 8.1 页面目的

回答：

> 当前 Runner 里，我现在需要关心什么？

页面顶部说明：

> 只展示需要你判断的边界来源；正常来源由 Agent 自动完成。

### 8.2 核心指标

只展示与工作相关的数字：

- 待人工审核；
- AI 处理中；
- 已交回 AI；
- 今日闭环。

不做老板驾驶舱式指标，不展示无业务价值的环比、总行数等统计。

### 8.3 待处理卡片

Review Card 重点展示：

- 主题；
- 来源主体；
- 为什么送审；
- Agent 已完成什么；
- 人现在只需要做什么；
- 是否已有草稿；
- 待确认项数量。

有草稿和无草稿采用不同视觉形态。

无草稿示例：

```text
芯片产业链 · Supply Chain Explorer

⚠ 无法确认交互遍历是否完整

AI 已完成：
✓ 打开页面
✓ 识别可点击节点
✓ 验证点击后业务内容变化

你只需要判断：
是否允许 AI 继续自主遍历？

[打开来源]      [交回 AI 继续]
```

已有草稿示例：

```text
锡膏 · 某研究报告

⚠ 2 家企业归属需要确认
已可靠处理 26 / 28 个节点

[进入审核]
```

---

## 9. 待审核 Queue

### 9.1 页面定位

待审核页是高频审核 Inbox，用于连续处理多条 `needs_review`。

推荐三栏：

```text
审核队列 | 来源快速预览 | 当前需要你判断
```

目标是避免：

```text
列表 → 详情 → 返回 → 再找下一条
```

而实现：

```text
判断 → 下一条 → 判断 → 下一条
```

### 9.2 左栏：Queue

每条 review 只展示：

- 主题；
- 人类可读的问题；
- 待确认数量或“无草稿”；
- 等待时间。

不展示 review ID、内部状态码和 decision enum。

默认排序不做复杂评分，可由以下简单因素组成：

1. `focus_items` 数量较少的简单 review 优先；
2. 无草稿、需要人决定是否交回 AI 的 review 次之；
3. 复杂结构修正靠后；
4. 同级按创建时间。

### 9.3 中栏：Quick Preview

只显示与当前问题相关的产业链局部结构，不强制展示完整树。

例如 28 个节点只有 2 个问题时，只展示问题附近的上下文。

无 `draft_records` 时显示“尚未生成产业链草稿”，并展示 Agent 已确认和未确认的事项。

### 9.4 右栏：Quick Review

标题始终围绕：

> 你现在需要判断什么？

例如企业归属问题直接给候选：

```text
华光新材应该归属于哪个节点？

○ 上游 / 锡粉
○ 中游 / 锡膏制造
○ 无法归属
```

处理一个 `focus_item` 后自动切换下一个。

全部处理完成后才突出“修正后通过”。

### 9.5 Quick Review → Full Review

简单问题应尽量在 Queue 页解决。

以下情况升级到 Full Review：

- 新增或删除节点；
- 修改父子关系；
- 多个企业重挂；
- 复杂图文冲突；
- 需要查看完整产业链上下文。

进入 Full Review 时必须保留当前前端 working copy，不要求用户重复确认已完成的修改。

### 9.6 队列处理体验

Review 成功闭环后：

- 当前卡片显示短暂成功反馈；
- 从待审核队列移除；
- 自动选中下一条；
- 不要求人工返回列表重新点击。

v1 不提供“批量通过”。

### 9.7 基础快捷键

建议：

```text
J / K       下一条 / 上一条 review
N / P       下一个 / 上一个 focus item
Enter       确认当前选择
O           打开来源
E           进入完整编辑
R           交回 AI
Cmd/Ctrl+Enter  修正后通过
```

快捷键仅作为效率增强，不是唯一操作方式。

---

## 10. 来源审核详情 Full Review Workbench

### 10.1 布局

推荐固定顶部上下文栏 + 三栏主体 + 固定底部决策栏。

```text
┌───────────────────────────────────────────────────────────────┐
│ ← 待审核   主题 / 来源                         打开原文 ↗     │
├────────────────┬──────────────────────────┬───────────────────┤
│ 来源与 AI 判断 │      产业链结构          │ 本次需要你确认    │
│                │                          │                   │
│ 为什么送审     │ 上游                     │ 问题 1 / 2        │
│ AI 已完成      │ ├─ 锡粉                  │                   │
│ 当前不确定     │ │  └─ 华光新材 ⚠         │ 当前证据与选项    │
│ 处理过程       │ └─ 助焊剂                │                   │
│                │                          │                   │
├────────────────┴──────────────────────────┴───────────────────┤
│ 2 处待确认              驳回来源  交回 AI 继续  修正后通过 → │
└───────────────────────────────────────────────────────────────┘
```

推荐宽度比例约：

```text
25% / 50% / 25%
```

产业链结构始终是视觉中心。

### 10.2 顶部来源上下文

固定展示：

- 返回待审核；
- 主题；
- 来源主体；
- 来源 URL / 来源位置摘要；
- 人类可读状态；
- 打开原始来源。

原网页、PDF、交互网站使用系统浏览器新 Tab 打开。v1 不为外部网页建立镜像，也不要求内嵌 iframe。

### 10.3 左栏：来源判断

按故事顺序展示：

1. 为什么送审；
2. Agent 已完成；
3. 当前不确定；
4. 可选的极简处理过程。

处理过程来自 `events`，只展示业务事实，不展示 Agent chain-of-thought、Prompt、token、temperature 等内部推理信息。

### 10.4 中栏：产业链 Tree View

Tree View 是正式审核主界面。

九字段 `records` 是数据协议，不是人工主界面。

展示规则：

- 分类节点按层级显示树；
- 企业显示为节点下的小型 Chip / Item；
- Agent 不确定项使用暖橙强调；
- 人工新增或修改项可用极轻的“已改 / 人工新增”提示；
- 默认自动滚动到第一个 `focus_item`；
- 已确认项恢复普通视觉，随后自动定位下一个问题。

### 10.5 Tree 编辑能力

人工拥有最终编辑权，v1 允许：

- 重命名节点；
- 新增同级节点；
- 新增子节点；
- 删除节点；
- 修改节点父子关系；
- 新增企业；
- 删除企业；
- 将企业移动到其他节点；
- 将企业保持为无法归属；
- 新增 Agent 完全没有识别出的节点或企业。

节点支持直接编辑名称。

移动节点可支持拖拽，但必须同时提供确定性的父节点选择方式，避免精确编辑只能依赖拖拽。

企业重挂使用节点搜索器，不要求人工直接填写 `分类1` ~ `分类4`。

### 10.6 右栏 Inspector

点击节点或企业时，不弹大 Modal，而在右侧 Inspector 中展示属性和操作。

节点 Inspector 包含：

- 节点名称；
- 当前路径；
- 企业列表；
- 重命名；
- 调整父节点；
- 添加企业；
- 添加子节点。

企业 Inspector 包含：

- 企业名称；
- 当前路径；
- 候选归属（如 Agent 已给出）；
- 搜索并移动到其他节点；
- 保持无法归属；
- 删除企业。

### 10.7 无草稿状态

`draft_records=[]` 是合法状态。

此时中栏不显示空表，也不生成伪树，而展示：

```text
尚未生成产业链草稿

Agent 已发现该来源需要交互式浏览。

✓ 已识别可点击节点
✓ 点击后业务内容发生变化
? 无法确认是否已完整遍历

[打开原始来源]
```

右栏集中展示是否“交回 AI 继续”。

v1 无草稿状态不提供从空白开始手工构建完整产业链的入口；此时可执行的业务决策为：

- `交回 AI 继续`；
- `驳回来源`。

因此 `draft_records=[]` 时“修正后通过”必须 disabled。纯人工从零构建来源若未来确有需求，应作为独立能力设计，不能用空 records 绕过正式来源校验。

---

## 11. 底部决策栏

Full Review 页面底部 Action Bar 始终可见。

普通草稿：

```text
2 处待确认             驳回来源   交回 AI 继续   修正后通过 →
```

全部 focus 已处理：

```text
✓ 所有待确认问题已处理              驳回来源   修正后通过 →
```

无草稿：

```text
暂无可提交草稿                     驳回来源   交回 AI 继续 →
```

### 11.1 修正后通过

最终确认面板只展示有业务意义的信息：

- 节点数量；
- 企业数量；
- 人工修改数量摘要；
- 将写入正式 Runner；
- 将刷新交付 XLSX；
- 当前 review 将闭环。

### 11.2 驳回来源

原因保持极简：

- 与主题无关；
- 不构成有效产业链；
- 来源质量不足；
- 内容无法可靠使用；
- 其他。

备注可选。

### 11.3 交回 AI 继续

确认面板必须明确：

- 只允许 Agent 继续处理当前 review_item；
- 只作用当前 URL；
- 只 bypass 当前送审 reason；
- Agent 不得因相同问题原样再次送审；
- 遇到新的不确定问题仍可重新进入人工审核；
- 不建立域名白名单；
- 不影响其他 URL；
- 不自动修改 Skill。

---

## 12. Tree 与 records 的边界

Runner 不新增独立 `draft_tree` 事实源。

数据流：

```text
review_item.draft_records
        ↓
前端 records → tree
        ↓
Tree View / Inspector 编辑
        ↓
前端 tree → records
        ↓
ReviewService approve
        ↓
正式 source_group
```

Tree 是 UI 表达；九字段 records 仍是 Client / Service 的业务协议。

这样避免 `draft_tree` 与 `draft_records` 双事实源不同步。

---

## 13. 前端 Working Copy

审核编辑不采用“每改一个字段就立刻写 Runner”的方式。

流程：

```text
加载 review draft
↓
浏览器内 working copy
↓
人工完成全部修改
↓
一次性提交完整 records
↓
ReviewService 原子校验与写入
```

Quick Review 与 Full Review 必须共享同一个当前 working copy。

v1 可在浏览器本地存储未提交 working copy，以避免意外刷新丢失编辑；它只是恢复辅助，绝不是业务事实源。

本地草稿 key 必须包含至少：

```text
runner_id + review_item_id + review version
```

当服务端 review version 已变化时，不自动把旧本地草稿覆盖到新版本。

---

## 14. 任务进度页

### 14.1 页面目的

回答：

> 当前 Runner 跑到哪了？

它是监控页，不是人工调度板。

### 14.2 顶部业务状态

展示：

- 已闭环 / 总主题；
- 已完成；
- AI 处理中；
- 待人工审核；
- 等待处理；
- 执行异常（存在时）。

UI 使用人类可读文案：

```text
pending             → 等待处理
in_progress         → AI 处理中
awaiting_review     → 待人工审核
completed           → 已完成
no_qualified_source → 无合格来源
failed              → 执行异常
```

### 14.3 流水线视图

可使用只读列式视图：

```text
等待处理 | AI处理中 | 待人工 | 已完成
```

不允许拖动卡片改变状态。

### 14.4 Agent Work

展示当前 Agent work：

```text
Codex       PCB焊接      6m
Claude Code 焊锡材料     3m
```

`worker_label` 只是观察信息，不参与调度。

若没有 label，只显示“Agent 正在处理”。

人工退回任务必须有独立的可读状态：

```text
↻ 已交回 AI，等待领取
↻ AI 正在继续处理
↻ 已重新处理，本次出现新的审核问题
```

### 14.5 Activity Feed

展示极简业务事件：

```text
10:31 Claude Code 完成「锡粉」· 3 个正式来源
10:28 「芯片产业链」被人工交回 AI
10:26 「精密结构件」进入人工审核
10:12 「助焊剂」无合格来源
```

这是状态理解工具，不是完整审计日志。

### 14.6 Topic 侧栏

点击 Topic 可打开只读聚合 Drawer：

- 当前状态；
- 正式来源数量；
- 待审核来源数量；
- 来源列表；
- 进入具体 review 的入口。

任务进度页不直接编辑节点、企业或 review 内部状态。

---

## 15. 已完成页

保持简单历史视图：

```text
✓ 锡膏 · 某研究院
  修正后通过 · 人工修改 2 处

✓ 芯片产业链 · Chip Explorer
  Agent 二次处理后通过

× 某营销网站
  人工驳回
```

支持：

- 搜索；
- 查看来源；
- 查看处理记录。

v1 不做审核绩效排名或复杂数据分析。

---

## 16. 前端与 Python Core 的架构边界

### 16.1 总体结构

```text
Human Browser
React + TypeScript
        │ HTTP
        ▼
FastAPI
薄 HTTP Adapter
        │
        ▼
Python Application Core
RunnerService
DatasetService
ReviewService
WorkService
        │
        ▼
RunnerStore
        │
runner.json + XLSX

Codex / Claude Code / Trae
        │ CLI
        ▼
CLI Adapter
        │
        └────→ 同一个 Python Application Core
```

核心原则：

> CLI 和 FastAPI 是同一套业务 Service 的两个 Adapter，不是两套实现。

### 16.2 Agent 入口

Agent 继续只使用 CLI：

```text
industry-chain work claim-next
industry-chain work renew
industry-chain work finish
industry-chain work fail
```

流水线优先级、claim、lease 和工作状态由 WorkService / CLI 管理。

Web 不负责领取或执行 Agent work。

### 16.3 Human 入口

Web 是人工审核的标准 UX 入口，使用 FastAPI 调用 ReviewService、RunnerService 和只读查询接口。

底层 CLI 可以保留与 Service 等价的审核业务命令，用于 Agent 协议、测试或调试；但前端不通过 subprocess 调 CLI，正常人工审核流程也不要求用户手敲命令。

前端只提交业务动作，例如：

```text
approve
return-to-agent
reject
retry topic
remove runner
```

禁止提供通用接口让前端任意 `PATCH review.status`。

---

## 17. FastAPI 设计原则

FastAPI 是薄 HTTP Adapter，不重新实现业务状态机。

推荐核心 API 范围：

```text
GET    /api/runners
GET    /api/runners/{runner_id}
DELETE /api/runners/{runner_id}

GET    /api/runners/{runner_id}/dashboard
GET    /api/runners/{runner_id}/reviews
GET    /api/runners/{runner_id}/reviews/{review_id}
GET    /api/runners/{runner_id}/activity

POST   /api/runners/{runner_id}/reviews/{review_id}/approve
POST   /api/runners/{runner_id}/reviews/{review_id}/return-to-agent
POST   /api/runners/{runner_id}/reviews/{review_id}/reject

POST   /api/runners/{runner_id}/topics/{node_id}/retry
```

最终 endpoint 命名可在实现计划中微调，但必须保持“业务动作 API”而非“任意状态 PATCH”。

---

## 18. HTTP View Model

前端不直接读取或理解原始 `runner.json`。

必须区分：

```text
Runner JSON = 持久化模型
HTTP JSON   = UI View Model
```

例如 Review List 返回人类可读字段：

```json
{
  "id": "review_123",
  "topic": "锡膏",
  "source_name": "某研究院",
  "source_url": "https://example.com",
  "display_reason": "2 家企业归属需要确认",
  "focus_count": 2,
  "has_draft": true,
  "created_at": "..."
}
```

前端不自行根据多个 Runner 内部字段推导核心业务状态。

---

## 19. 并发与版本保护

### 19.1 Runner 文件锁

CLI 与 FastAPI 最终都必须通过 `RunnerStore` 修改数据，继续使用 Runner 级文件锁和原子写入能力。

任何 Web 路由和 React 代码都不得直接修改 `runner.json`。

### 19.2 review_item.version

仅有文件锁无法阻止“人拿着旧页面覆盖 Agent 新结果”。

因此 v1 为 `review_item` 增加轻量版本号：

```text
version: integer
```

review 发生业务修改时递增。

人工提交业务动作时必须带：

```text
expected_version
```

ReviewService 校验：

```text
expected_version == current version
```

不一致则返回冲突，不覆盖新状态。

前端显示：

```text
这条审核任务刚刚发生了变化。
请查看最新结果后再提交。
```

推荐 HTTP 语义：`409 Conflict`。

不引入全 Runner revision。

### 19.3 当前编辑对象刷新规则

列表、Runner 进度可以后台刷新，但当前正在编辑的 review 不允许自动被服务器数据覆盖。

检测到 version 变化时只提示“已有新版本”，由用户主动加载。

---

## 20. Polling 与实时性

v1 不使用 WebSocket。

推荐：

```text
工作台       5 秒刷新
任务进度     5 秒刷新
审核队列     10 秒刷新
当前审核项   不自动覆盖
```

浏览器 Tab 从后台重新获得焦点时立即刷新列表和状态。

这足以满足 localhost 内部工具的实时感，同时避免增加实时基础设施。

---

## 21. 本地运行模式

### 21.1 统一启动入口

推荐新增：

```text
industry-chain web
```

职责：

1. 解析 `runs_root`；
2. 检查本地 Web 服务是否已运行；
3. 启动 FastAPI；
4. 挂载 React production build；
5. 绑定 `127.0.0.1`；
6. 自动打开默认浏览器；
7. Ctrl+C 停止服务。

默认访问：

```text
http://127.0.0.1:8765
```

端口可在实现阶段参数化。

### 21.2 runs_root

默认继续使用当前项目约定的 `runs/`。

允许：

```text
industry-chain web --runs-root <path>
```

Web 直接基于该 RunnerStore 工作，不需要上传 Runner 或导入 XLSX。

### 21.3 单实例体验

可使用轻量 `.web.lock` 或端口检测避免用户对同一 runs_root 意外启动多个 Web 服务。

若已存在服务，命令优先提示已有地址并打开浏览器，而不是无意义启动第二份服务。

### 21.4 本地服务边界

v1 默认只绑定：

```text
127.0.0.1
```

不绑定 `0.0.0.0`，不作为局域网服务设计。

因此 v1 无需登录和权限系统。

---

## 22. 前端技术栈

推荐：

```text
React
TypeScript
Vite
```

理由：

- Review Queue 有较多局部状态；
- Full Review 有 Tree 编辑与 Inspector；
- Quick Review / Full Review 需要共享 working copy；
- 需要键盘交互和局部刷新；
- 后续仍可保持单页应用规模，不需要引入大型前端框架。

可以使用基础 UI primitives，但不要直接套默认 Admin Dashboard 视觉。

生产运行不长期保留 Node 服务：

```text
Vite build
↓
FastAPI 挂载静态文件
```

开发环境才使用：

```text
Vite dev server
FastAPI dev server
```

---

## 23. 错误与异常体验

### 23.1 XLSX 被占用

当现有存储层返回 XLSX 占用错误时，UI 转换成人类文案：

```text
保存失败
交付 Excel 可能正在被其他程序占用。
关闭文件后重试。
```

### 23.2 Review 版本冲突

显示：

```text
这条审核任务已经发生变化。

Agent 或其他操作刚刚更新了当前来源。
请加载最新版本后继续。
```

不自动覆盖用户正在编辑的内容。

### 23.3 Runner active work 删除冲突

显示正在执行的 Agent work，并禁止删除。

### 23.4 Agent work 失败

任务进度页显示人类可理解的执行异常和最后成功动作。

Review work 的局部失败不把整个 topic 误标为全局失败；其业务规则遵循核心 HITL 设计。

---

## 24. XLSX 与来源文件操作

### 24.1 XLSX

XLSX 仍由 Runner / Dataset 持续投影，不在 Web 中维护第二份交付数据。

Runner 页面可以提供：

- 获取当前交付 XLSX；
- 复制 XLSX 本地文件路径。

### 24.2 原始来源

审核页提供“打开原文 / 打开 PDF / 打开 Explorer”。

使用系统浏览器新 Tab 打开原始 URL。

v1 不实现远程网页镜像、站点代理或通用网页内嵌系统。

---

## 25. Agent 主窗口协作体验

Runner 页面可提供“复制 Agent 启动指令”。

示例语义：

```text
阅读 skills/researching-industry-chains/SKILL.md，
继续处理 Runner <runner_id>。
从 CLI work claim-next 领取工作并持续执行，
不要自行选择任务。
```

该功能只生成文本，不启动 Agent。

Agent claim 时可附可选 `worker_label`，例如：

```text
Codex
Claude Code
Trae
```

用于 Runner UI 展示，不影响 WorkService 调度。

---

## 26. v1 页面验收标准

### Case A：Runner 选择

存在多个 Runner 时：

- 首页可搜索并选择 Runner；
- 进入后所有页面都只显示该 Runner；
- 可从左上角切换 Runner；
- 刷新页面仍能恢复当前 Runner URL。

### Case B：简单 Quick Review

一个来源只有 1 家企业归属不确定：

- Queue 默认定位该问题；
- 人可直接选择归属；
- 不必进入 Full Review；
- 通过后自动进入下一条待审核。

### Case C：复杂 Tree Review

Agent 已解析大部分树但漏节点：

- 人可以新增节点；
- 可以新增企业；
- 可以调整企业归属；
- 可以改变父子关系；
- 提交后转换为完整九字段 records；
- ReviewService 校验通过后成为正式 source_group；
- XLSX 更新。

### Case D：无草稿交互来源

Chip Explorer 类 review：

- `draft_records=[]` 能正常显示；
- 页面明确说明 Agent 已完成什么、卡在哪里；
- “修正后通过”不可直接使用；
- 人可“交回 AI 继续”或驳回来源；
- UI 明确说明 override 只作用当前 review / URL / reason。

### Case E：再次送审

同一 URL 人工放行后 Agent 遇到新的问题：

- 同一个 review 卡片再次进入待审核；
- UI 显示“已重新处理”；
- 可看到上一次问题已被人工放行；
- 当前只突出新的问题。

### Case F：版本冲突

人工打开 review version 3，Agent 更新为 version 4：

- 人提交 version 3 时不得覆盖 version 4；
- API 返回冲突；
- UI 提醒加载最新结果。

### Case G：Agent 与 Web 同时运行

Codex 正处理 Topic A，人在浏览器审核 Topic B：

- 两边均通过同一个 RunnerStore；
- Runner 文件不损坏；
- XLSX 与 JSON 保持一致；
- Runner 页面能看到 Agent work。

### Case H：Runner 删除

Runner 无 active work：

- 可从 Web 删除；
- 二次确认；
- Runner JSON 与 XLSX 一并删除；
- 页面回到 Runner Picker。

Runner 有 active work：

- 删除被拒绝；
- UI 展示当前执行 work；
- v1 不提供强制删除。

### Case I：本地启动

执行：

```text
industry-chain web
```

预期：

- 服务绑定 localhost；
- 使用指定 runs_root；
- 打开浏览器；
- React 和 API 同一入口可用；
- 无需 Node production server；
- 无需登录。

---

## 27. 实现边界建议

本文不规定最终文件拆分，但推荐保持职责小而明确。

Python Core：

```text
runner.py       Runner 生命周期与 topic 状态
review.py       ReviewService 与审核业务动作
work.py         WorkService 与 Agent 调度
storage.py      RunnerStore 与文件锁
api.py / web/   FastAPI 薄 Adapter
```

Frontend：

```text
app shell
runner picker
workspace dashboard
review queue
review workbench
progress
completed
shared tree editor / inspector
API client
working-copy state
```

避免把完整审核 Workbench、API 请求、Tree 转换和业务动作全部堆在单个超大 React 文件中。

---

## 28. 后续能力，不属于 v1

以下能力可以未来单独设计，不进入本次实现范围：

- 内网多人部署；
- 登录与审核人身份；
- 权限；
- 站点级规则建议；
- 人工修改统计和 Skill 优化分析；
- 更细粒度 evidence schema；
- AI 对人工结果进行只读 re-analysis / diff 建议；
- WebSocket；
- 数据库迁移；
- 回收站；
- 多人协同审核；
- 从 `draft_records=[]` 开始纯人工构建完整来源；
- Dark Mode。

---

## 29. 最终设计原则

v1 的前端和本地 Web 必须始终守住以下边界：

1. **Runner 是工作空间边界。**
2. **Agent 的标准任务入口是 CLI。**
3. **Human 的标准审核体验入口是 Web；CLI 与 Web 可共享等价 Service 业务动作。**
4. **CLI 与 Web 共用同一套 Python Service。**
5. **Runner JSON 是唯一任务事实源。**
6. **XLSX 只投影正式 source_groups。**
7. **Tree 是 UI，不是第二数据模型。**
8. **待审核数据不提前污染正式数据。**
9. **人工编辑一次提交，避免半完成状态不断写 Runner。**
10. **版本冲突必须显式失败，不能静默覆盖。**
11. **Web 不直接改 runner.json，不直接 PATCH 内部状态。**
12. **localhost v1 不为未来多人场景提前增加基础设施。**
13. **审核页始终优先展示“人现在只需要判断什么”。**
14. **Runner 删除永久生效，但 active Agent work 时禁止删除。**
15. **优先把审核工作压缩成决策，而不是让人重新研究一遍来源。**
