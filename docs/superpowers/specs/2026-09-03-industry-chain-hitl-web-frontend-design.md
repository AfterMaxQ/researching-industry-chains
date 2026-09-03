# 产业链 HITL 审核前端与本地 Web 架构设计 v1

## 1. 目的

本文定义 `researching-industry-chains` 的 HITL 本地 Web 审核界面。

配套核心设计：

- `docs/superpowers/specs/2026-09-03-industry-chain-human-review-design.md`

v1 是**单机 localhost 研究审核工作台**。

前端只解决：

> 人如何快速理解一个被 Agent 送审的来源、找到审核位置、查看当前产业链 Tree、必要时修正 Tree 和来源说明，并提交最终审核动作。

最终 XLSX 由 Core Service 根据最终 Tree 确定性生成，Web 不直接编辑 Excel 行。

---

## 2. 产品原则

1. Runner 是最外层工作空间。
2. Quick Review 只读；所有 Tree / description 编辑只发生在 Full Review。
3. 审核心智模型是 `source + description + chain + uncertainties`，不是九字段 records。
4. `description` 同时是最终 XLSX 第一行 `备注` 的内容。
5. uncertainty 不是 Agent 向人提问，而是“哪里不确定、为什么、去哪里看”。
6. Evidence v1 只显示 `locator + description`，不做截图资产、图片渲染、Lightbox、OCR 或 Evidence DB。
7. focus 由 uncertainty 在 Tree 中的位置动态派生，不做问答对象。
8. 人工决策是来源级：采用当前结果、修正后通过、交回 AI 继续、驳回来源。
9. Web 不直接 patch Runner JSON 或 status，全部调用共享 Python Core。
10. 无用户系统、数据库、WebSocket、消息队列或统计后台。

---

## 3. 信息架构

```text
/runners
  ↓
/runners/{runner_id}
  ├─ 工作台
  ├─ 待审核
  ├─ 任务进度
  └─ 已完成
```

路由：

```text
/runners
/runners/{runner_id}
/runners/{runner_id}/reviews
/runners/{runner_id}/reviews/{review_id}
/runners/{runner_id}/progress
/runners/{runner_id}/completed
```

侧边栏只保留：

```text
当前 Runner
工作台
待审核
任务进度
已完成
切换 Runner
```

不出现用户头像、个人中心、通知中心、知识库、数据源管理、Agent 管理、统计分析或大型设置菜单。

---

## 4. Runner Picker

Runner 卡片显示：

- Runner 名称 / 创建时间；
- 已完成 / 总主题；
- 待人工审核数量；
- AI 处理中数量；
- 最近更新时间。

“已完成”统计：

```text
completed + no_qualified_source
```

单个 `no_qualified_source` 仍显示“无合格来源”。

### 删除 Runner

- 永久删除，无回收站；
- 有有效 topic / review claim 时拒绝；
- 无 force delete；
- 输入 `删除` 二次确认；
- 删除 Runner JSON、XLSX 和相关运行文件；
- v1 无 Evidence Asset 目录；
- XLSX 被占用时显示明确错误。

---

## 5. 工作台：极薄 Overview

固定四个指标：

```text
待人工审核
AI处理中
已交回AI
今日完成
```

下面最多显示：

- 最近 3 个待审核来源；
- 少量最近 Activity。

不做趋势、环比、企业总量、模型成功率、审核效率或 Worker 排行。

---

## 6. Quick Review

Quick Review **严格只读**。

三栏：

```text
审核队列 | 来源 / Tree 快速预览 | 审核处理
```

### 队列项

显示：

- 主题；
- `source.name`；
- `source.url` 的可读部分；
- 当前状态；
- uncertainty 数量；
- 最近更新时间。

不依赖独立 `source.title` 字段。

### 快速预览

显示：

- description 只读；
- Tree 只读；
- 当前 uncertainty message；
- 相关审核依据。

Quick Review 无 working copy，不允许改节点、拖拽、改企业或改 description。

### 动作

```text
查看审核依据
打开完整审核
采用当前结果
交回 AI 继续
驳回来源
```

- chain 非空时才可采用；
- `chain=[]` 只能交回 AI 或驳回；
- 不做批量 approve。

---

## 7. Full Review

Full Review 是唯一编辑面。

三栏：

```text
审核依据        产业链草稿        审核处理
约 25%          约 50%            约 25%
```

顶部固定展示：

- 主题；
- `source.name`；
- `source.url`；
- review 人类可读状态；
- 打开原来源；
- `description` 编辑区，标签：`来源说明（最终备注）`。

`description + chain` 一起构成 working copy。

Client 不自动根据 Tree 改写 description。

---

## 8. 审核依据

v1 不做来源渲染系统。

左栏只回答：

```text
去哪里看？
为什么看这里？
```

Evidence 卡片：

```text
locator
description
```

例如：

```text
PDF 第17页 · 图5
图中能看到华光新材，但与锡粉节点的直接连接不清楚。
```

一个 uncertainty：

- 可以没有 Evidence；
- 也可以有多条 Evidence；
- 多条可分别指向产业链结构、正文和企业归属位置。

没有 Evidence 时仍展示 uncertainty message 和 `打开原来源`，不要求 Agent 为满足 UI 强行制造截图或 locator。

v1 不做：

```text
Evidence ID
图片缩略图
Lightbox
zoom / drag
OCR
bounding box
截图资产
Evidence Asset API
PDF crop
网页镜像
浏览器录像
```

Agent 可以截图完成视觉研究，但截图不进入前端持久化模型。

---

## 9. uncertainty 与 focus

不出现：

```text
问题
候选答案
推荐答案
单选框
多选框
human_answer
```

### 来源级

根级 uncertainty → source focus。

### 节点级

node uncertainty 且无 company → node focus，定位当前 root-to-node path。

### 企业 occurrence

node uncertainty 带 company → company focus，定位：

```text
node path + company
```

因此同一家企业出现在多个节点时不会串位。

`focus_items` 不要求持久化。ViewModel 根据 uncertainty 所在位置动态派生。

点击 focus：

- Tree 定位到对应节点；
- company focus 高亮当前节点下该企业；
- 左栏显示相关 Evidence；
- 右栏显示 uncertainty message。

---

## 10. Tree 编辑

Tree 直接来自 review_item `chain`。

不维护：

```text
draft_records + draft_tree
```

### 非空 Tree

支持：

```text
rename
add root
add sibling
add child
delete
change parent
同父拖拽排序
跨父拖拽整棵子树
新增遗漏节点
```

跨父级移动时整棵子树递归跟随。

拒绝：

- 拖到自己下面；
- 拖到自己的后代下面；
- 移动后正式分类深度超过 4。

父级选择器和拖拽使用同一 reparent 语义。

删除有后代的节点必须明确提示影响。

当前 Tree 顺序就是最终 records 的稳定输出顺序，不维护第二套 order。

### 初始 `chain=[]`

这是无草稿 review。

v1 **不启用 Tree 编辑器，也不允许 add root 从零建链**。

只能：

```text
交回 AI 继续
驳回来源
```

---

## 11. 企业编辑

企业对应：

```text
companies: string[]
```

支持：

- 添加；
- 删除；
- 重命名；
- 移动到其他节点；
- 新增 Agent 遗漏企业。

不展示企业组层级。

最终同节点企业由 Client 用 `、` 合并进 XLSX `公司` 字段。

如果 uncertainty.company 存在，必须能在当前节点 companies 中找到对应企业。

如果人工确认某企业确实在来源中出现但无法归属任何节点，可把：

```text
发现但无法归属：A公司、B公司
```

写入 `description`，随最终 XLSX 第一行备注交付；不新增独立 unresolved 字段。

---

## 12. Working Copy

Full Review working copy 只有：

```text
chain
description
```

uncertainties / Evidence 是审核上下文，不要求人工逐条编辑或“回答”。

页面不按每个按键写 Runner。

可用：

```text
runner_id + review_item_id + review_version
```

保存浏览器本地临时 working copy。

人工通过时一次性提交：

```text
final chain
final description
expected_version
```

Core Service：

```text
Tree validate
↓
Tree → 九字段
↓
DatasetService validate
↓
原子写正式来源
↓
刷新 XLSX
```

---

## 13. 审核处理栏

默认展示：

- review 状态；
- 当前 uncertainty message；
- 当前定位对象：来源 / 节点路径 / 企业 occurrence；
- 关联 Evidence locator；
- 来源级审核动作。

可折叠显示少量 Agent 已确认事实，但不展示 chain-of-thought。

点击 Tree 节点或企业时，右栏可临时切换 Inspector；关闭后返回审核处理。不增加第四列。

---

## 14. 审核动作

### 采用当前结果

working copy 未修改且 chain 非空。

### 修正后通过

Tree 或 description 被修改后。

两者底层都是 `approve`，区别只是是否提交修改后的 working copy。

### 交回 AI 继续

只作用当前 review_item 当前 version。

不配置域名白名单、parser 规则或 Skill 修改。

同一 version 只允许 return 一次；Agent 返回新 SourceResult 后 version 更新，用户再基于新结果处理。

### 驳回来源

不生成正式 source_group，不写 XLSX。

---

## 15. Quick / Full 边界

```text
Quick Review
= 看 + 决策

Full Review
= 看 + 编辑 + 决策
```

任何以下动作必须进 Full Review：

- 改节点；
- 改顺序 / 父级；
- 新增 / 删除节点；
- 企业增删改 / 换节点；
- 改 description。

避免两套 Tree 编辑器。

---

## 16. 任务进度

只读。

顶部：

```text
已完成 / 总主题
```

“已完成”包含：

```text
completed
no_qualified_source
```

标签：

```text
pending              等待处理
in_progress          AI处理中
awaiting_review      待人工审核
completed            已完成
no_qualified_source  无合格来源
failed               执行异常
```

推荐列：

```text
等待处理 | AI处理中 | 待人工 | 已完成
```

`no_qualified_source` 在已完成列中显示“无合格来源”。

不允许拖拽 topic 状态。Codex / Claude / Trae 只作为观察中的 worker 信息。

---

## 17. 已完成

包含：

```text
completed
no_qualified_source
```

支持：

- 搜索主题；
- 查看最终来源；
- 查看最终 Tree / description；
- 查看简要审核记录；
- 打开来源 URL。

不做性能排行榜或统计分析。

---

## 18. Activity

只记录最小业务事实：

```text
主题被领取
正式来源写入
来源进入人工审核
人工交回 AI
Agent 重新提交
来源已采用
来源被驳回
主题已完成
主题无合格来源
```

不展示 Prompt、token、完整推理、浏览器操作录像或调试日志瀑布流。

---

## 19. Web 架构

```text
Browser / React + TypeScript
        │
        ▼
FastAPI thin adapter
        │
        ▼
Python Core
RunnerService
DatasetService
ReviewService
WorkService
SourceResult Compiler
        │
        ▼
RunnerStore
runner.json + XLSX
```

CLI 与 Web 共用 Python Core。

Web 不：

- 直接 patch Runner JSON；
- 暴露通用 `PATCH status`；
- 实现第二套状态机；
- 自己实现 Tree → 九字段。

---

## 20. Review ViewModel

建议：

```text
review_id
version
topic
source
  name
  url
description
chain
uncertainties
status
actions
events
```

focus 从 chain + uncertainties 动态派生。

不要求：

```text
draft_records
draft_tree
evidence_id
evidence_assets
focus_item_id
question
options
recommended_answer
human_answer
```

`stage / reason` 如果 Core 仍提供，只是可选展示 metadata，前端不得依赖它决定业务动作。

---

## 21. API

读：

```text
GET /api/runners
GET /api/runners/{runner_id}
GET /api/runners/{runner_id}/dashboard
GET /api/runners/{runner_id}/reviews
GET /api/runners/{runner_id}/reviews/{review_id}
GET /api/runners/{runner_id}/progress
GET /api/runners/{runner_id}/completed
GET /api/runners/{runner_id}/activity
```

写：

```text
POST /api/runners/{runner_id}/reviews/{review_id}/approve
POST /api/runners/{runner_id}/reviews/{review_id}/return-to-agent
POST /api/runners/{runner_id}/reviews/{review_id}/reject
POST /api/runners/{runner_id}/topics/{topic_id}/retry
DELETE /api/runners/{runner_id}
```

approve：

```json
{
  "expected_version": 3,
  "description": "最终来源说明",
  "chain": []
}
```

Core 对 `chain=[]` approve 返回业务错误。

Web 不需要 Evidence asset endpoint。

---

## 22. 并发与刷新

人工写动作必须带 `expected_version`。

版本冲突：

```text
409 REVIEW_VERSION_CONFLICT
```

页面保留本地 working copy，不静默覆盖。

Polling：

```text
工作台    5s
任务进度  5s
审核队列  10s
```

Full Review 正在编辑时不自动替换 Tree；后台版本变化只提示重新加载 / 对比。

不引入 WebSocket。

---

## 23. 错误体验

### XLSX 被占用

明确说明正式写入未完成，请关闭占用文件后重试。

### 非法 Tree 操作

不生效，并说明：不能移动到自己 / 后代下面，或正式分类超过 4 层。

### 企业 uncertainty 结构失效

如果 uncertainty.company 不在当前节点 companies 中，提示重新加载或让 Agent 重新提交。

### 来源打不开

仍保留 uncertainty 和 locator / description；不伪造缓存截图。

---

## 24. 本地启动

```text
industry-chain web
```

默认：

```text
127.0.0.1:8765
```

- FastAPI 单进程；
- 服务 Vite production build；
- 自动打开浏览器；
- Node 仅用于前端开发 / 构建；
- 无登录。

---

## 25. Agent 协作边界

Web 可以显示可复制的 Agent 启动说明，但不直接启动或管理 Agent。

Agent-facing 动作仍是：

```text
work claim-next
source submit
work done（仅 topic work）
work fail
```

Web 只观察结果。

---

## 26. 视觉风格

官方风格：**Warm Editorial Research Workbench**。

关键词：warm、restrained、research editorial room、clear、professional、low cognitive load、high information density without crowding。

色彩：

```text
background        #FAF6F0
surface           #FFFDFC
secondary surface #F7EFE7
border            #E9DCD1
primary text      #2E2622
secondary text    #776C65
primary           #C65F49
primary hover     #B8533F
review/warning    #D9913D
success           #78906B
error             #B85F55
```

规则：

- 10–12px 圆角；
- 1px 暖色 border；
- 很轻的 shadow；
- 细线图标；
- chip 少量使用；
- 不使用渐变、玻璃、霓虹、大面积彩色标签；
- v1 不做 Dark Mode。

字体：Inter / system sans、PingFang SC、Microsoft YaHei。

---

## 27. v1 非目标

不做：

- 公网、多用户、角色权限；
- 多人实时协同；
- DB / Redis / MQ / WebSocket；
- Evidence DB / Evidence Asset / 截图归档；
- 图片 Viewer / Lightbox / OCR / bounding box；
- 网页镜像 / 浏览器录像；
- `draft_records` 编辑；
- XLSX 网页编辑器；
- 无限画布知识图谱；
- 问答式 review；
- Quick Review 编辑；
- 从 `chain=[]` 纯人工从零建链；
- 用户头像 / 个人中心 / 通知中心；
- 知识库 / 数据源管理 / Agent 管理；
- 统计分析后台；
- 暗色模式；
- 回收站；
- 站点专用 parser UI。

---

## 28. 验收

1. Runner 选择、统计和有 claim 时禁止删除正确。
2. 工作台只有四个核心指标、最近待审和少量 Activity。
3. Quick Review 严格只读。
4. Full Review 明确显示 topic、source.name、source.url 和可编辑“来源说明（最终备注）”。
5. uncertainty 没有 Evidence 也能审核；有 Evidence 时可显示多条 locator + description。
6. source / node / company occurrence focus 能按位置正确派生。
7. 同名企业多节点时不会串位。
8. 非空 Tree 支持新增、排序、整棵子树 reparent，循环和 >4 层被阻止。
9. 企业支持增删改和跨节点移动；最终由 Client 用 `、` 合并。
10. 初始 `chain=[]` 不启用 Tree 编辑或 add root，只能交回 AI / 驳回。
11. description 修改后通过，最终内容进入 XLSX 第一行备注。
12. 确认无法归属的企业可写进 description 的 `发现但无法归属：...`。
13. Agent 重新提交后同一 review_item 更新 version，不生成 review 链。
14. 旧 expected_version 返回 409，不静默覆盖。
15. `no_qualified_source` 计入已完成并显示“无合格来源”。
16. `industry-chain web` 在 `127.0.0.1:8765` 启动。

---

## 29. 核心结论

Full Review 核心对象只有：

```text
source
+ description（最终备注）
+ chain
+ 就地 uncertainties
+ 可选 locator / evidence description
```

人工最终只确认真正影响交付的：

```text
最终 Tree
最终 description
```

Core Service 再原子化编译为九字段 XLSX。