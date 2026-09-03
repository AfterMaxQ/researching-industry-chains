# 使用指南

本指南说明如何创建 Runner、让研究 Agent 通过统一 work 协议提交 SourceResult，以及如何查看正式九字段交付。

## 1. 准备环境

需要：

- Python 3.11 或更高版本；
- 互联网搜索能力；
- 可打开网页、PDF 和交互内容的浏览器能力；
- 实际视觉读图能力；
- 当前仓库的 `industry-chain` Client。

安装：

```powershell
cd <repository-root>
python -m pip install -e .\skills\researching-industry-chains
```

仓库内执行研究任务时优先使用本地 launcher：

```powershell
python .\skills\researching-industry-chains\run_cli.py --help
```

以下示例用 `industry-chain` 简写同一套当前源码命令。

## 2. 创建 Runner

新任务默认创建新 Runner，不扫描或复用同主题历史结果。只有用户明确给出 `runner_id` 并要求续跑时，才继续该 Runner。

### 单主题

```powershell
industry-chain runner create --name 锡膏 --topic 锡膏
```

单主题 Runner 包含：

```text
node_id: node_0001
主题: 锡膏
path: [锡膏]
aliases: []
```

### 批量主题

配置文件：

```yaml
themes:
  正式主题示例:
    path:
      - 一级目录
      - 二级目录
    aliases:
      - 已批准别名

  另一个正式主题:
    path:
      - 另一目录
    aliases: []
```

创建：

```powershell
industry-chain runner create --name 产业链检索 --config <topic_identity.yaml>
```

`path` 只表示主题目录位置，不是产业链节点。Runner 创建后保存正式主题、path、aliases 和顺序快照，后续配置变化只影响新 Runner。

## 3. 领取工作

统一入口：

```powershell
industry-chain work claim-next --runner-id <runner_id> --worker-label Codex
```

响应包含：

```text
work_type: topic | review
work_id
claim_token
lease_expires_at
topic
review: null | 当前审核业务快照
```

领取优先级：

```text
已交回 Agent 的 review
→ 租约过期的 review
→ 租约过期的 topic
→ pending topic
```

保存当前 `work_id` 和 `claim_token`。有效 work 不能被第二个 Agent 重复领取；过期后重新领取会生成新令牌。

## 4. Agent 的职责

研究 Agent 只负责：

1. 搜索候选来源；
2. 实际打开网页、PDF 或交互内容；
3. 判断地域、专业性、主题一致性和产业链资格；
4. 完整扫描单个合格来源；
5. 按来源原义还原产业链 Tree 和企业直接归属；
6. 提交完整 SourceResult。

Agent 不生成：

```text
九字段 records
source_group_id
review_item_id
evidence_id
status / version / events
XLSX
```

详细来源门禁、视觉读取和搜索饱和规则见 [研究 Agent Skill](skills/researching-industry-chains/SKILL.md)。

## 5. SourceResult

### accept

只有来源资格、Tree、企业归属和完整性可靠闭环时使用：

```json
{
  "outcome": "accept",
  "source": {
    "name": "示例研究院",
    "url": "https://example.com/report"
  },
  "description": "该来源完整展示锡膏上游材料和中游制造，并明确列出部分节点对应企业。",
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

要求：

- `source.name` 和 HTTP(S) `source.url` 必填；
- `description` 必填，同时是最终 XLSX 来源组第一行备注；
- chain 非空，最多四层，至少包含一家企业；
- 任何位置都不能出现 `uncertainties` 字段。

### review

来源有业务价值且 Agent 已主动探索，但仍无法可靠闭环、人工可能改变结果时使用：

```json
{
  "outcome": "review",
  "source": {
    "name": "示例研究院",
    "url": "https://example.com/report"
  },
  "description": "主要产业链结构可确认，但企业与具体节点的直接归属仍不清楚。",
  "chain": [
    {
      "name": "上游",
      "children": [
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
  ]
}
```

review 的 chain 可以为空，但必须至少有一个 uncertainty。uncertainty 可位于：

- SourceResult 根级：整个来源的问题；
- Tree 节点内：当前节点或父子关系问题；
- Tree 节点内并带 `company`：当前节点下该企业 occurrence 的问题。

Evidence 可省略或包含多条。每条只有 `locator + description`，表示“去哪里看、为什么看这里”；不保存截图资产、图片 URL、OCR 或 Evidence ID。

## 6. Tree 规则

最小节点：

```json
{"name": "上游"}
```

带企业和子节点：

```json
{
  "name": "上游",
  "children": [
    {
      "name": "锡粉",
      "companies": ["华光新材", "康普锡威"]
    }
  ]
}
```

规则：

- 每个可读节点都保留，包括父节点和无企业节点；
- 企业只挂到来源直接证据支持的最小节点，不从父节点继承；
- `companies` 始终是字符串数组，不保存企业组；
- 节点最多四层，同父节点不能重名；
- 数组顺序就是最终业务顺序；移动父节点时整棵子树跟随；
- 空 `companies/children/uncertainties` 可以省略。

企业最终无法归属任何节点时，不伪造归属；可将 `发现但无法归属：A公司、B公司` 写进最终 description。

## 7. 提交来源

Agent 一次只深度处理一个来源，完成来源/节点/企业覆盖检查后提交完整快照。不要创建中间 JSON 文件；通过 stdin 提交：

```powershell
$payload = @'
{"outcome":"accept","source":{"name":"示例研究院","url":"https://example.com/report"},"description":"该来源完整展示产业链。","chain":[{"name":"上游","children":[{"name":"锡粉","companies":["甲公司"]}]}]}
'@
$payload | industry-chain source submit --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token> --input -
```

返回：

```json
{"result": "accepted", "source_group_id": "source_..."}
```

或：

```json
{"result": "queued_for_review", "review_item_id": "review_...", "version": 1}
```

`accepted` 会在同一事务中编译 Tree、复用九字段校验、更新 Runner JSON 和 XLSX。`queued_for_review` 只写审核队列，不进入正式来源或 XLSX。

同一个 topic work 可以连续提交多个来源。明确不合格的候选直接跳过，不提交 `reject` SourceResult。

重复来源错误：

- `SOURCE_GROUP_DUPLICATE_URL`：同一主题已有相同 URL；
- `SOURCE_GROUP_DUPLICATE_CONTENT`：相同原始主体的完整节点路径和企业集合已存在。

不要通过修改 URL、删除节点、改变企业或拆分提交来绕过去重。

## 8. 结束工作

### topic work

搜索饱和后调用一次：

```powershell
industry-chain work done --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token>
```

Client 推导 topic 状态：

```text
有开放 review                 → awaiting_review
无开放 review + 有正式来源    → completed
无开放 review + 无正式来源    → no_qualified_source
```

### review work

人工交回 AI 后，`work claim-next` 会返回同一个 review_item 的 source、description、chain 和 uncertainties。Agent 对该来源继续研究，再提交一份完整 `accept` 或 `review` SourceResult。

一次 `source submit` 即结束 review work，不调用 `work done`。再次 review 只更新同一个 review_item 并增加 version。

### 执行异常

```powershell
industry-chain work fail --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token> --code <错误代码> --message <简短说明>
```

只用于真实执行异常；候选不合格、重复来源或无合格来源不属于 fail。

## 9. 状态

Topic：

| 状态 | 含义 |
| --- | --- |
| `pending` | 等待 Agent 处理 |
| `in_progress` | topic 自动搜索进行中 |
| `awaiting_review` | 自动搜索结束，仍有开放审核 |
| `completed` | 有正式来源且审核已闭环 |
| `no_qualified_source` | 无正式来源且审核已闭环 |
| `failed` | 真实执行异常 |

ReviewItem：

| 状态 | 含义 |
| --- | --- |
| `pending_review` | 等待人工决定 |
| `returned_to_agent` | 已交回 AI，等待领取 |
| `in_agent` | Agent 正在继续研究 |
| `approved` | 已形成正式来源 |
| `rejected` | 来源已驳回 |

人工写动作使用 `expected_version`；过期版本返回 `REVIEW_VERSION_CONFLICT`，不静默覆盖。

## 10. 正式数据与低层维护

每个 Runner 目录只包含：

```text
runs/<runner_id>/runner.json
runs/<runner_id>/<runner_id>_交付数据.xlsx
```

XLSX 固定为：

```text
主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注
```

Client 为每个 Tree 节点生成一行；父节点先于子节点；同节点企业用顿号合并；只有来源组第一行写 description；URL 是可点击超链接。uncertainty、Evidence、review status、version 和 events 不进入 XLSX。

`dataset get|insert|patch|replace|remove` 是人工精确维护正式数据的低层接口，不是研究 Agent 的来源提交协议。任何正式数据修改都会重新执行九字段、父主题一致性和确定性重复检查。

需要重建 XLSX：

```powershell
industry-chain runner export --runner-id <runner_id>
```
