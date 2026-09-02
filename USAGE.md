# 使用指南

本指南说明如何安装 Client、创建单主题或批量 Runner、让研究 Agent 使用本 Skill，以及如何查看和修正最终 XLSX。

## 1. 准备运行环境

需要以下条件：

- Python 3.11 或更高版本；
- 可以访问互联网的搜索能力；
- 可以打开网页和 PDF、翻页、缩放和截图的浏览器能力；
- 可以实际理解截图内容的图像视觉能力；
- 已安装并可调用 `industry-chain` CLI。

搜索、浏览器和视觉能力由运行 Skill 的研究 Agent 提供。Client 不负责访问网页，也不会替 Agent 判断产业链节点和企业归属。

如果只处理一个主题，不需要准备主题配置文件。只有批量主题或需要显式维护 `path`、`aliases` 时才使用 `topic_identity.yaml`。

## 2. 安装 Client

在项目目录中执行：

```powershell
cd E:\researching-industry-chains
python -m pip install -e .\skills\researching-industry-chains
```

安装后检查命令：

```powershell
industry-chain --help
```

项目默认在当前目录的 `runs` 文件夹中保存 Runner。

## 3. 选择主题输入方式

创建 Runner 时，`--topic` 和 `--config` 必须二选一。

### 单个主题

直接传正式主题名称：

```powershell
industry-chain runner create --name 锡膏 --topic 锡膏
```

单主题 Runner 只包含一个主题：

```text
node_id: node_0001
主题: 锡膏
path: [锡膏]
aliases: []
```

Agent 不得为了单主题执行临时生成 YAML 配置文件。

### 批量主题

批量任务使用 YAML。文件顶层必须是 `themes` 对象：

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

格式要求：

- `themes` 必须存在；
- 主题键必须是非空正式主题名称；
- `path` 必须是非空字符串数组；
- `aliases` 必须是字符串数组，可以为空；
- `themes` 中的书写顺序就是 Runner 主题顺序；
- `path` 只用于理解主题位置，不作为产业链节点。

创建 Runner：

```powershell
industry-chain runner create --name 产业链检索 --config E:\data\topic_identity.yaml
```

批量配置也可以在创建前查询：

```powershell
industry-chain identity get --config E:\data\topic_identity.yaml --topic 半导体与精密装备
industry-chain identity search --config E:\data\topic_identity.yaml --query 半导体
```

Runner 创建后使用内部主题快照。批量模式下之后修改外部 YAML 不会改变已有 Runner。

## 4. 让 Agent 加载 Skill

按照所用 Agent 的 Skill 配置方式，把 `skills/researching-industry-chains` 注册为 Skill 包。Agent 应能读取其中的 `SKILL.md`，并调用安装后的 `industry-chain` 命令。

启动前确认 Agent 同时拥有搜索、浏览器、PDF 查看、截图或高分辨率渲染、图像视觉理解和终端命令能力。

### 单主题任务

可以直接告诉 Agent：

```text
使用 researching-industry-chains Skill 执行“锡膏”主题。
没有主题配置文件，直接创建单主题 Runner 并完成检索、解析、写入和终态提交。
```

Agent 应使用：

```text
industry-chain runner create --name 锡膏 --topic 锡膏
```

### 批量任务

```text
使用 researching-industry-chains Skill 新建一个名为“产业链检索”的 Runner。
主题配置位于 ...\topic_identity.yaml。
依次处理全部待处理主题。
```

### 继续已有 Runner

```text
使用 researching-industry-chains Skill 继续 Runner：<runner_id>。
只处理这个 Runner 中尚未尝试的 pending 主题。
```

### 指定补跑

```text
使用 researching-industry-chains Skill 补跑 Runner：<runner_id> 中的节点：<node_id>。
如果主题已经是终态，显式重开后继续处理。
```

### 父 Agent 调度

多主题任务中，父 Agent 创建 Runner 后读取主题快照，再按互不重叠的 `node_id` 范围派发子 Agent。父 Agent负责监控租约和状态；子 Agent 不预设来源、节点或企业结果。

不论单主题还是批量主题，研究过程都遵守同一套来源准入、单来源事务、节点/企业覆盖和 CLI 写入规则。

## 5. Agent 的单主题处理闭环

研究 Agent 对每个主题执行：

1. 领取主题并保存 `node_id、claim_token、lease_expires_at`；
2. 搜索候选来源，优先全国范围和专业来源；
3. 一次只深度处理一个来源；
4. 完整扫描当前网页、分页或报告相关页；
5. 图片已经清楚时直接解析，只对具体看不清的局部继续放大或渲染；
6. 建立当前来源的来源清单、节点清单和企业清单；
7. 按来源原结构还原节点，每个可读节点都保留；
8. 企业只挂到同一来源直接证据支持的最小节点，无法归属时记录到首行备注；
9. 生成固定九字段 records，并完成节点覆盖和企业覆盖；
10. 当前来源通过覆盖检查后立即一次性 `dataset insert`，成功后才处理下一来源；
11. 连续两个完整搜索轮次没有新增独立合格来源后提交主题终态。

长时间处理至少每 20 分钟续期一次。租约过期后，原令牌不能再修改该主题。

## 6. 手动创建和管理 Runner

单主题 Runner：

```powershell
industry-chain runner create --name 锡膏 --topic 锡膏
```

批量 Runner：

```powershell
industry-chain runner create --name 产业链检索 --config ..\topic_identity.yaml
```

两种输入不能同时提供，也不能同时省略。

查看 Runner：

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

一个网页、报告或 PDF 对应一个独立来源组。Agent 完整解析当前来源后，在内存中整理 `records` 并通过 CLI 标准输入一次提交，不创建来源 JSON 文件。

```json
{
  "records": [
    {
      "主题": "锡膏",
      "信源主体": "示例研究院",
      "分类1": "上游",
      "分类2": "核心材料",
      "分类3": "",
      "分类4": "",
      "公司": "甲公司、乙公司",
      "信源URL": "https://example.com/report",
      "备注": "产业链图位置：第 12 页，图 3《锡膏产业链》"
    }
  ]
}
```

只有来源组第一行可以填写备注。第一行备注必须包含产业链图位置；没有产业链图、而由表格或明确正文给出结构时，写明 `产业链图位置：无（结构来源：表格/正文，位置：具体页码或小节）`。

通过标准输入提交：

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
    "备注":"产业链图位置：正文“产业链结构”小节，第 2 张图"
  }
]}
'@
$payload | industry-chain dataset insert --runner-id <runner_id> --scope source_group --parent-id <node_id> --claim-token <claim_token> --input -
```

每一行表示从根节点到当前节点的完整路径，以及直接归属于路径终点的企业集合。不是一家企业一行，也不能把多个独立节点合并为一行。没有企业的有效节点仍然保留。

## 8. 查看交付文件

每个 Runner 使用独立目录：

```text
runs/<runner_id>/runner.json
runs/<runner_id>/<runner_id>_交付数据.xlsx
```

`runner.json` 保存主题快照、状态、稳定 ID、来源组和九字段记录，是修改和重新导出的事实源。

XLSX 只包含：

```text
主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注
```

信源 URL 会自动生成可点击超链接。需要重新导出时：

```powershell
industry-chain runner export --runner-id <runner_id>
```

## 9. 常见状态

| 状态 | 含义 | 后续处理 |
| --- | --- | --- |
| `pending` | 尚未开始 | 可通过 `claim-next` 领取 |
| `in_progress` | 已被研究 Agent 领取 | 使用当前有效令牌继续处理 |
| `completed` | 已写入至少一个来源组并完成搜索 | 可以审核，必要时显式重开 |
| `no_qualified_source` | 搜索饱和但没有合格来源 | 可以审核，必要时显式重开 |
| `failed` | 浏览器、网络、视觉或运行过程异常 | 按 `node_id` 重新领取 |

CLI 成功时返回：

```json
{"ok": true, "data": {}}
```

业务校验失败时返回：

```json
{"ok": false, "error": {"code": "错误代码", "message": "中文错误说明"}}
```

## 10. 审核和纠正数据

使用 `dataset get` 读取主题、来源组或单行，再按修改范围选择：

- `patch`：修改指定字段，保留 ID 和位置；
- `replace`：原子替换整行、整篇来源组或整个主题；
- `remove`：删除单行、来源组或主题；
- `insert`：在末尾或指定 `before_id、after_id` 位置插入。

审核终态主题时不需要研究领取令牌，但不能把 `completed` 主题改成零来源组，也不能直接向 `no_qualified_source` 主题加入来源组。需要改变这种终态时，先显式重开主题。
