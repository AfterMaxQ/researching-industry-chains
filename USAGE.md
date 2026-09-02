# 使用指南

本指南说明如何准备主题配置、安装客户端、让研究 Agent 使用本 Skill，以及如何查看最终 XLSX。第一次使用时按顺序完成即可。

## 1. 准备运行环境

需要以下条件：

- Python 3.11 或更高版本；
- 可以访问互联网的搜索能力；
- 可以打开网页和 PDF、翻页、缩放和截图的浏览器能力；
- 可以实际理解截图内容的图像视觉能力；
- 一个包含正式主题、路径和批准别名的`topic_identity.yaml`。

搜索、浏览器和视觉能力由运行 Skill 的研究 Agent 提供。Client 不负责访问网页，也不会替 Agent 判断产业链节点和企业归属。

## 2. 安装 Client

在项目目录中执行：

```powershell
cd E:\researching-industry-chains
python -m pip install -e .\skills\researching-industry-chains
```

安装后检查命令是否可用：

```powershell
industry-chain --help
```

命令输出帮助信息即可。项目默认在当前目录的`runs`文件夹中保存任务批次。

## 3. 准备主题配置

主题配置文件名可以自定义，通常命名为`topic_identity.yaml`。文件使用 YAML，顶层必须是`themes`对象。`themes`下的键是正式主题，`path`用于理解主题在目录中的位置，`aliases`是经过批准、可用于搜索和主题匹配的别名。下面是可直接复制的模板：

```yaml
themes:
  正式主题示例:
    path:
      - 一级目录
      - 二级目录
    aliases:
      - 已批准别名一
      - 已批准别名二

  另一个正式主题:
    path:
      - 另一目录
    aliases: []
```

填写时遵守以下格式：

- `themes`必须存在，且每个主题键都是非空的正式主题名称；
- `path`必须是至少包含一个非空字符串的数组；
- `aliases`可以为空，但必须是字符串数组；
- `themes`中的排列顺序就是 Runner 的配置顺序；
- `path`只表示主题在目录中的位置，不会成为产业链节点，也不会写入九字段数据。

创建 Runner 后，Client 会保存这份目录的内部快照，包括正式主题、`path`、`aliases`、配置顺序和自动生成的`node_id`。以后修改外部 YAML，只影响新建 Runner，不改变已有 Runner 的主题名称、编号和状态。正式主题必须在配置中存在，不能由 Agent 临时新增或临时生成别名。

可以在创建任务前查询配置：

```powershell
industry-chain identity get --config E:\data\topic_identity.yaml --topic 半导体与精密装备
industry-chain identity search --config E:\data\topic_identity.yaml --query 半导体
```

## 4. 让 Agent 加载 Skill

按照所用 Agent 的 Skill 配置方式，把`.\researching-industry-chains\skills\researching-industry-chains`注册为 Skill 包。该目录同时包含`SKILL.md`、`pyproject.toml`、Client 源码和 Schema。Agent 应能够读取其中的`SKILL.md`，并调用安装后生成的`industry-chain`命令。

启动前确认 Agent 同时拥有搜索、浏览器、截图或 PDF 渲染、图像视觉理解和终端命令能力。只有文本抓取或 OCR、但不能实际看图的 Agent 不满足本 Skill 的执行条件。

可以直接给 Agent 以下三类任务之一。

### 新建批次

```text
使用 researching-industry-chains Skill 新建一个名为“产业链检索”的批次。
主题配置位于 ...\topic_identity.yaml。
依次处理全部待处理主题，按 Skill 规则搜索、读图、写入并提交主题状态。
```

### 继续已有批次

```text
使用 researching-industry-chains Skill 继续 Runner：<runner_id>。
只处理这个 Runner 中尚未尝试的 pending 主题。
```

### 指定补跑

```text
使用 researching-industry-chains Skill 补跑 Runner：<runner_id>中的节点：<node_id>/主题名:<主题名>。
如果该主题已经是终态，显式重开后继续处理。
```

### 用户发给父 Agent 的调度提示词

下面的提示词用于让父 Agent 创建 Runner、拆分任务和派发子 Agent。它不是子 Agent 的启动提示词；父 Agent 应使用 Skill 中的子 Agent 启动模板继续派发。

```text
请作为父 Agent使用 researching-industry-chains Skill 完成本次产业链检索任务。

先阅读并遵守：
- researching-industry-chains/SKILL.md
- 项目 AGENTS.md

任务配置：
- 主题配置文件：<topic_identity.yaml 路径>
- 任务名称：<任务名称>
- 处理范围：<全部主题 / 指定主题 / 指定 node_id>
- Runner 输出目录：<runs 目录；不填写时使用项目默认 runs>

请由你作为父 Agent 完成完整调度：

1. 创建一个新的 Runner，并保存 runner_id；
2. 读取 Runner 中的主题快照，确认正式主题、path、aliases 和 node_id；
3. 如果处理多个主题，先统计待处理主题数量，再决定子 Agent 数量，并尽量均分 node_id 范围；
4. 为每个子 Agent 分配明确且互不重叠的 node_id 或 node_id 范围；
5. 使用 Skill 中的启动提示词模板派发子 Agent，不额外预设来源、节点或企业结果；
6. 持续查看子 Agent 状态，必要时处理租约、失败和补跑；
7. 子 Agent 每完成一个主题后，立即汇总该主题的终态、来源组数量、写入行数、来源 URL 和 XLSX 路径；
8. 所有主题处理完成后，查看 Runner 总状态并汇报最终交付文件。

父 Agent 和子 Agent 都必须遵守以下边界：

- 产业链来源必须先通过产业链证据门禁；
- 必须先确认明确的产业链图、产业链表格，或结构化的上游/中游/下游节点；
- 系统架构、技术路线、零部件清单或企业名单不能单独拼成产业链；
- 必须使用浏览器和视觉能力实际查看图片、网页和 PDF；
- 图片或页面元素看不清时，裁切并放大核心区域后再判断；
- 企业只能挂到来源直接支持的节点；
- 不得把不同 URL 或不同报告混合；
- 不得创建中间 JSON、截图、PDF、脚本、日志或 evidence 文件；
- Runner 只保留 runner.json 和交付 XLSX；
- 每个来源完整解析后，通过 CLI 一次性写入全部 records；
- 子 Agent 完成主题后必须立即简要汇报；
- 不要在整个批次结束后才统一汇报。
```

或者，例如指定三个主题时，可以直接使用：

```text
请作为父 Agent使用 researching-industry-chains Skill，新建一个 Runner，并派发 3 个子 Agent，分别处理：

1. 灵巧手丝杠
2. 绿色能源金融
3. 原油

主题配置文件：
...\topic_identity.yaml(配置文件路径)

请先读取 SKILL.md 和 AGENTS.md，确认三个主题的正式名称、path、aliases 和 node_id。每个子 Agent 只负责一个主题，使用 Skill 中的通用启动提示词，不要在派发提示词中预设具体来源、节点或企业。

父 Agent 负责创建 Runner、派发子 Agent、监控租约和状态，并在每个主题完成后立即汇报结果。所有来源都必须先通过产业链证据门禁，确认有明确产业链图、产业链表格或结构化产业链节点后，才能生成记录和写入来源组。
```

## 5. 理解 Agent 的处理过程

研究 Agent 对每个主题执行以下闭环：

1. 领取主题，保存`node_id、claim_token、lease_expires_at`；
2. 使用正式主题、批准别名和产业链限定词搜索多个独立来源；
3. 在浏览器中检查完整网页或报告，包括后续产业链图、企业图、表格和正文；
4. 对所有用于节点或企业判断的图片页实际执行视觉检查；
5. 先按原图还原产业链树，再把每条根到节点路径转换成一条九字段记录；
6. 企业只写在来源直接支持的节点行，父节点企业不继承给子节点；
7. 完整解析一个来源后，通过 CLI 标准输入一次提交该来源的全部`records`，不创建中间 JSON 文件；
8. 继续搜索，直到连续两个完整搜索轮次都没有新增独立合格来源；
9. 有来源组时提交`completed`，没有合格来源时提交`no_qualified_source`，运行异常时提交`failed`。

长时间处理时，Agent 至少每20分钟续期一次。租约过期后，原令牌不能再修改该主题。

## 6. 手动创建和管理 Runner

研究 Agent 通常会自动执行这些命令。需要人工检查时，也可以直接运行。

创建 Runner：

```powershell
industry-chain runner create --name 产业链检索 --config ..\topic_identity.yaml
```

响应中的`data.runner_id`是后续所有操作必须使用的 Runner ID。

查看 Runner 状态：

```powershell
industry-chain runner status --runner-id <runner_id>
```

领取下一个待处理主题：

```powershell
industry-chain topic claim-next --runner-id <runner_id>
```

领取指定主题：

```powershell
industry-chain topic claim --runner-id <runner_id> --node-id <node_id>
```

重开终态主题：

```powershell
industry-chain topic claim --runner-id <runner_id> --node-id <node_id> --reopen
```

## 7. 来源组提交方式

一个网页、报告或 PDF 对应一个独立来源组。Agent 完整扫描该来源后，在内存中整理以下 `records` 数据结构，并通过 CLI 标准输入提交。不创建或保存来源 JSON 文件。

```json
{
  "records": [
    {
      "主题": "半导体与精密装备",
      "信源主体": "示例研究院",
      "分类1": "上游",
      "分类2": "核心零部件",
      "分类3": "传感器",
      "分类4": "",
      "公司": "甲公司、乙公司",
      "信源URL": "https://example.com/report",
      "备注": "发布日期未识别"
    }
  ]
}
```

通过标准输入提交来源组：

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$payload = @'
{"records":[
  {
    "主题":"正式主题",
    "信源主体":"发布主体",
    "分类1":"上游",
    "分类2":"节点",
    "分类3":"",
    "分类4":"",
    "公司":"企业名称",
    "信源URL":"https://example.com/report",
    "备注":""
  }
]}
'@
$payload | industry-chain dataset insert --runner-id <runner_id> --scope source_group --parent-id <node_id> --claim-token <claim_token> --input -
```

不创建或保存来源 JSON 文件；如果 CLI 校验失败，在内存中修正 `records` 后重新通过标准输入提交。

每一行表示“原图产业链树中从根节点到某个节点的完整路径”，公司字段只包含直接归属于该路径终点节点的企业。不是一家企业一行，也不能把多个独立叶子节点合并为一行。

只有来源组第一行可以填写备注。主题、信源主体和 URL 在来源组内必须保持一致。至少一行必须有明确企业，但没有企业的其他有效节点仍然需要保留。

## 8. 查看交付文件

每个 Runner 使用独立目录：

```text
runs/<runner_id>/runner.json
runs/<runner_id>/<runner_id>_交付数据.xlsx
```

`runner.json`保存主题快照、状态、稳定 ID、来源组和当前九字段记录，是修改和重新导出的依据。

XLSX 是交付文件，只包含：

```text
主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注
```

信源 URL 会自动生成可点击超链接。不同来源按成功写入顺序排列，同一来源内部按原图和原文的阅读顺序排列。

需要从当前 JSON 状态重新生成 XLSX 时执行：

```powershell
industry-chain runner export --runner-id <runner_id>
```

## 9. 常见状态和处理方式

| 状态 | 含义 | 后续处理 |
| --- | --- | --- |
| `pending` | 尚未开始 | 自动批次可通过`claim-next`领取 |
| `in_progress` | 已被研究 Agent 领取 | 使用当前有效令牌继续处理 |
| `completed` | 已写入至少一个来源组并完成搜索 | 可以审核，必要时显式重开 |
| `no_qualified_source` | 搜索饱和但没有合格来源 | 可以审核，必要时显式重开 |
| `failed` | 浏览器、网络、视觉或运行过程异常 | 在补跑任务中按`node_id`重新领取 |

CLI 成功时返回：

```json
{"ok": true, "data": {}}
```

业务校验失败时返回：

```json
{"ok": false, "error": {"code": "错误代码", "message": "中文错误说明"}}
```

遇到来源组校验错误时，应在内存中修正当前来源的 `records` 后重新通过标准输入提交，不能创建中间 JSON 文件，也不能拆成逐行写入来绕过来源级校验。

## 10. 审核和纠正数据

使用`dataset get`读取主题、来源组或单行的当前内容，再按修改范围选择操作：

- `patch`：只修改指定字段，保留 ID 和位置；
- `replace`：原子替换整行、整篇来源组或整个主题，保留目标 ID 和位置；
- `remove`：删除单行、来源组或主题，并保持其余数据相对顺序；
- `insert`：在末尾或指定`before_id、after_id`位置插入。

审核终态主题时不需要研究领取令牌，但不能把`completed`主题改成零来源组，也不能直接向`no_qualified_source`主题加入来源组。需要改变这种终态时，应先显式重开主题。
