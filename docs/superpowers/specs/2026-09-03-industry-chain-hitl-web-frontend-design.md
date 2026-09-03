# 产业链 HITL 审核前端与本地 Web 架构设计 v1

## 1. 文档目的

本文定义 `researching-industry-chains` 的 HITL 本地 Web 审核界面。

配套核心设计：

- `docs/superpowers/specs/2026-09-03-industry-chain-human-review-design.md`

v1 是**单机 localhost 研究审核工作台**，不是多人 SaaS，也不是传统数据后台。

前端只解决：

> 人如何快速理解一个被 Agent 送审的来源、找到审核位置、查看当前产业链 Tree、必要时修正 Tree 和来源说明，并提交最终审核动作。

最终 XLSX 仍由 Core Service 根据最终 Tree 确定性生成，Web 不直接编辑 Excel 行。

---

## 2. 产品原则

1. Runner 是最外层工作空间。
2. Quick Review 只读；所有 Tree 编辑只发生在 Full Review。
3. 审核心智模型是 `来源 + description + Tree + uncertainties`，不是九字段 records。
4. `description` 是来源说明，也是最终 XLSX 第一行 `备注` 的内容，Full Review 可编辑。
5. uncertainty 不是 Agent 向人提问，而是“哪里不确定、为什么、去哪里看”。
6. Evidence v1 只显示 `locator + description`，不做截图资产、图片渲染、Lightbox、OCR 或 Evidence DB。
7. focus 不作为独立问答对象，只是由 uncertainty 的 Tree 位置动态派生的注意点。
8. 人工决策是来源级：采用当前结果、修正后通过、交回 AI 继续、驳回来源。
9. Web 不直接写 Runner JSON，不直接设置 status，所有业务动作调用同一套 Python Core Service。
10. 保持轻量：无用户系统、无数据库、无 WebSocket、无消息队列、无统计后台。

---

## 3. 信息架构

启动先进入 Runner Picker，不做跨 Runner 总 Inbox。

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

不出现：

- 用户头像；
- 个人中心；
- 通知中心；
- 知识库；
- 数据源管理；
- Agent 管理；
- 统计分析；
- 系统设置大菜单。

---

## 4. Runner Picker

每个 Runner 卡片显示最必要信息：

- Runner 名称 / 创建时间；
- 已完成 / 总主题；
- 待人工审核数量；
- AI 处理中数量；
- 最近更新时间。

其中“已完成”统计包括 topic 终态：

```text
completed
no_qualified_source
```

单个 `no_qualified_source` 仍展示“无合格来源”。

### 4.1 删除 Runner

删除是永久操作，无回收站。

规则：

- 有有效 topic claim 或 review claim 时拒绝删除；
- 不提供 force delete；
- 输入 `删除` 二次确认；
- 删除 Runner JSON、XLSX 和该 Runner 的相关本地运行文件；
- v1 已无 Evidence Asset 目录要求；
- XLSX 被占用时给出清楚错误，不做静默失败。

---

## 5. 工作台：极薄 Overview

工作台不是第二套 dashboard，只展示当前 Runner 的最小概况。

固定四个指标：

```text
待人工审核
AI处理中
已交回AI
今日完成
```

下面最多：

- 最近 3 个待审核来源；
- 少量最近业务 Activity。

不做：

- 趋势图；
- 环比；
- 企业总量；
- 模型成功率；
- 审核效率；
- Worker 排行。

---

## 6. 待审核：Quick Review

Quick Review **严格只读**。

三栏：

```text
审核队列 | 来源 / Tree 快速预览 | 审核处理
```

### 6.1 审核队列

每项展示：

- 主题；
- 来源主体；
- 来源标题 / URL 的可读部分；
- 当前状态；
- uncertainty 数量；
- 最近更新时间。

### 6.2 快速预览

显示：

- `description` 只读；
- 当前 Tree 只读；
- 当前 uncertainty 的简短 message；
- 相关审核依据入口。

Quick Review 不存在 working copy，不允许：

- 改节点；
- 拖拽；
- 改父级；
- 改企业；
- 改 description。

### 6.3 Quick Review 动作

只允许：

```text
查看审核依据
打开完整审核
采用当前结果
交回 AI 继续
驳回来源
```

其中：

- `采用当前结果` 仅在 chain 非空、当前结果未修改时可用；
- `chain=[]` 时只允许交回 AI 或驳回；
- 不做批量 approve。

---

## 7. Full Review 总体布局

Full Review 是唯一编辑面。

推荐三栏：

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
- `description` 编辑区，标签明确为：`来源说明（最终备注）`。

`description` 与 Tree 一起属于 Full Review working copy。

如果人工修改 Tree，可以同步修改 description；Client 不自动改写自然语言说明。

---

## 8. 审核依据：不做来源渲染系统

v1 左栏不承担图片 Viewer 或网页镜像职责。

它只回答两件事：

```text
去哪里看？
为什么要看这里？
```

每条 Evidence 卡片只显示：

```text
locator
description
```

例如：

```text
PDF 第17页 · 图5
图中能看到华光新材，但与锡粉节点的直接连接不清楚。
```

或：

```text
Supply Chain Explorer → Materials → 展开子节点
点击节点后页面内容变化，但页面没有明确的完整节点总数。
```

### 8.1 多 Evidence

一个 uncertainty 可以显示多条 Evidence：

```text
① PDF 第17页 · 图5
   产业链结构位置

② 正文第13段
   企业主营业务说明

③ PDF 第26页 · 表8
   企业再次出现但无直接节点映射
```

### 8.2 打开来源

页面提供 `打开原来源`。

locator 负责告诉审核员具体页码、章节、图表或交互路径。

v1 不要求浏览器自动跳到 PDF 指定框选区域，也不要求复制 Agent 当时的截图。

### 8.3 明确不做

- Evidence ID 展示；
- 图片缩略图；
- Lightbox；
- zoom / drag；
- OCR 编辑器；
- bounding box；
- 截图资产；
- Evidence Asset API；
- PDF 裁剪；
- 浏览器录像；
- 网页镜像。

Agent 可以用截图完成视觉研究，但截图不是前端必须持久化的数据。

---

## 9. uncertainty 与 focus

前端不显示：

```text
问题
候选答案
推荐答案
单选框
多选框
human_answer
```

uncertainty 是注意点，不是问卷。

### 9.1 来源级

根级 uncertainty：

```text
整个来源存在的不确定性
```

例如：

> 无法确认是否已经遍历全部必要交互状态。

### 9.2 节点级

node uncertainty 且无 company：

```text
当前 root-to-node path 对应的节点 / 结构问题
```

### 9.3 企业 occurrence

node uncertainty 带 company：

```text
当前 node path + company
```

因此同一家企业出现在多个节点时，前端仍能精确定位具体 occurrence。

### 9.4 focus 动态派生

`focus_items` 不要求作为 Runner 独立持久化对象。

前端 ViewModel 根据 uncertainty 所在位置动态生成 focus：

```text
source focus
node focus
company occurrence focus
```

点击某个 focus：

- Tree 自动定位到对应节点；
- 企业 focus 高亮当前节点下该企业；
- 左栏切到该 uncertainty 的 Evidence；
- 右栏显示对应 message。

不需要 `focus_item_id` 由 Agent 生成。

---

## 10. Tree 展示与编辑

Tree 直接来自 review_item 的 `chain`。

不再使用：

```text
draft_records → 前端投影 draft_tree
```

也不维护：

```text
draft_records + draft_tree
```

双模型。

### 10.1 节点编辑

Full Review 支持：

- rename；
- add root；
- add sibling；
- add child；
- delete；
- change parent；
- 同父节点拖拽排序；
- 跨父节点拖拽到新父级；
- 新增 Agent 遗漏节点。

### 10.2 整棵子树移动

例如：

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

B 的全部后代一起移动。

UI 必须拒绝：

- 拖到自己下面；
- 拖到自己的后代下面；
- 移动后正式分类深度超过 4。

父级选择器与拖拽使用完全相同的 reparent 语义。

### 10.3 顺序

当前 Tree 显示顺序就是最终 records 的稳定输出顺序。

不维护独立 node_order 编辑器。

### 10.4 删除

删除有子节点的节点时必须明确提示将影响整个子树，不能静默丢失后代。

---

## 11. 企业编辑

Tree 只关心：

> 当前节点直接有哪些企业。

企业 UI 对应：

```text
companies: string[]
```

支持：

- 添加企业；
- 删除企业；
- 修改企业名；
- 将企业移动到其他节点；
- 新增 Agent 遗漏企业。

不展示“企业组”层级。

最终同节点企业由 Client 用 `、` 合并进 XLSX `公司` 字段。

如果一个 uncertainty 指向企业 occurrence，UI 必须确认该企业确实存在于当前节点。

---

## 12. Full Review working copy

working copy 只有：

```text
chain
description
```

uncertainties / evidence 是审核上下文，不要求人工逐条编辑或“回答”。

### 12.1 保存策略

不按每个按键写 Runner。

页面本地可用：

```text
runner_id + review_item_id + review_version
```

保存临时 working copy，以防浏览器误刷新。

### 12.2 提交

人工点击通过时，一次性提交完整：

```text
final chain
final description
expected_version
```

Core Service 再执行：

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

右栏默认展示：

- 当前 review 状态；
- 当前 uncertainty message；
- 当前定位对象：来源 / 节点路径 / 企业 occurrence；
- 当前关联 Evidence 的 locator；
- 来源级审核动作。

如有必要，可折叠展示少量 Agent 已确认事实，但不展示 chain-of-thought。

点击 Tree 节点 / 企业时，右栏可临时切换成 Inspector；关闭 Inspector 后回到审核处理。

不增加第四列。

---

## 14. 审核动作

### 14.1 采用当前结果

working copy 与加载时相同且 chain 非空：

```text
采用当前结果
```

业务动作仍是 `approve`。

### 14.2 修正后通过

Tree 或 description 修改后：

```text
修正后通过
```

业务动作仍是同一个 `approve`，只是提交修改后的完整 working copy。

### 14.3 交回 AI 继续

```text
交回 AI 继续
```

只作用当前 review_item 当前 version。

前端不让用户配置域名白名单、parser 规则或 Skill 修改。

同一 version 只能 return 一次；Agent 返回新 SourceResult 后 review version 更新，用户才可基于新结果再次处理。

### 14.4 驳回来源

```text
驳回来源
```

不生成正式 source_group，不写 XLSX。

### 14.5 无 Tree review

`chain=[]` 时：

```text
采用当前结果   disabled
修正后通过     disabled
交回 AI 继续   enabled
驳回来源       enabled
```

v1 不允许从空白开始纯人工构建整个来源。

---

## 15. Quick Review 与 Full Review 的边界

这是硬边界：

```text
Quick Review
= 看 + 决策

Full Review
= 看 + 编辑 + 决策
```

任何以下动作必须进入 Full Review：

- 改节点名；
- 改顺序；
- 改父级；
- 新增 / 删除节点；
- 新增 / 删除企业；
- 企业换节点；
- 修改 description。

避免维护两套 Tree 编辑行为。

---

## 16. 任务进度

进度页只读。

顶部：

```text
已完成 / 总主题
```

“已完成”包含：

```text
completed
no_qualified_source
```

人类标签：

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

`no_qualified_source` 放入“已完成”列，但显示子标签“无合格来源”。

不允许拖拽改 topic 状态。

Worker 信息如 Codex / Claude / Trae 只是观察信息，不是控制面板。

---

## 17. 已完成

已完成页包含：

```text
completed
no_qualified_source
```

支持：

- 搜索主题；
- 查看最终来源；
- 查看最终 Tree / 来源说明；
- 查看简要审核处理记录；
- 打开最终来源 URL。

`no_qualified_source` 明确标记“无合格来源”。

不做性能排行榜或统计分析。

---

## 18. Activity Feed

只记录最小业务事实，例如：

```text
主题被 Agent 领取
来源已正式写入
来源进入人工审核
人工交回 AI
Agent 重新提交
来源已采用
来源被驳回
主题已完成
主题无合格来源
```

不展示：

- 模型完整推理；
- Prompt；
- token；
- 浏览器逐步操作录像；
- 内部调试日志瀑布流。

---

## 19. Web 架构

```text
Browser
React + TypeScript
        │
        ▼
HTTP API
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

CLI 和 Web 共享同一个 Python Core：

```text
Codex / Claude / Trae
        │
        ▼
CLI adapter
        │
        └────────────┐
                     ▼
               Python Core
                     ▲
        ┌────────────┘
        │
FastAPI adapter
        ▲
        │
      Web UI
```

Web 不：

- 直接读取并 patch 原始 Runner JSON；
- 暴露通用 `PATCH status`；
- 自己实现第二套状态机；
- 自己做 Tree → 九字段规则。

---

## 20. Review ViewModel

前端 Detail ViewModel 建议围绕真实审核心智组织：

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

focus 由 `chain + uncertainties` 动态派生。

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

`stage / reason` 如果 Core 仍提供，只作为可选展示 metadata，前端不得依赖它决定业务动作。

---

## 21. API 形态

建议使用业务动作 API，而不是通用状态 patch。

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

approve body：

```json
{
  "expected_version": 3,
  "description": "最终来源说明",
  "chain": []
}
```

Web 不需要 Evidence asset endpoint。

---

## 22. 并发与刷新

### 22.1 Review 版本

人工写动作必须带：

```text
expected_version
```

版本冲突：

```text
409 REVIEW_VERSION_CONFLICT
```

页面提示：

> 当前审核项已被 Agent 或其他操作更新，请重新加载最新版本。你本地的编辑不会被静默覆盖。

### 22.2 Polling

v1 可使用简单 polling：

```text
工作台          5s
任务进度        5s
审核队列        10s
```

当前正在编辑的 Full Review 不自动覆盖 working copy。

如果后台版本发生变化，只提示用户 reload / compare，不直接替换 Tree。

不引入 WebSocket。

---

## 23. 错误体验

### XLSX 被占用

显示：

> XLSX 当前被其他程序占用，正式写入未完成。请关闭占用文件后重试。

不得显示“成功”但实际未刷新交付文件。

### 非法 Tree 拖拽

操作不生效，并说明：

- 不能将节点移动到自己下面；
- 不能移动到自己的后代下面；
- 正式分类最多支持 4 层。

### 企业 uncertainty 无效

如果 uncertainty.company 不在当前节点 companies 中：

> 当前审核项结构已失效，请重新加载或由 Agent 重新提交。

### 来源无法打开

locator / description 仍保留，提示原来源当前不可访问；不伪造缓存截图。

---

## 24. 本地启动

建议：

```text
industry-chain web
```

默认：

```text
host = 127.0.0.1
port = 8765
```

启动后：

- FastAPI 单进程；
- 服务 Vite production build；
- 自动打开浏览器；
- Node 只用于前端开发 / 构建，不要求最终用户单独启动 Node 服务；
- 无登录。

---

## 25. Agent 协作边界

Web 可以提供一段可复制的“Agent 启动说明”，例如告诉用户如何让 Codex / Claude / Trae 开始领取 work。

但 Web 不直接启动 Agent 进程，也不提供 Agent 管理后台。

Agent-facing 工作协议仍是：

```text
work claim-next
source submit
work done（仅 topic work）
work fail
```

Web 只观察其结果。

---

## 26. 视觉风格

官方风格：**Warm Editorial Research Workbench**。

关键词：

```text
warm
restrained
research editorial room
clear
professional
low cognitive load
high information density without crowding
```

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

- 卡片圆角 10–12px；
- 1px 暖色 border；
- 很轻的 shadow；
- 细线图标；
- chip 少量使用；
- 不使用渐变、玻璃、霓虹、大面积彩色标签；
- 不做装饰性树叶 / 纹理；
- v1 不做 Dark Mode。

字体：

```text
Inter / system sans
PingFang SC
Microsoft YaHei
```

层级：

```text
页面标题 24 semibold
区块标题 17–18
卡片标题 14–15
正文 14
说明 12
```

---

## 27. v1 非目标

明确不做：

- 公网部署；
- 登录、多用户、角色权限；
- 多人实时协同；
- DB / Redis / MQ / WebSocket；
- 独立 Review DB / Evidence DB；
- Evidence Asset / 截图归档；
- 图片 Viewer / Lightbox；
- OCR / bounding box；
- 网页镜像；
- 浏览器录像；
- `draft_records` 编辑；
- XLSX 网页表格编辑器；
- 无限画布知识图谱；
- 问答式 review；
- Quick Review Tree 编辑；
- 从 `chain=[]` 纯人工从零构造完整产业链；
- 用户头像 / 个人中心 / 通知中心；
- 知识库 / 数据源管理 / Agent 管理；
- 统计分析后台；
- 暗色模式；
- 回收站；
- 站点专用 parser UI。

---

## 28. v1 验收用例

### A. Runner 选择与删除

能选择 Runner；“已完成 / 总主题”统计包含 `completed + no_qualified_source`；有有效 claim 时阻止删除。

### B. 极薄工作台

只显示四个核心指标、最近待审核和少量 Activity，无分析大盘。

### C. Quick Review 只读

可以快速看 description、Tree、uncertainty 和审核依据，但任何修改都必须进入 Full Review。

### D. 来源上下文

Full Review 顶部清楚显示 topic、source.name、source.url 和可编辑的“来源说明（最终备注）”。

### E. Evidence locator

一个 uncertainty 可以有多条 `locator + description`；页面不要求图片资产即可完成审核定位。

### F. 来源级 focus

根级 uncertainty 能在右栏显示，并关联对应 Evidence。

### G. 节点级 focus

节点 uncertainty 点击后 Tree 自动定位当前 path。

### H. 同名企业多节点

同一企业出现在多个节点时，company occurrence focus 根据 `node path + company` 精确定位，不串位。

### I. 采用当前结果

chain 非空、working copy 未修改时可直接采用。

### J. description 修改

人工修改来源说明后“修正后通过”，最终内容进入 XLSX 第一行备注。

### K. 节点新增与排序

支持新增节点、同级拖拽，最终稳定输出顺序与 Tree 一致。

### L. 子树 reparent

跨父级移动节点时整棵子树递归跟随；循环和超过 4 层被阻止。

### M. 企业编辑

可新增、删除、重命名和移动企业；最终同节点企业由 Client 用 `、` 合并。

### N. 无 Tree review

`chain=[]` 页面只允许交回 AI 或驳回。

### O. 交回 AI 再提交

Agent 返回新 SourceResult 后同一 review_item 更新版本，不生成新的 review 链；页面提示最新结果。

### P. 版本冲突

旧 expected_version 提交返回 409，不静默覆盖。

### Q. 进度页

人类状态标签正确；`no_qualified_source` 计入已完成并标记“无合格来源”。

### R. 本地启动

`industry-chain web` 在 `127.0.0.1:8765` 启动，单进程服务前端构建产物。

---

## 29. 核心结论

Full Review 的核心对象收敛为：

```text
来源
+ description（最终备注）
+ chain
+ 就地 uncertainties
+ locator / evidence description
```

前端不再承担 Evidence Asset 平台、九字段编辑器或问答系统职责。

人工最终只确认两件真正影响交付的数据：

```text
最终 Tree
最终 description
```

Core Service 再负责把它们原子化编译为正式九字段 XLSX。