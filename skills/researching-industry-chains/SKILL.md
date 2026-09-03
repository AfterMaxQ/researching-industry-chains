---
name: researching-industry-chains
description: Use when 需要围绕正式产业主题检索、视觉读取并提交可审核的产业链来源，尤其涉及网页、报告、PDF、交互图和企业直接归属判断时；不用于普通行业总结、表格编辑、流程图或系统架构整理。
---

# 产业链来源研究与 SourceResult 提交

## 任务边界

研究 Agent 是研究员，只负责：

1. 找来源；
2. 浏览并理解来源；
3. 判断来源资格、产业链 Tree 和企业直接归属；
4. 输出完整 `SourceResult`。

不要生成九字段 records、内部 ID、审核状态、事件或 XLSX。Client 负责确定性校验、Tree → 九字段、编号、状态机、原子持久化和 XLSX 投影。

本任务不是总结行业知识，也不是建立“更合理”的标准产业链。只表达当前来源明确展示的业务事实。

## 必需输入与能力

运行前必须具备：

- Runner 中的正式主题、`path` 和 `aliases`；
- 互联网搜索能力；
- 网页、PDF 和交互内容浏览能力；
- 实际视觉读图能力；
- 可调用的当前仓库 `industry-chain` CLI。

项目内优先使用：

```text
python skills/researching-industry-chains/run_cli.py ...
```

PATH 中的已安装命令只作为人工快捷入口。其帮助若与当前源码不一致，以项目本地 launcher 为准。

新任务默认新建 Runner。除非用户明确要求继续某个 `runner_id`，否则不扫描或复用历史 Runner、JSON、XLSX、来源组和搜索结果。

单主题直接使用 `--topic`；批量主题使用 `--config`，不得为单主题临时生成 YAML：

```text
industry-chain runner create --name <任务名称> --topic <正式主题>
industry-chain runner create --name <任务名称> --config <topic_identity.yaml>
```

## Agent 工作协议

Agent-facing CLI 只有：

```text
industry-chain work claim-next --runner-id <runner_id> [--worker-label <名称>]
industry-chain source submit --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token> --input -
industry-chain work done --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token>
industry-chain work fail --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token> --code <错误代码> --message <简短说明>
```

保存领取响应中的 `work_type`、`work_id`、`claim_token`、租约时间和 topic context。

### topic work

```text
work claim-next
→ 搜索并逐个处理来源
→ source submit accept/review × N
→ 搜索饱和
→ work done
```

`work done` 只表示本轮自动搜索完成。Agent 不判断 topic 应为 `completed`、`awaiting_review` 或 `no_qualified_source`；Client 根据正式来源和开放审核推导。

### review work

领取结果包含同一 review_item 的当前 `source + description + chain + uncertainties`。只继续研究这个来源，随后提交一份完整的新 SourceResult：

```text
work claim-next
→ 继续读取当前来源
→ source submit accept/review
```

一次 `source submit` 即结束 review work，不再调用 `work done`。再次 `review` 会更新同一个 review_item，不创建 `review_01/review_02/review_03` 链。

### fail

`work fail` 只用于浏览器、网络、视觉能力或运行环境等真实执行异常。候选不合格、主题不一致、无企业证据或重复来源都不是执行失败。

## 来源准入

候选来源只有依次通过以下门槛，才进入深度解析。

### 1. 地域范围

除非正式主题明确要求地方范围，否则只接受研究对象为全国、中国整体或全国市场的来源。默认排除省市区县、园区、开发区、地方集群、招商图谱和地方重点企业分布。

判断的是来源研究对象，不是发布机构所在地。来源可以只覆盖正式主题产业链的一部分，但研究对象仍必须是正式主题本身。

### 2. 来源质量

优先政府和政府研究机构、全国性行业协会、证券公司研究所、权威科研机构、头部咨询和专业研究机构、正式白皮书及产业龙头研究材料。读取 `references/preferred-sources.md`，先做少量优质来源定向搜索，再开放搜索。

普通新闻、聚合、营销、自媒体、个人博客、软文和残缺转载默认跳过。发现转载时优先追溯原始报告；原始来源不可访问但转载完整保留证据时，才使用转载页。

发布日期不是准入门槛。2024 年及以后来源只具有搜索优先级；较早来源仍可使用，并在 `description` 说明“来源早于2024年”；日期无法确认时说明“发布日期未识别”。

### 3. 主题一致性

来源的产业链研究对象必须与 Runner 正式主题一致。只接受：

- 来源直接使用正式主题；
- 来源使用 Runner 已批准 `aliases`；
- 来源自身明确说明另一名称就是正式主题的直接同义表达。

不得用外部常识自行认定同义词。正式主题只作为上位产业链中的节点、产品、原料、应用或案例出现时，直接排除。

### 4. 产业链资格

来源必须同时满足：

1. 图、表或正文表达原材料/零部件 → 制造/服务 → 集成/运营 → 应用/需求等产业角色关系，能够回答“谁提供什么给谁”；
2. 至少一组企业能由来源内部证据直接归属于已有节点。

工艺流程、业务流程、工作流、技术路线、系统架构、功能模块、产品结构、零部件清单、应用场景集合、企业名单、相关标的表、排行榜、展商目录或无产业角色关系的生态图单独出现时不合格。

明确不合格的候选直接跳过，不向 Client 提交 `reject` 或 review。

## Source Probe 与视觉读取

先判断取得完整业务证据需要什么：正文、浏览器渲染、视觉读图、PDF、表格、折叠区、Tab、筛选、点击或多状态遍历。不要以固定 parser type 或域名特例驱动。

候选网页必须实际打开。DOM/正文用于定位标题、小节、图题和文字；浏览器渲染用于确认图片、表格、连接、分组和企业空间归属。出现产业链图题、图注或“资料来源”等视觉线索时，必须滚动到对应区域查看。

完整网页、全部分页和报告相关页都要扫描。同一底层文档的正文、分页、产业链图、补充节点图、企业图表和明确正文可以综合；其它 URL 或报告不得混入。

先看完整页面或整图。已经能可靠读取节点、层级、企业和直接关系时立即解析；只在具体局部不可读时裁切、放大或高分辨率渲染。OCR 和正文抓取不能替代视觉结构判断。

对交互来源主动遍历必要状态。只有主动探索后仍无法确认完整性，且人工有可能改变结果时，才提交 `review`，并用自然语言 Evidence 定位。

## Tree 合同

Tree 是 Agent 的核心输出。节点统一使用对象：

```json
{
  "name": "锡粉",
  "companies": ["华光新材", "康普锡威"],
  "children": []
}
```

`companies`、`children` 和 `uncertainties` 为空时可以省略。

还原规则：

- 先按来源中的框、标题、连接、缩进、包含关系和阅读方向还原 Tree；
- 每个可读节点都保留，包括父节点和无企业节点；
- 并列节点拆开，组合节点原样保留；省略号和装饰文字不生成节点；
- 节点名称、层级和数组顺序保持来源原义，不标准化、不润色、不补全；
- Tree 最多四层，不能把第五层及以后合并进第四层；
- 同一父节点下不能有同名节点；
- 数组顺序就是最终业务顺序：父节点先于后代，同级保持来源顺序。

企业永远只是当前节点的字符串数组，不保留企业组层级：

```json
"companies": ["华光新材", "康普锡威"]
```

企业只挂到同一来源直接证据支持的最小节点。证据只到父节点时只挂父节点，不向子节点继承；不凭行业知识、知名度、主营印象或股票代码推断。

企业清单中的每个可读企业都必须已挂载，或已明确判断为无法归属。无法归属的企业不要伪造节点归属；可在最终 `description` 中写 `发现但无法归属：A公司、B公司`。

## SourceResult 合同

### accept

只有来源资格、Tree、企业归属和完整性都可靠闭环时使用：

```json
{
  "outcome": "accept",
  "source": {
    "name": "示例研究院",
    "url": "https://example.com/report"
  },
  "description": "该来源展示锡膏上游材料和中游制造，并明确列出部分节点对应企业。",
  "chain": [
    {
      "name": "上游",
      "children": [
        {
          "name": "锡粉",
          "companies": ["甲公司", "乙公司"]
        }
      ]
    }
  ]
}
```

`accept` 的 chain 非空、至少包含一家企业，并且任何位置都不得出现 `uncertainties` 字段。

### review

来源具有业务价值、已主动探索，但结构、企业归属或完整性仍无法可靠闭环，且人工有可能改变结果时使用：

```json
{
  "outcome": "review",
  "source": {
    "name": "示例研究院",
    "url": "https://example.com/report"
  },
  "description": "主要结构可确认，但部分企业的直接归属仍不清楚。",
  "chain": [
    {
      "name": "锡粉",
      "companies": ["甲公司"],
      "uncertainties": [
        {
          "company": "甲公司",
          "message": "企业与锡粉节点之间的直接连接不清楚。",
          "evidence": [
            {
              "locator": "PDF 第17页图5",
              "description": "企业名称出现在节点附近，但连接线无法可靠辨认。"
            }
          ]
        }
      ]
    }
  ]
}
```

`review` 的 chain 可以为空，但整个 SourceResult 至少有一个 uncertainty。

uncertainty 就地挂载：

- 根级：整个来源的问题；
- 节点内且无 `company`：当前节点或父子结构问题；
- 节点内且有 `company`：当前节点下该企业 occurrence 的问题；`company` 必须存在于当前节点 `companies`。

每个 uncertainty 的 `message` 必填。`evidence` 可省略或包含多条；每条只包含：

```json
{
  "locator": "PDF 第17页图5",
  "description": "图中企业与节点的直接关系不清晰。"
}
```

Evidence 只是“去哪里看 + 为什么看这里”，不是截图资产、图片 URL、OCR、Evidence DB 或问答对象。

`description` 同时是来源说明和最终 XLSX 第一行备注。不要创建 `remark`、`summary`、`source_note` 或第二套未归属企业字段。

`source.name` 按发布关系填写：原始主体、`发布平台（原始主体）` 或 `发布平台（原始主体未明）`。找到可直接使用的原始发布页时使用原始页。

## 单来源事务与提交

一次只深度处理一个来源：

```text
完整扫描
→ 来源清单
→ 节点清单
→ 企业清单
→ 还原 Tree
→ 节点/企业覆盖检查
→ 形成完整 SourceResult
→ source submit
→ 再处理下一来源
```

用内存维护来源、节点和企业清单，不写入 Runner。不要创建中间 JSON；通过标准输入提交：

```powershell
$payload = @'
{"outcome":"accept","source":{"name":"示例研究院","url":"https://example.com/report"},"description":"来源完整展示产业链。","chain":[{"name":"上游","children":[{"name":"锡粉","companies":["甲公司"]}]}]}
'@
$payload | industry-chain source submit --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token> --input -
```

提交成功才结束当前来源事务。`accept` 会由 Client 编译为正式来源组并刷新 XLSX；`review` 只进入审核队列，不进入正式来源和 XLSX。

同一 topic 可连续提交多个来源。若 Client 返回 `SOURCE_GROUP_DUPLICATE_URL` 或 `SOURCE_GROUP_DUPLICATE_CONTENT`，不要改 URL、删节点、改企业或拆成多次提交来绕过；该候选不计为新增独立来源。

## 搜索结束

搜索饱和不按固定来源数或机械轮次判断。结束前确认：

1. 优质来源定向搜索已执行；
2. 正式主题和已批准 aliases 都覆盖了核心 `表达 + 产业链` 查询；
3. 视觉/引用发现和专业来源补漏已覆盖；
4. 高价值图题、报告名、原始机构和转载追源线索已处理；
5. 候选队列中没有尚未判断的潜在合格来源。

topic work 搜索结束后调用一次 `work done`。review work 在 `source submit` 后直接结束。

## 持久化边界

Runner JSON 是事实源，XLSX 只是正式来源的九字段投影。Agent 不直接编辑 XLSX，也不把 uncertainty、Evidence、截图、PDF、OCR、搜索过程、Prompt 或模型推理写入 Runner。

`dataset get|insert|patch|replace|remove` 是低层人工精确维护接口，不是研究 Agent 的来源提交协议。
