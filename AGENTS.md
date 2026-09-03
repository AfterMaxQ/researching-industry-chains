# 项目指令

## 项目定位与职责

本项目提供独立、跨 Agent 的产业链检索、Human-in-the-loop 审核与交付数据客户端。研究 Agent 负责搜索、浏览器操作、视觉读图、来源资格、主题一致性、产业链 Tree 和企业归属，并只提交 SourceResult；Client 负责主题快照、租约、SourceResult/Tree 确定性校验、Tree 到九字段编译、稳定 ID、审核状态机、原子修改、JSON 持久化和 XLSX 投影。

项目不绑定 Agent SDK。创建 Runner 时可以传入外部 `topic_identity.yaml` 批量创建主题快照，也可以直接传入一个正式主题创建单主题 Runner。批量模式保存配置中的正式主题、`path`、`aliases` 和顺序；单主题模式使用该主题本身作为 `path`，`aliases` 为空。Runner 创建后只使用内部主题快照，后续外部配置变化不影响已有批次。执行产业链检索时遵守 `skills/researching-industry-chains/SKILL.md`，本文件定义稳定业务边界。

新任务默认新建 Runner。除非用户明确要求继续、续跑或补跑某个已有 Runner，或明确提供 `runner_id`，研究 Agent 不得扫描 `runs/` 寻找同主题历史结果，也不得复用已有 JSON、XLSX、来源组或历史搜索结果。续跑时只使用用户指定的 Runner，不自行选择其它同主题 Runner。

研究 Agent 执行 Client 时，以**当前仓库源码**为 CLI 合同，默认使用 `python skills/researching-industry-chains/run_cli.py ...`。PATH 中已安装的 `industry-chain` 只是人工快捷入口，不作为能力判断依据；如果它的 `--help` 与当前源码或文档不一致，不得据此认定功能缺失，也不得退回临时 YAML 等替代流程。单主题任务仍必须使用当前源码支持的 `--topic`；只有项目本地 launcher 本身无法运行时，才按环境阻塞处理。

## 九字段与行语义

每条记录固定包含九个字符串字段：

```text
主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注
```

一行表示“从根节点到当前节点的完整路径”以及直接归属于路径终点的企业集合，不是一家企业一行，也不能把整棵产业链压成一行。Client 从 Tree 按父节点优先的深度优先顺序生成每个可读节点的行，包括父节点和无企业节点；同一父节点下的并列子节点不得合并。

先根据来源中的框、分组标题、连接关系、缩进、包含关系和阅读方向还原产业链 Tree，再由 Client 投影为行；不得先建立标准产业链再套入来源内容。Tree 最多四层，超过四层拒绝提交或人工修改，不把第五级及以后合并进分类4。分类必须连续。节点名称、层级和顺序保持来源原义，不标准化、不润色、不用行业知识补全；组合节点原样保留，并列节点拆行，省略号和装饰文字不生成节点。

企业只写入直接证据支持的最小节点 `companies: string[]`。证据只到父节点时只挂父节点，不向子节点继承；无法确认归属时不删除节点、不猜测挂载，可在最终 description 中说明。Client 按当前数组顺序用顿号合并同一节点企业；节点文字相同但完整父路径不同时分别保留。

公司字段保存企业实体名称；“旗下的、所属、由……控股、代表企业为”等关系文字只作为归属证据，不进入公司名称。只能识别原文简称或品牌时仍保留原文，不调用外部知识补全企业工商全称。

主题使用 Runner 快照中的正式名称。`source.name` 按发布关系填写，`source.url` 必须是产生本组节点和企业证据的同一来源地址。`description` 同时是来源说明和最终来源组第一行备注，不维护 `remark`、`summary` 或 `source_note`。

## 来源资格与证据

一个网页、报告或 PDF 形成一个来源组。同一底层文档的分页、产业链图、后续企业图表、企业列表和明确正文可以综合；其他 URL 或其他报告的内容不得补入。同一底层文档的转载或托管版本只保留一组。

来源产业链的研究对象必须与 Runner 正式主题一致。来源直接使用正式主题、使用已批准 `aliases`，或来源自身明确说明另一名称就是正式主题时可以保留；正式主题仅作为上位产业链中的节点、产品、原料、应用或案例出现时，不构成该主题的合格来源。不得用外部行业常识自行认定同义词。

合格来源还必须同时满足：

1. 图、表或正文表达产业角色之间的供给、生产或服务、集成或运营、应用或需求关系，能够回答“谁提供什么给谁”；
2. 至少一组企业能通过来源内部证据直接归属于已有节点。

工艺或业务流程、工作流、技术路线、系统架构、功能模块、产品结构、零部件清单、应用场景集合、企业名单、相关标的表和没有产业角色关系的生态图单独出现时不构成产业链。未通过资格门禁不得生成记录或写入来源组。

网页候选不能只依赖搜索摘要、DOM 或正文抽取判断视觉证据。DOM / 正文用于定位标题、小节、图题、表题和文字内容；Agent 自带浏览器用于确认页面实际渲染的图片、表格、连接、分组和企业空间归属。出现产业链图题、图注或“资料来源”等视觉线索时，必须实际滚动到对应区域查看；DOM 没有暴露图片节点不能作为“页面无图”的依据。

来源可以只覆盖正式主题产业链的一部分，但已展示范围必须完整解析。完整网页、全部分页和报告相关页都要扫描；所有可读节点均保留，不能因为没有企业而省略。用于判断节点或企业的图片必须由具备视觉能力的 Agent 实际查看；OCR、正文抓取、搜索摘要或下载成功不能替代视觉检查。先看完整图，只在局部内容无法可靠读取时裁切或放大。网页只有在实际查看相关页面区域并确认不存在产业链图后，才允许备注 `产业链图位置：无`。

产业链结构证据依次采用图片或表格、正文明确结构；普通介绍不能生成节点。企业证据依次采用图中明确位置、分组表或企业列表、正文明确介绍。证据冲突且无法消解时不强行挂载。不得用外部知识、企业知名度、主营业务印象或股票代码推断归属；只能确认品牌名或简称时保留原样。

信源主体填写为原始主体、`发布平台（原始主体）` 或 `发布平台（原始主体未明）`。找到可直接使用的原始发布页时优先原始页，不再提交转载页。发布日期不是来源准入门槛：2024 年及以后来源仅优先搜索和处理；较早来源只要其它条件合格仍正常保留，并在首行备注“来源早于2024年”。日期未识别时在首行备注。

开放搜索以**搜索意图覆盖**判断饱和，不以机械搜索轮次数判断。搜索表达集合中的每个表达都必须至少执行一次 `表达 + 产业链` 核心结构查询；其它结构扩展、视觉 / 引用发现和专业来源补漏仍按需执行，不做关键词笛卡尔积。搜索结果中明确的产业链图题、报告名和原始研究主体应完成有限追源。搜索用字面变体只帮助发现候选，不改变 Runner `aliases`，也不能放宽主题一致性门禁。

## Client 与 Runner 边界

Agent 通过 `source submit` 提交完整 SourceResult：

```json
{"outcome":"accept","source":{"name":"","url":"https://example.com"},"description":"","chain":[]}
```

`outcome` 只有 `accept` 和 `review`。`accept` 的 chain 非空、至少有一家企业，且任何位置都不能包含 uncertainty；`review` 可使用空 chain，但整个 SourceResult 至少有一个 uncertainty。uncertainty 就地挂在来源根级或节点内；企业 uncertainty 使用当前节点路径加 company 定位。Evidence 可省略或包含多条，每条只保存 `locator + description`，不建设截图资产、Evidence DB 或图片服务。

Agent-facing 命令只包括 `work claim-next`、`source submit`、topic work 结束时的 `work done` 和异常时的 `work fail`。Agent 不输出九字段、内部 ID、状态、version、events、stage 或 reason。`work done` 只表示自动搜索完成，Client 推导 topic 状态；review work 在一次 `source submit` 后结束。

`accept` 经 SourceResult/Tree 校验后由 Client 编译为九字段，再复用 DatasetService 校验并在同一事务中写入 Runner JSON 和 XLSX。`review` 只创建或更新 review_item，不进入正式 `source_groups` 和 XLSX。人工通过时提交最终 description、chain 和 expected_version，Client 再执行同一正式写入流程。人工交回 AI 后，Agent 的下一次 SourceResult 更新同一个 review_item，不创建 review 链。

低层 `dataset get|insert|patch|replace|remove` 保留为人工精确维护接口。其九字段载荷固定为：

```json
{"records":[{"主题":"","信源主体":"","分类1":"","分类2":"","分类3":"","分类4":"","公司":"","信源URL":"","备注":""}]}
```

Client 不判断主题相关性、产业链语义或企业真实性；只做 SourceResult/Tree、九字段、父主题一致性和重复来源等确定性校验。来源组内主题、信源主体和 URL 必须一致，分类不能断层，只有首行可写备注，至少一行公司非空，URL 必须可生成超链接。

Client 只在**同一 Runner、同一正式主题**内做确定性重复检查：

- 已存在完全相同的 `信源URL` 时拒绝；
- URL 不同，但能够识别出相同原始信源主体，且去掉 URL、备注、信源主体和行顺序后，“完整节点路径 + 该节点企业集合”完全相同时拒绝；
- 原始信源主体不同，即使业务内容完全相同也不自动判重；
- 仅节点结构相同、企业证据不同，不自动判重。

原始信源主体按 `原始主体`、`发布平台（原始主体）` 的规范格式确定；`发布平台（原始主体未明）` 不参与内容指纹判重。企业集合比较忽略顿号分隔后的书写顺序。该去重不使用行业语义、模糊相似度、embedding、模型判断，也不跨 Runner 查询历史数据。Client 不自动合并来源或企业。

每个来源完整解析后一次提交完整 SourceResult，不能边读边逐节点写入。低层 DatasetService 的三种作用域仍为 `topic、source_group、row`；内部 ID、时间、审核数据和顺序不进入九列 XLSX。Runner JSON 是事实源，XLSX 只投影正式来源；业务数据修改必须同时原子更新 JSON 和 XLSX。

主题状态为 `pending、in_progress、awaiting_review、completed、no_qualified_source、failed`。`work claim-next` 优先领取 `returned_to_agent` review，再恢复过期 review/topic，最后领取 pending topic。合法 `source submit` 续租；有效租约不能被其它 Agent 重复领取，过期后生成新令牌。

topic 自动搜索结束后：存在开放 review 时为 `awaiting_review`；无开放 review 且有正式来源时为 `completed`；无开放 review 且无正式来源时为 `no_qualified_source`。review 状态为 `pending_review、returned_to_agent、in_agent、approved、rejected`；人工动作使用整数 version 做乐观并发检查。每个 Runner 只保存 `runner.json` 和 `<runner_id>_交付数据.xlsx`，不同 Runner 完全隔离。

## 项目范围与验收

保持单一 Python 包和 CLI + JSON 协议。不得引入 SQLite 或其他数据库、知识图谱、来源评分平台、Agent SDK 依赖、模型推理日志、置信度字段、搜索过程或截图持久化，也不得把主题相关性等语义判断移入 Client。

Python 标识符、第三方库和 CLI 命令使用兼容的英文名称；文档、Skill、注释、docstring、错误信息、测试名称和用户可见内容使用中文。文档只描述当前项目和稳定规则，不记录会话过程、修改历史、旧版本比较或路线图。

验收以实际行为为准：外部主题配置或单主题输入都可创建主题快照；统一 work 调度不会产生两个有效持有者；accept SourceResult 能原子编译并写入正式来源与 XLSX；review 不会在批准前泄漏进 XLSX；同一个 review_item 可交回 Agent 并用完整 SourceResult 更新；人工 version 冲突不会静默覆盖；Tree/九字段/XLSX 任一步失败都不留下半个来源组；XLSX 只有九个业务列并将 URL 生成为超链接。
