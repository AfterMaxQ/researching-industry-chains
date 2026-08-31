# 产业链研究 Skill 瘦身与证据门禁改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 在不削弱产业链证据、企业直接归属、来源边界、九字段写入、租约和终态规则的前提下，压缩运行时 Skill 的重复提示词，降低不必要的裁切/放大操作，并阻止流程图、系统架构图等非产业链图进入数据来源组。

**Architecture:** 保持单一 Python 包、CLI + JSON 协议和现有 Runner/Client 边界不变。改造只集中在研究 Agent 的运行时 SKILL.md：先用语义证据门禁筛选来源，再建立来源图表清单和两份内存覆盖清单，最后一次性写入；裁切和放大只作为局部不可读时的按需工具。Client 仍只执行确定性数据校验和 XLSX 投影，不负责判断产业链语义或企业真实性。

**Tech Stack:** Markdown Skill、Python 3.11+、industry-chain CLI、Runner JSON、XLSX、网页/PDF 浏览器和视觉能力；不新增数据库、Agent SDK、证据字段或截图持久化。

**Spec:** AGENTS.md、skills/researching-industry-chains/SKILL.md 以及当前九字段和 Runner/Client 业务约束。

## Global Constraints

- 保持单一 Python 包和 CLI + JSON 协议，不引入 SQLite、知识图谱、Agent SDK 或模型推理日志。
- 九字段固定为：主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注。
- 公司只能挂到来源直接证据支持的节点；不得依据常识、企业知名度、股票代码或父节点自动继承。
- 一个来源完整解析后一次性写入一个来源组；不同 URL 或不同底层文档不得混合，分页属于同一底层文档时合并。
- Client 不判断来源是否为产业链、节点是否正确或企业归属是否真实；这些判断留在 Skill 的研究流程中。
- Runner 目录只保留 runner.json 和交付 XLSX；图像、PDF、OCR、中间清单和日志不写入 Runner。
- 运行时用户可见文本、文档、注释、错误信息和测试名称使用中文；Python 包名、模块名、变量名和 CLI 命令保持英文兼容标识。
- 实施时保留现有 AGENTS.md、USAGE.md、README.md、Client 源码、Schema 和运行数据不变，除非后续明确授权扩大范围。

---

## 1. 现状、问题与改造决策

### 1.1 已确认的问题

- 当前 SKILL.md 的 SubAgent 模板要求复合页面的每个图块都“单独截图、裁切和放大”，流程部分又重复要求下载、缩放、分页截图、高清渲染和逐块放大。
- 同一份 Skill 对节点覆盖检查写得很明确，但没有同等强度的“企业证据组逐项盘点和映射”检查。
- 宽来源与窄主题的处理顺序不清晰，容易出现保留整棵节点树、却只保留命中主题关键词的企业。
- 产业链门禁同时使用“框、箭头、层级”等容易与流程图、系统架构图重叠的视觉特征，没有要求给出供应/生产/应用链语义。
- 多分页网页没有明确要求先确认总页数并扫描全部分页，容易只读取第一页主图。

### 1.2 改造决策

- 将“裁切/放大”从强制步骤改为条件动作；全图或整页优先，局部不可读时再处理局部区域。
- 将“产业链证据门禁”前置到深度视觉解析之前，并同时写出正证据和反证据。
- 在来源完整解析期间维护“节点清单”和“企业清单”两份内存清单，不新增持久化文件或数据字段。
- 先完成来源级扫描，再处理主题范围；接受宽来源时保留范围变化说明，不能静默删除同一来源中明确对应其它节点的企业。
- 每个硬规则只在 Skill 中出现一次；SubAgent 派发模板只保留任务参数、关键门禁和交付要求，不复制整套 CLI 说明。

## 2. 文件边界和职责

| 文件 | 实施动作 | 职责 |
| --- | --- | --- |
| skills/researching-industry-chains/SKILL.md | 唯一生产文件修改目标 | 合并重复规则，重写来源门禁、视觉读取、来源清单、企业覆盖和 SubAgent 模板 |
| docs/superpowers/plans/2026-08-31-slim-industry-chain-skill.md | 本计划文件 | 记录改造目标、边界、步骤和验收条件 |
| skills/researching-industry-chains/src/industry_chain_skills/dataset.py | 不修改 | 保持九字段和来源组确定性校验 |
| skills/researching-industry-chains/src/industry_chain_skills/excel.py | 不修改 | 保持来源顺序、九列和 URL 超链接投影 |
| skills/researching-industry-chains/schemas/record.schema.json | 不修改 | 保持九字段 Schema |
| README.md、USAGE.md、AGENTS.md | 不修改 | 保持当前公共契约和已有用户修改 |

## 3. 保持不变的业务理解合同

实施者必须先把下面的合同作为不可删除项，再开始压缩文案：

1. 来源必须同时有产业链结构和至少一组能直接归属到节点的企业证据。
2. 来源内部的图、表、分页和正文可以综合，但不同底层文档不得混合。
3. 节点按原图框、连接关系、分组、缩进和阅读方向还原；每条完整路径一行。
4. 企业按图片位置、分组标题、连接线或明确正文关系挂载；没有直接关系时留空，不得猜测。
5. 同一路径企业合并到同一 公司 单元格，按来源出现顺序用顿号连接并去重。
6. 只有来源组第一行填写备注；一次来源级写入必须通过 CLI 的九字段校验。
7. 主题领取、续租、写入、修改、删除、终态提交继续携带有效 claim_token。
8. 搜索连续两轮没有新增独立合格来源后，才能提交主题终态。

## 4. Task 1：冻结现有合同并建立删改对照表

**Files:**

- Read: AGENTS.md
- Read: skills/researching-industry-chains/SKILL.md
- Read: skills/researching-industry-chains/src/industry_chain_skills/dataset.py
- Read: skills/researching-industry-chains/src/industry_chain_skills/excel.py

**Interfaces:**

- Consumes: 当前 Skill、项目指令、九字段 Schema 和 Client 校验/投影实现。
- Produces: 运行时硬规则、可压缩规则、仅用于工具选择的说明三类对照结果。

- [ ] **Step 1: 复核当前文件范围**

运行：

~~~powershell
git status --short
git ls-files
~~~

预期：确认工作区已有的 AGENTS.md、USAGE.md 修改和未跟踪构建产物属于既有状态；本次实现不清理、不覆盖、不顺带格式化这些内容。

- [ ] **Step 2: 标出必须保留的业务规则**

重点核对当前 SKILL.md 中的主题快照、租约、来源门禁、来源边界、直接企业证据、九字段、原子写入、搜索饱和和终态命令。将重复表达合并时，只删除重复句，不改变规则含义。

- [ ] **Step 3: 标出需要删除或改写的动作性重复文案**

重点处理当前 SubAgent 模板和“扫描完整来源”部分中把每个图块都强制截图、裁切、放大的句子；保留“必须实际查看视觉证据”和“读不清不能猜测”，但把具体工具调用改为按需策略。

## 5. Task 2：重写来源证据门禁，阻止非产业链图误收

**Files:**

- Modify: skills/researching-industry-chains/SKILL.md 的来源资格和来源扫描部分

**Interfaces:**

- Consumes: 候选网页、报告、PDF 的标题、正文结构、图表类型和可视内容。
- Produces: 合格来源、不合格来源或证据不足三种内部判断；只有合格来源进入深度解析和 dataset insert。

- [ ] **Step 1: 写入正向门禁**

在 Skill 中只保留一段正向定义：来源必须明确表达供应商—制造商—应用方、上游—中游—下游、原材料—生产—应用或等价的产业链关系，并且至少一组企业可以直接对应某个节点。

- [ ] **Step 2: 写入反向门禁**

明确列出以下内容即使有框、箭头或分类，也不能单独通过门禁：技术路线、系统架构、工艺流程、业务流程、工作原理、产品结构、零部件清单、应用场景图、展商目录和没有节点关系的企业名单。标题含“产业链”但没有链条语义时同样不通过。

- [ ] **Step 3: 加入“先门禁、后高清”的顺序**

候选来源先用标题、正文小节、图题和整图快速判断；不具备产业链正证据时直接排除，不进入重复裁切和放大。只有门禁通过的图表才进入完整解析。

- [ ] **Step 4: 加入具体负例验收**

将 https://chinarobomap.com/exhibitors?lang=en 作为负例：页面自称官方展商数据库，按展商类别和产品展示，若没有其它明确的上游—中游—下游结构，不得仅凭 Supply Chain & Components 分类生成产业链来源组。

## 6. Task 3：压缩视觉读取和来源扫描流程

**Files:**

- Modify: skills/researching-industry-chains/SKILL.md 的完整来源扫描和视觉规则部分

**Interfaces:**

- Consumes: 已通过门禁的网页或 PDF 来源。
- Produces: 完整的来源图表清单，以及每个图表的类型和处理状态。

- [ ] **Step 1: 用一句话替换重复的截图操作要求**

写入以下语义，不再分别重复下载、分页截图、缩放、裁切和放大：

~~~text
先查看完整页面或完整图。只有节点、企业名或连接关系无法可靠读取时，才对对应区域按需裁切或放大；工具操作完成不代表来源解析完成，已经清晰的区域不重复处理。
~~~

- [ ] **Step 2: 明确分页扫描**

加入：网页有分页时先确认总页数并扫描全部分页；分页 URL 属于同一底层文档时合并为一个来源组，不得只解析第一页，也不得把分页误当成多个独立来源。

- [ ] **Step 3: 建立来源图表清单**

要求 Agent 在内存中记录：图表/页码、类型（主产业链图、企业图/表、正文结构、数据图、非链图）、是否提供节点、是否提供企业关系、是否已读取。该清单不写入 Runner。

- [ ] **Step 4: 保留视觉硬约束**

保留“用于节点或企业判断的图片/PDF 页面必须实际由视觉能力查看”“OCR、正文抓取、搜索摘要不能替代视觉检查”“看不清时不得猜测”三项硬规则，不因瘦身而删除。

## 7. Task 4：补齐企业清单、主题范围和节点归属规则

**Files:**

- Modify: skills/researching-industry-chains/SKILL.md 的节点与企业解析部分

**Interfaces:**

- Consumes: 来源图表清单、原图结构和正文/表格中的企业证据。
- Produces: 完整节点路径集合、直接企业归属集合和来源组 records。

- [ ] **Step 1: 增加企业证据清单**

要求 Agent 对每个图中企业框、企业列表、企业表格和明确正文企业关系逐组盘点，记录：来源页/图、企业组原文、直接对应节点、已挂载或无法归属。企业清单只存在于当前推理上下文，不新增 JSON 字段或证据文件。

- [ ] **Step 2: 增加对称覆盖门禁**

写入前必须同时满足：所有可读产业链节点都有路径行；所有可读企业证据组都已挂载到直接支持的节点，或已明确判断为无法归属。禁止只完成节点清单就提交。

- [ ] **Step 3: 固定来源级扫描优先于主题级过滤**

加入以下规则：

~~~text
先完整读取已接受来源中的产业链结构和企业证据，再判断主题范围。宽来源用备注说明范围变化；不能保留来源中的兄弟节点，却静默删除同一来源中明确对应这些节点的企业。若产品需要只交付某个叶子主题，必须由上游任务明确指定叶子子集，不得由 Agent 自行半截过滤。
~~~

- [ ] **Step 4: 防止企业过细挂载**

明确区分“来源明确属于某父节点”和“来源明确属于某子节点”。例如仅称“相关标的”或“算力设备租赁相关企业”时，不能自动挂到更细的云计算中心/AIDC 子节点；直接证据只到父层时只能挂父层。

- [ ] **Step 5: 保留原图结构规则**

保留节点原名、原层级、完整路径、同路径企业合并、父节点企业不向子节点继承和四级以上分类合并规则。瘦身只改变表达，不改变数据含义。

## 8. Task 5：重写精简版 SubAgent 派发模板

**Files:**

- Modify: skills/researching-industry-chains/SKILL.md 的 SubAgent 启动提示词模板

**Interfaces:**

- Consumes: runner_id、node_id 范围、主题快照、主题配置和领取令牌。
- Produces: 研究 Agent 能直接执行的任务提示词，以及主题终态汇报。

- [ ] **Step 1: 删除模板中重复的 CLI 和全流程解释**

模板只保留任务目标、输入范围、来源门禁、完整扫描、直接归属、双清单、原子写入和汇报要求；九字段具体 JSON、PowerShell UTF-8、全部 CLI 命令在 Skill 正文中各保留一份。

- [ ] **Step 2: 写入精简模板正文**

模板应表达以下完整语义：

~~~text
你是产业链来源研究 SubAgent，只处理指定 Runner 和 node_id 范围。先读取 skills/researching-industry-chains/SKILL.md，领取主题并保存有效 claim_token。

候选来源先过证据门禁：必须有明确的上游/中游/下游或供应商—制造商—应用关系，并且至少一组企业能直接对应节点。技术路线、系统/工艺/业务流程、工作原理、产品结构、零部件清单、应用场景图、展商目录和无节点关系的企业名单不能单独通过门禁。

门禁通过后扫描全文和全部分页，建立来源图表清单。先查看整图；只有局部不可读清楚时才裁切或放大。先完整还原来源树和企业清单，再处理主题范围；不能只保留命中关键词的企业而丢掉同一来源中明确对应其它节点的企业。

每个可读节点生成一条完整路径；每个企业组只挂到直接证据支持的终点，不能凭常识补充或从父节点继承。写入前核对所有可读节点都有行、所有企业组都已挂载或明确无法归属。任一项不通过，不得写入或提交终态。

每个来源完整解析后一次性通过 CLI 写入九字段 records。不同底层文档不得混合；所有写入、修改和终态操作携带有效 claim_token。搜索饱和后提交 completed、no_qualified_source 或 fail，并汇报 node_id、主题、终态、来源组数、行数和来源 URL。
~~~

- [ ] **Step 3: 检查模板与正文是否重复**

运行：

~~~powershell
rg -n "截图|裁切|放大|证据门禁|企业清单|来源图表清单|全部分页" skills/researching-industry-chains/SKILL.md
~~~

预期：关键规则在正文有唯一权威表述；模板只保留执行所需的短版，不再出现“每个图块都必须截图、裁切和放大”的强制句。

## 9. Task 6：保持 Client、写入协议和文档边界

**Files:**

- Read: skills/researching-industry-chains/src/industry_chain_skills/dataset.py
- Read: skills/researching-industry-chains/src/industry_chain_skills/excel.py
- Read: skills/researching-industry-chains/schemas/record.schema.json
- Do not modify: Section 2 中列出的所有文件，SKILL.md 除外

**Interfaces:**

- Consumes: 改造后的 Skill 文案和现有 Client 协议。
- Produces: 不变的九字段 records、来源组校验、稳定顺序和 URL 超链接。

- [ ] **Step 1: 静态确认九字段和写入约束仍存在**

检查 SKILL.md 仍明确包含九字段、来源组元数据一致、首行备注、至少一行企业、合法 HTTP(S) URL、一次性来源组写入、PowerShell UTF-8 和有效租约要求。

- [ ] **Step 2: 静态确认不把语义判断移进 Client**

检查本次 diff 不触及 dataset.py、excel.py、Schema 或 CLI。不要为了检测漏企业而新增证据字段、语义校验器、数据库或持久化覆盖清单。

- [ ] **Step 3: 确认公共文档不被顺带扩写**

README.md 和 USAGE.md 当前只描述 Skill 所需能力和稳定 CLI 使用方式；若没有与新规则矛盾的句子，不修改它们。AGENTS.md 的已有用户改动不参与本次编辑。

## 10. Task 7：固定来源验收和随机性验证

**Files:**

- Test input: https://www.askci.com/news/chanye/20260513/093025277863582328671722.shtml
- Test input: https://pdf.dfcfw.com/pdf/H3_AP202504111654883638_1.pdf
- Negative input: https://chinarobomap.com/exhibitors?lang=en
- Output: 使用新的 Runner 和交付 XLSX；不复用已有 Runner、旧 checkpoint 或旧结果

**Interfaces:**

- Consumes: 改造后的 SKILL.md、相同主题配置和上述固定来源。
- Produces: 可复核的来源组、行数、企业覆盖、负例门禁和 XLSX 投影结果。

- [ ] **Step 1: 运行三个独立新批次**

创建三个新的验证批次：skill-slim-validation-a、skill-slim-validation-b、skill-slim-validation-c。三次均使用相同主题配置和来源范围，不读取或复制已有运行结果。

- [ ] **Step 2: 验证中商来源的企业召回**

验收条件：

- 主图的 9 个上游零部件企业组和中游整机企业组都被盘点；不能只剩“丝杠”企业组。
- 页面 1–5 的企业图/表被检查，空心杯电机、传感器、减速器、控制器等明确企业证据不能静默丢失。
- 主图每个可读节点都有路径行；企业只挂到其直接支持的节点。

- [ ] **Step 3: 验证天风证券来源的召回和归属**

验收条件：

- 图 6 的 13 家企业全部保留。
- 正文明确提到的景嘉微、昆仑芯科技不能静默漏掉。
- 表 5 的相关标的不得在没有直接证据时自动挂到过细的云计算中心/AIDC 子节点。
- 设备服务器等图中无企业的节点仍保留，但不填猜测企业。

- [ ] **Step 4: 验证负例不误收**

验收条件：China Robot Map 展商数据库在没有明确产业链关系时不生成来源组、不调用 dataset insert。从现有测试来源中再选取至少一个实际流程图或系统架构图，验证同样结果。

- [ ] **Step 5: 验证提示词瘦身效果**

验收条件：

- SKILL.md 不再把裁切、放大或逐图截图写成无条件完成步骤。
- 三次运行都先完成来源门禁和来源清单，再进行必要的局部视觉处理。
- 企业证据组召回率和节点召回率不能因提示词缩短而下降；如果浏览器动作计数可获取，记录裁切/放大次数作为辅助指标，但不把动作次数当作业务成功标准。

- [ ] **Step 6: 验证交付协议不变**

对每次新批次检查：

- XLSX 只有九个业务列；
- 来源顺序与 Runner JSON 一致；
- URL 单元格生成超链接；
- 每个来源组共享主题、信源主体和 URL；
- 所有来源级写入仍是原子操作；
- 终态和来源组数量保持一致。

## 11. Task 8：最终审查、清理和交付

**Files:**

- Modify: skills/researching-industry-chains/SKILL.md
- Inspect: docs/superpowers/plans/2026-08-31-slim-industry-chain-skill.md

**Interfaces:**

- Consumes: 全部改动和固定来源验收结果。
- Produces: 只包含授权文件的最终 Skill 改动和验收报告。

- [ ] **Step 1: 检查改动范围**

运行：

~~~powershell
git diff --name-status
git diff -- skills/researching-industry-chains/SKILL.md
~~~

预期：生产改动只有 skills/researching-industry-chains/SKILL.md；计划文件作为本次明确请求的文档单独保留；没有 AGENTS.md、USAGE.md、Client、Schema、Runner 或临时证据文件的非授权改动。

- [ ] **Step 2: 做规则耐久性检查**

逐句确认新增文案描述的是长期业务规则和当前公共契约，而不是本次运行、某个模型、某次错误或临时交接说明。删除任何只解释编辑过程的句子。

- [ ] **Step 3: 只按批准范围提交**

如果进入提交阶段，只显式暂存计划文件和 SKILL.md，不暂存已有用户修改、__pycache__、.egg-info、运行数据、截图或下载物。

## 12. 完成判定

本计划只有在以下条件全部满足时才算完成：

- 运行时 Skill 的硬规则仍完整，重复动作性文案已合并；
- 来源门禁能区分产业链图与流程图/架构图；
- 中商来源的多图、多分页企业证据不再只保留目标关键词企业；
- 天风来源的图内企业、正文企业和表格企业分别按直接证据处理；
- 节点清单和企业清单都通过写入前覆盖核对；
- 新 Runner 验证不复用旧 checkpoint，固定正例和负例均通过；
- Client、九字段、JSON/XLSX、租约和终态契约没有变化；
- git diff --name-status 和完整 diff 通过最终范围审查。
