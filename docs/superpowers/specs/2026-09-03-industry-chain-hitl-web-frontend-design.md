# 产业链 HITL 审核前端与本地 Web 架构设计 v1

## 1. 文档目的

本文定义 `researching-industry-chains` 项目的 Human-in-the-loop（HITL）审核前端与 localhost Web 接入方式。

本文是以下核心设计的配套文档：

- `docs/superpowers/specs/2026-09-03-industry-chain-human-review-design.md`

核心 HITL 设计回答“什么时候进入人工审核、Runner / review_item / work 如何流转”；本文回答：

> 人如何在本地 Web 中高效查看来源证据、理解 Agent 的不确定点、修正产业链草稿并完成最终审核，同时不绕开现有 CLI / Service / Runner 状态机。

v1 定位为**单机 localhost 研究审核工作台**，不是多人 SaaS，也不是传统数据管理后台。

---

## 2. 产品目标

前端需要做到：

1. 用户先选择一个 Runner，再进入该 Runner 的独立工作空间。
2. 工作台、待审核、任务进度和已完成均限定在当前 Runner。
3. 审核页必须清楚显示：**当前待审核来源属于哪个主题、来源是什么、真实证据是什么、Agent 草稿是什么、为什么被送审、哪些位置不可靠。**
4. 简单 review 可在 Queue 中快速查看和处理，复杂 review 再进入 Full Review Workbench。
5. Full Review 采用 **Evidence-first** 心智：左侧原始来源证据，中间产业链草稿，右侧审核处理。
6. 有产业链图时直接展示原图或必要的局部图，可点击放大；没有图时展示真正支持审核的正文 / 表格 / 交互证据。
7. **不使用正文摘要代替证据。** 人工审核需要来源原始证据，不需要 AI 再概括一遍文章。
8. 产业链树 + 企业归属是主要编辑模型，九字段 records 是底层业务协议，不是主要 UI。
9. 人工可修改、增加、删除节点和企业，也可修正企业挂载关系。
10. `focus_items` 只表示**需要人工注意的不确定点 / 定位点**，不表示 Agent 向人提出的问题，也不携带问卷式候选答案。
11. 人工决策发生在 review 级：采用当前结果、修正后通过、交回 AI 继续、驳回来源。
12. `draft_records=[]` 仍是合法 review，但 v1 不允许从空白开始纯人工构建完整来源。
13. `交回 AI 继续` 只作用当前 review_item / 当前 URL / 当前 reason，不建立域名规则。
14. Runner 页面能观察 Codex / Claude Code / Trae 等 Agent 主窗口当前 work，但 Web 不负责 Agent 调度。
15. Web 与 CLI 必须共用同一套 Python Service、RunnerStore、锁和状态机。
16. v1 保持轻量：无账号、无数据库、无 WebSocket、无消息队列。

最终体验目标：

> Agent 已经完成大部分研究与结构化工作；人打开审核页后，能直接对照真实证据和当前草稿，看到哪里不可靠，需要修改就直接修改，不需要修改就直接采用结果。

---

## 3. 非目标

v1 明确不做：

- 公网部署、登录、多用户、角色和权限；
- 多人协同编辑同一 review；
- 数据库、Redis、消息队列、WebSocket；
- 独立 Review DB 或 Evidence DB；
- 自动学习人工修改并直接修改 Skill；
- 站点级自动白名单；
- 完整审计平台和模型调用审计；
- 保存完整 chain-of-thought、Prompt、token、temperature；
- 全站截图归档、浏览器录像、网页镜像；
- 无限画布式知识图谱编辑器；
- 把 XLSX 整体搬到网页上；
- Dark Mode；
- 回收站；
- 从 `draft_records=[]` 开始纯人工构造完整产业链；
- 针对某个站点写专用前端或 parser 特例；
- 把审核做成 Agent 问问题、人选择答案的问卷系统。

---

## 4. 产品信息架构

启动先进入 Runner Picker，不使用跨 Runner 总 Inbox。

```text
Runner Picker
    ↓
Runner Workspace
    ├─ 工作台
    ├─ 待审核
    │   ├─ Quick Review
    │   └─ Full Review Workbench
    ├─ 任务进度
    └─ 已完成
```

Runner 是整个 Web 工作空间的边界。

推荐路由：

```text
/runners
/runners/{runner_id}
/runners/{runner_id}/reviews
/runners/{runner_id}/reviews/{review_id}
/runners/{runner_id}/progress
/runners/{runner_id}/completed
```

当前 Runner 上下文必须由 URL 表达，不能只存在隐藏的前端状态中。

---

## 5. 视觉语言：Warm Editorial Research Workbench

### 5.1 产品气质

正式视觉方向定为：

> **Warm Editorial Research Workbench**

关键词：

```text
暖色
克制
研究编辑室
清晰
专业
低认知负荷
高信息密度但不拥挤
```

它不是传统蓝色企业后台，也不是赛博数据大屏。

参考心智：

- Research SaaS 的干净信息结构；
- 编辑 / 审稿工具的暖色纸张感；
- IDE Inspector 的局部编辑效率；
- Diff / Review 工具“只强调真正需要处理的地方”的交互。

### 5.2 颜色体系

推荐设计 token 方向：

| 用途 | 建议色 |
| --- | --- |
| 页面背景 | `#FAF6F0` / 暖米白 |
| 主 Surface | `#FFFDFC` |
| 次级 Surface | `#F7EFE7` |
| Border | `#E9DCD1` |
| 一级文字 | `#2E2622` |
| 次级文字 | `#776C65` |
| Primary | `#C65F49` 陶土橙红 |
| Primary Hover | `#B8533F` |
| Review / Warning | `#D9913D` 琥珀 |
| Success | `#78906B` 灰绿 |
| Error | `#B85F55` 低饱和砖红 |

颜色用于**状态和关键操作**，不用于无意义装饰。

禁止：

- 大面积渐变；
- 玻璃拟态；
- 霓虹；
- 满屏彩色 Tag；
- 为了“暖”而加入叶子、纹理、插画等装饰元素。

暖色来自 Surface、Border、Primary 和整体色温，而不是装饰物。

### 5.3 元素语言

- Card 圆角约 `10–12px`；
- 1px 暖灰边框；
- 阴影非常轻，仅区分层级；
- 面板主要靠留白、间距和标题层级分区；
- 主按钮使用陶土橙红，危险操作不用抢主视觉；
- 图标采用简洁细线型图标；
- 企业适合显示为轻量 Chip，但不要把所有文本都做成胶囊；
- 当前 focus item 使用暖橙局部强调，切换后恢复普通视觉；
- 错误使用低饱和砖红，不用强烈纯红铺底。

### 5.4 字体与层级

优先使用系统字体，避免额外分发字体资源。

建议：

```text
Latin: Inter / system sans
macOS 中文: PingFang SC
Windows 中文: Microsoft YaHei / system sans
```

推荐层级：

```text
页面标题      24px / Semibold
区域标题      17–18px / Semibold
卡片标题      14–15px / Medium
正文          14px / Regular
辅助说明      12px / Regular
```

### 5.5 文案原则

UI 优先告诉人：

> 为什么这条来源被送审？哪里不可靠？我现在可以怎么处理？

而不是暴露内部枚举，也不是把不确定点改写成问卷问题。

例如：

```text
送审原因
企业归属缺少直接来源证据

当前草稿
华光新材 → 上游 / 金属材料 / 锡粉
```

而不是：

```text
华光新材应该属于哪个节点？
○ 锡粉
○ 锡膏制造
○ 无法归属
```

---

## 6. Runner Picker 与生命周期

Runner Picker 默认按最近活跃时间倒序。

“已闭环”只包括：

```text
completed
no_qualified_source
```

`pending / in_progress / awaiting_review / failed` 不计入闭环数量。

Runner 卡展示：

- Runner 名称；
- 已闭环 / 总主题；
- 整体进度；
- 待审核；
- AI 处理中；
- 等待处理；
- 最近活动；
- 进入入口；
- `...` 菜单。

### 6.1 Runner 切换

进入 Workspace 后，左上角始终提供 Runner selector。

浏览器可以保存 `last_runner_id` 作为本地便利设置，但该信息不属于 Runner 业务状态。

### 6.2 Runner 删除

Runner 支持永久删除，不做回收站。

删除前必须满足：

- 无有效 topic claim；
- 无有效 review work claim。

存在 active work 时禁止删除，v1 不提供强制删除。

二次确认明确：将删除整个 Runner、Runner JSON、交付 XLSX、review 数据和该 Runner 下的 review evidence assets，但不影响项目源码。

最终确认输入“删除”即可。

若 XLSX 被 Excel 等程序占用导致删除失败，前端必须明确提示，不得显示假成功。

---

## 7. Runner Workspace

左侧导航保持克制：

```text
锡膏专项研究 ▾

◉ 工作台
△ 待审核      6
◇ 任务进度
✓ 已完成

────────────
切换 Runner
```

### 7.1 工作台

回答：

> 当前 Runner 里，我现在需要关心什么？

只展示有工作价值的指标：

- 待人工审核；
- AI 处理中；
- 已交回 AI；
- 今日闭环。

待审核卡必须优先展示：主题、来源、送审原因、不确定点数量、是否已有草稿和下一步动作。

不做老板驾驶舱式无关指标。

---

## 8. 待审核 Queue / Quick Review

待审核页是高频 Inbox，目标是连续处理 review，而不是“列表 → 详情 → 返回”。

推荐三栏：

```text
审核队列 | 来源 / 草稿快速预览 | 审核处理
```

### 8.1 Queue

每条 review 展示：

- 主题；
- 来源主体；
- 人类可读送审原因；
- focus item 数量或“无草稿”；
- 等待时间。

不显示内部 review ID / status / enum。

默认排序保持简单：

1. 少量 focus_items 的简单 review 优先；
2. 无草稿、只需决定是否交回 AI 的 review 次之；
3. 复杂结构修改靠后；
4. 同级按创建时间。

### 8.2 Quick Preview

Quick Preview 只显示当前 focus item 必要的上下文：

- 相关的产业链局部树；
- 相关来源证据入口；
- 当前 focus item 的送审说明。

若审核必须阅读大图、多个证据、完整树或改变结构，应升级到 Full Review。

### 8.3 Quick Review

Quick Review **不生成问题和候选答案**。

例如企业归属存在不确定时，右侧应展示：

```text
审核处理

送审原因
企业归属缺少直接来源证据

当前关注点
华光新材

当前草稿位置
上游 / 金属材料 / 锡粉

关联证据
正文第 13 段
图 5 · PDF 第 17 页

[查看证据]   [打开完整审核]

[驳回来源]   [交回 AI 继续]
[采用当前结果]
```

如果审核员认为草稿正确，可以直接采用当前结果；如果需要改节点、关系或企业归属，进入 Full Review 或直接使用共享 Tree 编辑能力修正，再执行“修正后通过”。

`focus_item` 在 Quick Review 中只是定位和阅读顺序，不要求人工逐项回答或保存“答案”。

Quick Review 和 Full Review 必须共享同一份浏览器 working copy。

v1 不提供批量通过。

---

## 9. Full Review：Evidence-first Workbench

### 9.1 核心心智

Full Review 的三个核心对象固定为：

```text
来源证据 | 产业链草稿 | 审核处理
```

不是：

```text
AI 摘要 | AI 结果 | 人回答问题
```

审核过程必须形成：

```text
原始证据
    ↕
产业链草稿
    ↕
送审不确定点 / 人工操作
```

### 9.2 页面顶部：先回答“我在审什么”

顶部固定显示：

- 返回待审核；
- **主题名称，作为一级信息**；
- 来源标题 / 来源主体；
- URL 或 PDF / 页面位置；
- 人类可读状态；
- 打开原始来源。

示意：

```text
← 待审核

主题：锡膏
《2025 中国锡膏产业链研究报告》
华经产业研究院 · 2025 · example.com

                                         [打开原来源 ↗]
```

用户不能在审核过程中失去“当前来源属于哪个主题”的上下文。

### 9.3 三栏布局

推荐比例约：

```text
30% / 45% / 25%
```

当证据大图需要更多空间时允许临时扩大左栏；中栏产业链仍保持主要编辑区域。

```text
┌────────────────────────────────────────────────────────────────────────┐
│ ← 待审核   主题：锡膏   《某研究报告》                 打开来源 ↗     │
├────────────────────┬────────────────────────────┬──────────────────────┤
│ 来源证据            │ 产业链草稿                 │ 审核处理             │
│                    │                            │                     │
│ 图5 产业链图        │ 上游                       │ 送审原因             │
│ [原图缩略图]        │ ├─ 锡粉                    │ 企业归属缺少直接证据 │
│ 🔍 点击放大         │ │  └─ 华光新材 ⚠           │                     │
│                    │ └─ 助焊剂                  │ 当前关注点           │
│ 正文证据            │                            │ 华光新材             │
│ “华光新材……”       │ 中游                       │                     │
│ 第13段              │ └─ 锡膏制造               │ 当前草稿位置         │
│                    │                            │ 上游 / 锡粉          │
│                    │                            │                     │
│                    │                            │ [查看关联证据]       │
├────────────────────┴────────────────────────────┴──────────────────────┤
│ 2 个审核关注点        驳回来源   交回 AI 继续   采用当前结果 / 修正后通过 │
└────────────────────────────────────────────────────────────────────────┘
```

### 9.4 右栏：审核处理，而不是问答

右栏固定承担以下职责：

1. 显示当前 review 的送审原因；
2. 显示当前 focus item 的 target / message；
3. 显示当前草稿中对应节点 / 企业 / 结构位置；
4. 显示相关 evidence 引用和快速定位入口；
5. 可折叠显示 Agent 已确认内容；
6. 提供 review 级业务动作。

右栏禁止把 `focus_item` 自动翻译成：

- 问题；
- 单选题；
- 多选题；
- AI 推荐答案；
- 必填人工回答。

人工若要改变结果，直接编辑中间产业链草稿；右栏负责解释“为什么送审”和提供业务动作。

### 9.5 采用当前结果与修正后通过

两者最终都进入 `approve` 业务动作，但 UI 文案根据 working copy 是否变化区分：

- working copy 与 Agent draft 相同：显示 **采用当前结果**；
- working copy 已被人工修改：显示 **修正后通过**。

两者都必须提交完整 records，由 ReviewService 做最终确定性校验。

---

## 10. 来源证据区

### 10.1 原则

来源证据区展示**真正支持人工判断的原始证据**。

明确禁止使用“正文摘要”作为主要证据视图。

摘要回答“文章大概讲什么”，但 HITL 审核需要回答：

> 为什么这条产业链节点、企业归属或结构可以 / 不可以从当前来源得到？

因此证据必须尽量保留来源原始形态和定位。

### 10.2 产业链图片

如果来源存在产业链图，优先直接展示：

- 图像缩略图；
- 图标题 / label；
- 来源位置，如“PDF 第17页 · 图5”；
- 打开原来源入口。

图片必须可以点击进入 Lightbox。

Lightbox 最低支持：

- 放大 / 缩小；
- 滚轮缩放或等价操作；
- 拖动查看；
- 恢复 100% / fit；
- 关闭；
- 打开原来源。

不需要做图片编辑器、标注器或 OCR 编辑器。

### 10.3 多张图

同一来源存在多张与产业链有关的图时，以缩略图组展示，不强行拼成一张大图。

例如：

```text
[图3 上游] [图4 中游]
[图5 下游]
```

图与图的用途必须来自 Agent 对来源内部关系的判断；若用途本身无法确定，应进入 focus_item，而不是前端自行猜测。

### 10.4 正文证据

没有产业链图，或某个判断依赖正文时，直接展示**来源原文片段**：

```text
正文证据

“华光新材主要从事……其产品包括……”

正文第 13 段
[打开原文 ↗]
```

要求：

- 展示原文片段，不展示 AI 摘要；
- 有 locator 时显示段落、章节、页码等位置；
- 只展示与当前 review / focus item 有关的片段，避免把全文塞进面板。

### 10.5 PDF 证据

PDF 证据可表现为：

- PDF 某页中的产业链图；
- 某页表格；
- 某页原文片段。

UI 必须显示页码 / 图号等 locator，并提供打开原 PDF 的入口。

### 10.6 表格证据

来源中的产业链关系来自表格时，前端可以用只读表格保留原结构展示。

不要为了 UI 统一把表格强行改写成摘要文本。

### 10.7 交互式来源

对于 Chip Explorer 类来源，没有固定产业链原图时，不伪造图片。

证据区展示：

- 来源 URL；
- “交互式来源”标签；
- Agent 已验证的操作事实，例如“存在可点击产业链节点”“点击会改变业务内容”；
- 当前无法确认的点；
- `[打开 Explorer ↗]`。

交互式来源的业务完整性仍由核心 Source Probe / Capability Gate 决定，前端不引入站点类型特例。

---

## 11. Evidence 与 Focus Item 联动

这是 Full Review 的核心交互要求。

### 11.1 Focus Item 语义

`focus_item` 表示：

> Agent 认为当前来源中有一个位置无法可靠自动闭环，需要人工特别查看。

它是**注意力与定位对象**，不是问答对象。

推荐语义：

```json
{
  "type": "company_mapping",
  "target": "华光新材",
  "message": "当前企业归属缺少直接来源证据",
  "evidence_refs": ["ev_02"]
}
```

v1 不增加：

```text
question
options
recommended_answer
human_answer
```

### 11.2 三栏联动

每个 focus item 可以关联一个或多个 `evidence_id`。

当用户切换 focus item 时，页面同步：

1. 左侧定位到相关图片 / 原文 / 表格证据；
2. 中间 Tree 定位到对应企业、节点或结构区域；
3. 右侧展示该 focus item 的送审说明、当前草稿位置和相关业务动作。

如果证据是一段正文，可高亮目标企业 / 关键短语；如果证据是一张图，至少自动切换到对应图，不要求 v1 做像素级自动框选。

审核员可以使用上一项 / 下一项在 focus items 间导航，但不需要逐项提交答案。

---

## 12. 产业链草稿区

Tree View 是正式审核主界面。

展示规则：

- 分类节点按层级显示；
- 企业显示在最小直接支持节点下；
- 当前 focus item 使用暖橙强调；
- 人工新增 / 修改项显示极轻的“已改 / 人工新增”；
- 切换 focus item 时自动定位对应区域；
- 不使用“答对 / 已回答 / 已确认第 N 题”之类问答状态。

### 12.1 编辑能力

人工可：

- 重命名节点；
- 添加同级 / 子节点；
- 删除节点；
- 修改父子关系；
- 添加 / 删除企业；
- 将企业移动到其他节点；
- 将企业设为无法归属；
- 增加 Agent 完全遗漏的节点或企业。

节点移动可以支持拖拽，但必须同时提供确定性的父节点选择方式。

企业移动使用节点搜索器，不要求用户直接编辑 `分类1` ~ `分类4`。

### 12.2 Inspector

点击节点或企业时使用右侧 Inspector / 编辑区，不使用阻断式大 Modal。

右侧只有一个区域：

- 默认显示“审核处理”；
- 点击 Tree 节点 / 企业后切换到 Inspector；
- Inspector 关闭后回到当前 focus item 的审核处理。

不额外增加第四栏。

---

## 13. 无草稿状态

`draft_records=[]` 合法。

此时中间不显示空表和伪树。

例如：

```text
尚未生成产业链草稿

该来源需要交互式浏览。

✓ 已识别可点击产业链节点
✓ 点击后业务内容发生变化
? 无法确认是否完整遍历
```

左侧仍展示可用的真实来源证据 / 来源入口。

右侧“审核处理”展示送审原因、Agent 已确认事实和当前不确定点，但不向人工提出问题。

可执行动作仅为：

- `交回 AI 继续`；
- `驳回来源`。

“采用当前结果 / 修正后通过”必须 disabled，因为没有可提交的正式 records。

---

## 14. Review 决策栏

底部 Action Bar 始终可见，并且是 **review 级动作**。

普通未修改草稿：

```text
2 个审核关注点        驳回来源   交回 AI 继续   采用当前结果 →
```

人工已修改 working copy：

```text
2 个审核关注点        驳回来源   交回 AI 继续   修正后通过 →
```

无草稿：

```text
暂无可提交草稿                     驳回来源   交回 AI 继续 →
```

`focus_item` 不需要逐项“确认完成”才能显示 approve 动作。是否采用当前结果由人工对整个来源做最终判断。

### 14.1 采用当前结果 / 修正后通过

最终确认只展示：

- 节点数；
- 企业数；
- 是否存在人工修改；
- 人工修改摘要（如有）；
- 将写入正式 source_group；
- XLSX 将刷新；
- 当前 review 将闭环。

### 14.2 驳回来源

原因保持极简：

- 与主题无关；
- 不构成有效产业链；
- 来源质量不足；
- 内容无法可靠使用；
- 其他。

备注可选。

### 14.3 交回 AI 继续

确认面板必须明确：

- 只作用当前 review_item；
- 只作用当前 URL；
- 只 bypass 当前 reason；
- 相同 reason 不得原样再次送审；
- 新的不确定点可以再次进入审核；
- 不建立域名白名单；
- 不影响其他 URL；
- 不自动修改 Skill。

---

## 15. Tree / Records / Working Copy 边界

Runner 不新增 `draft_tree` 事实源。

```text
review_item.draft_records
        ↓
前端 records → tree
        ↓
浏览器 working copy
        ↓
Tree / Inspector 编辑
        ↓
前端 tree → records
        ↓
ReviewService approve
        ↓
正式 source_group
```

九字段 records 仍是业务协议；Tree 只是 UI 投影。

人工编辑不采用“每改一个节点就写 Runner”。一次审核最终一次性提交完整 records，由 ReviewService 做原子校验与写入。

Quick Review 和 Full Review 使用同一个 working copy。

可以使用浏览器本地存储恢复未提交草稿，key 至少包含：

```text
runner_id + review_item_id + review_version
```

本地 working copy 永远不是业务事实源。

---

## 16. 最小 Evidence 数据模型

为了满足“原图可看可放大、正文证据可直接阅读、focus item 可定位证据”，v1 允许为 review 保存**最小、review-scoped evidence 引用**。

这不是 Evidence DB，也不是全量网页归档。

推荐语义：

```json
{
  "evidence": [
    {
      "evidence_id": "ev_01",
      "kind": "image",
      "label": "图5：锡膏产业链",
      "locator": "PDF 第17页 · 图5",
      "source_url": "https://example.com/report.pdf",
      "asset_ref": "evidence/review_ab12cd/chain-01.png"
    },
    {
      "evidence_id": "ev_02",
      "kind": "text",
      "label": "企业归属正文证据",
      "locator": "正文第13段",
      "source_url": "https://example.com/article",
      "content": "华光新材……"
    }
  ]
}
```

`kind` 至少允许：

```text
image
text
table
interactive
```

它们是**前端证据表现形式**，不是 Source Probe 的 parser type。

`focus_items` 可以通过 `evidence_refs` 关联证据，但不保存问卷字段或人工答案。

### 16.1 Evidence Asset 存储边界

网页本身已有稳定图片 URL 时可以直接引用 URL。

如果是：

- PDF 内嵌产业链图；
- 浏览器渲染后才能看到的关键图；
- 为 review 截取的必要局部视觉证据；

允许保存到当前 Runner 目录，例如：

```text
runs/<runner_id>/
└─ evidence/
   └─ <review_item_id>/
      └─ chain-01.png
```

只保存**当前 review 真正需要人工查看的证据**。

明确不保存：

- 所有搜索结果截图；
- 整站页面快照；
- 浏览器录像；
- 所有 Agent 浏览过程；
- 独立 screenshot database。

Runner 永久删除时，其 evidence assets 一并删除。

---

## 17. 任务进度页

任务进度页回答：

> 当前 Runner 跑到哪了？

它是只读监控页，不是人工调度板。

展示：

- 已闭环 / 总主题；
- 已完成；
- AI 处理中；
- 待人工审核；
- 等待处理；
- 执行异常。

人类可读状态：

```text
pending             → 等待处理
in_progress         → AI 处理中
awaiting_review     → 待人工审核
completed           → 已完成
no_qualified_source → 无合格来源
failed              → 执行异常
```

可以使用只读列式流程：

```text
等待处理 | AI处理中 | 待人工 | 已完成
```

不允许拖卡改变状态。

Agent Work 展示 `worker_label` 仅作观察，不参与调度。

Activity Feed 只展示极简业务事实，不做完整审计日志。

对于重新送审，文案使用：

```text
发现新的不确定点
重新进入人工审核
```

不使用“Agent 又问了一个问题”。

---

## 18. 已完成页

保持简单历史视图，支持：

- 搜索；
- 查看来源；
- 查看 review 处理记录；
- 查看最终结果。

不做审核绩效排行榜和复杂分析。

---

## 19. Web 与 Python Core 架构边界

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
runner.json + XLSX + review evidence assets

Codex / Claude Code / Trae
        │ CLI
        ▼
CLI Adapter
        │
        └────→ 同一个 Python Application Core
```

核心原则：

> CLI 与 FastAPI 是同一套业务 Service 的两个 Adapter。

Web 不直接读取 / 修改 `runner.json`，React 更不能直接操作本地文件。

Agent 标准入口仍然是：

```text
industry-chain work claim-next
industry-chain work renew
industry-chain work finish
industry-chain work fail
```

Web 只提交 Human 业务动作和只读查询。

---

## 20. FastAPI 与 View Model

FastAPI 是薄 Adapter，不重写业务状态机。

推荐核心 API：

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

“采用当前结果”和“修正后通过”是同一个 `approve` 业务动作的不同 UI 文案，不增加两个状态机入口。

如 Evidence asset 需要由本地服务读取，应使用受 Runner / review 范围约束的只读资源接口，不允许任意本地文件路径访问。

前端不理解原始 Runner JSON 结构：

```text
Runner JSON = 持久化模型
HTTP JSON   = UI View Model
```

Review Detail View Model 至少能提供：

- topic；
- source；
- display_reason；
- focus_items；
- evidence；
- draft_records；
- events；
- version；
- 可执行 Human actions。

前端不得依赖 `question / options / answer` 之类问卷 View Model。

---

## 21. 并发与版本保护

CLI 与 FastAPI 最终都通过 RunnerStore 修改 Runner，继续使用 Runner 级文件锁和原子写入。

每个 review_item 增加轻量：

```text
version: integer
```

人工提交业务动作时带：

```text
expected_version
```

不一致时返回冲突，不能静默覆盖 Agent 新结果。

推荐 HTTP：`409 Conflict`。

列表和 Runner 进度可以后台刷新，但正在编辑的 review 不允许自动覆盖 working copy；发现服务器 version 变化时只提示“已有新版本”。

---

## 22. Polling 与本地运行

v1 不使用 WebSocket。

推荐：

```text
工作台       5 秒刷新
任务进度     5 秒刷新
审核队列     10 秒刷新
当前审核项   不自动覆盖
```

浏览器重新获得焦点时立即刷新列表 / 状态。

统一启动入口：

```text
industry-chain web
```

职责：

1. 解析 runs_root；
2. 检查已有本地服务；
3. 启动 FastAPI；
4. 挂载 React production build；
5. 绑定 `127.0.0.1`；
6. 自动打开浏览器；
7. Ctrl+C 停止。

默认：

```text
http://127.0.0.1:8765
```

允许：

```text
industry-chain web --runs-root <path>
```

v1 不绑定 `0.0.0.0`，不需要账号系统。

---

## 23. 前端技术栈

推荐：

```text
React
TypeScript
Vite
```

原因：

- Queue 有局部工作状态；
- Full Review 有 Evidence viewer、Tree editor、Inspector；
- Quick / Full Review 共用 working copy；
- 需要快捷键、Lightbox、局部刷新和版本冲突处理。

生产环境：

```text
Vite build
↓
FastAPI 挂载静态文件
```

不长期运行 Node production server。

---

## 24. 错误体验

### XLSX 被占用

```text
保存失败
交付 Excel 可能正在被其他程序占用。
关闭文件后重试。
```

### Review 版本冲突

```text
这条审核任务已经发生变化。
请查看最新结果后再继续。
```

不能自动覆盖用户 working copy。

### Evidence 缺失

如果 review metadata 指向的本地 evidence asset 丢失：

- 不阻止用户打开原来源；
- 明确显示“本地证据文件不可用”；
- 不伪造占位内容；
- 不因此把 review 自动判定通过或失败。

### Runner 删除冲突

存在 active work 时拒绝删除，并展示当前 work。

---

## 25. Agent 主窗口协作

Runner 页面可以提供“复制 Agent 启动指令”：

```text
阅读 skills/researching-industry-chains/SKILL.md，
继续处理 Runner <runner_id>。
从 CLI work claim-next 领取工作并持续执行，
不要自行选择任务。
```

只复制文本，不启动 Agent。

Agent claim 可以附：

```text
worker_label = Codex / Claude Code / Trae
```

仅用于 UI 展示，不影响 WorkService 调度。

---

## 26. v1 验收标准

### Case A：Runner 选择与删除

- 多 Runner 可搜索、进入和切换；
- Workspace 始终限定当前 Runner；
- 无 active work 时可永久删除 Runner；
- 有 active work 时删除被拒绝；
- JSON、XLSX 和当前 Runner evidence assets 一并删除。

### Case B：主题上下文

进入任何 review：

- 页面顶部明显显示所属主题；
- 明显显示来源标题 / 主体；
- 可打开原始来源；
- 审核员不需要从 URL 或 Runner 名猜主题。

### Case C：图片证据

来源有产业链图：

- 左侧直接展示图像缩略图；
- 显示图号 / 页码等 locator；
- 点击进入 Lightbox；
- 可以放大、缩小和拖动；
- 可以回到原来源。

### Case D：正文证据

来源审核依赖正文：

- 展示相关原文片段；
- 展示 locator；
- 不用“正文摘要”代替证据；
- 可打开原文。

### Case E：Evidence / Focus 联动

一个 review 有多个 focus item：

- 切换 focus item 时左侧自动定位相关 evidence；
- 中间 Tree 同时定位相关节点 / 企业；
- 右侧显示该 focus item 的送审说明和当前草稿位置；
- 不生成问题、候选答案或人工 answer 字段；
- 人可以通过上一项 / 下一项浏览所有关注点。

### Case F：采用当前结果

Agent draft 已存在，人工查看证据后认为无需修改：

- working copy 保持不变；
- UI 显示“采用当前结果”；
- 提交完整 records；
- ReviewService 校验通过后进入正式 source_group；
- XLSX 刷新。

### Case G：复杂 Tree 修正

- 可新增 / 删除 / 重命名节点；
- 可改变父子关系；
- 可新增 / 删除 / 重挂企业；
- working copy 变化后主动作显示“修正后通过”；
- 最终转换为九字段 records；
- ReviewService 校验后进入正式 source_group 并刷新 XLSX。

### Case H：无草稿交互来源

- `draft_records=[]` 正常展示；
- 展示来源入口和 Agent 已确认的交互事实；
- 不伪造产业链图；
- 不向人生成“是否继续”的问卷；
- “采用当前结果 / 修正后通过”不可使用；
- 可交回 AI 或驳回。

### Case I：再次送审

- 同一 URL 在人工放行后遇到新的不确定点，复用同一 review_item；
- 页面明确显示这是新的送审关注点；
- 旧 override 已消费；
- 当前 evidence / focus 只突出新的不确定点。

### Case J：版本冲突

- 人打开 version 3，Agent 更新为 version 4；
- version 3 提交不得覆盖 version 4；
- UI 提醒加载最新结果。

### Case K：本地启动

执行：

```text
industry-chain web
```

预期：

- 绑定 localhost；
- 使用指定 runs_root；
- 自动打开浏览器；
- React 与 API 同入口；
- 无需登录；
- 无需 Node production server。

---

## 27. 实现边界建议

Python Core：

```text
runner.py       Runner 生命周期与 topic 状态
review.py       ReviewService 与审核业务动作
work.py         WorkService 与 Agent 调度
storage.py      RunnerStore / 文件锁 / Runner scoped asset IO
api.py / web/   FastAPI 薄 Adapter
```

Frontend 至少拆分：

```text
app shell
runner picker
workspace dashboard
review queue
review workbench
source evidence viewer
image lightbox
shared tree editor
review handling panel / inspector
progress
completed
API client
working-copy state
```

不要把 Evidence、Tree、API、Working Copy 和 Review Actions 全部堆进一个 React 大文件。

---

## 28. 后续能力，不属于 v1

- 内网多人部署；
- 登录、身份、权限；
- 多人协同审核；
- Evidence DB；
- 更细的证据标注框 / 坐标系统；
- OCR 编辑与图片标注器；
- 全量网页快照；
- 人工修改统计与 Skill 优化分析；
- AI 对人工结果做 re-analysis / diff 建议；
- WebSocket；
- 数据库迁移；
- 回收站；
- Dark Mode；
- 纯人工从零构建来源。

---

## 29. 最终设计原则

1. **Runner 是工作空间边界。**
2. **审核页必须先让人知道当前来源属于哪个主题。**
3. **Evidence-first：原始证据不是 AI 摘要。**
4. **有产业链图就直接展示，并可放大查看。**
5. **没有图就展示真正支持审核的正文 / 表格 / 交互证据。**
6. **Evidence、Tree、Focus Item 三者必须联动。**
7. **Focus Item 是人工注意点 / 定位点，不是 Agent 向人的问题。**
8. **审核处理不使用问卷式问题、选项或人工 answer。**
9. **需要修改时直接编辑产业链 Tree；不需要修改时直接采用当前结果。**
10. **采用当前结果与修正后通过共用同一个 approve 业务动作。**
11. **产业链 Tree 是 UI；九字段 records 才是底层业务协议。**
12. **待审核数据不提前进入正式 source_groups / XLSX。**
13. **人工编辑使用 working copy，最终一次性提交。**
14. **review evidence 只保存当前人工审核真正需要的最小证据，不演变成 Evidence DB。**
15. **Agent 标准任务入口是 CLI；Human 标准审核入口是 Web。**
16. **CLI 与 Web 共用同一套 Python Service。**
17. **Web 不直接 PATCH 内部状态，也不直接修改 runner.json。**
18. **版本冲突必须显式失败，不能静默覆盖。**
19. **localhost v1 不为未来多人场景提前增加基础设施。**
20. **视觉语言统一采用暖色、克制、专业的 Warm Editorial Research Workbench。**
21. **最终目标是让人围绕真实证据修正或采用整个来源结果，而不是回答 Agent 出的题。**
