# 使用指南

本指南说明如何安装 Client、创建单主题或批量 Runner、让研究 Agent 使用本 Skill，以及如何查看和修正最终 XLSX。

## 1. 准备运行环境

需要以下条件：

- Python 3.11 或更高版本；
- 可以访问互联网的搜索能力；
- 可以打开网页和 PDF、翻页、缩放和截图的浏览器能力；
- 可以实际理解截图内容的图像视觉能力；
- 已安装并可调用 `industry-chain` CLI。

搜索、浏览器和视觉能力由运行 Skill 的研究 Agent 提供。Client 不负责访问网页，也不会替 Agent 判断主题相关性、产业链节点和企业归属。

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

按照所用 Agent 的 Skill 配置方式，把 `skills/researching-industry-chains` 注册为 Skill 包。Agent 应能读取其中的 `SKILL.md` 和 `references/preferred-sources.md`，并调用安装后的 `industry-chain` 命令。

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

多主题任务中，父 Agent 创建 Runner 后读取主题快照，再按互不重叠的 `node_id` 范围派发子 Agent。父 Agent 负责监控租约和状态；子 Agent 不预设来源、节点或企业结果。

不论单主题还是批量主题，研究过程都遵守同一套来源准入、单来源事务、节点/企业覆盖和 CLI 写入规则。

## 5. Agent 的单主题处理闭环

研究 Agent 对每个主题执行：

1. 领取主题并保存 `node_id、claim_token、lease_expires_at`；
2. 读取 `references/preferred-sources.md`，先做优质来源定向搜索；
3. 再进行开放网络搜索，补充种子库未覆盖的专业来源；
4. 对候选依次检查全国范围、专业性、原始来源、主题一致性和产业链资格；
5. 一次只深度处理一个来源；
6. 完整扫描当前网页、分页或报告相关页；
7. 图片已经清楚时直接解析，只对具体看不清的局部继续放大或渲染；
8. 建立当前来源的来源清单、节点清单和企业清单；
9. 按来源原结构还原节点，每个可读节点都保留；
10. 企业只挂到同一来源直接证据支持的最小节点，无法归属时记录到首行备注；
11. 生成固定九字段 records，并完成节点覆盖和企业覆盖；
12. 当前来源通过覆盖检查后立即一次性 `dataset insert`，成功后才处理下一来源；
13. 连续两个完整搜索轮次没有新增独立合格来源后提交主题终态。

主题一致性是硬门禁。例如正式主题是“锡膏”，《焊锡膏行业产业链》且来源自身明确“焊锡膏也叫锡膏”可以保留；《微电子焊接材料产业链》中“锡膏”只是与焊锡丝、焊锡条等并列节点时应直接排除。

长时间处理至少每 20 分钟续期一次。租约过期后，原令牌不能再修改该主题。

## 6. 优先来源定向搜索

默认优先站点维护在：

```text
skills/researching-industry-chains/references/preferred-sources.md
```

当前默认站点包括：

```text
中商情报网      askci.com
前瞻经济学网    qianzhan.com
华经情报网      huaon.com
观研天下        chinabaogao.com
智研网          chyxx.com
东方财富网      eastmoney.com
```

搜索工具支持站点限定时，可以直接使用：

```text
site:askci.com 锡膏 产业链
site:qianzhan.com 锡膏 产业链
site:huaon.com 锡膏 产业链
site:chinabaogao.com 锡膏 产业链
site:chyxx.com 锡膏 产业链
site:eastmoney.com 锡膏 产业链
```

也可以把“产业链”替换成“产业图谱、行业研究、研究报告”等少量直接相关表达。

优先站点只是“先去哪找”，不是白名单。站内页面仍然需要通过全国范围、主题一致性、产业链资格和企业证据规则。不要做大量网站 × 大量关键词的穷举搜索。

`preferred-sources.md` 由人工维护。Agent 可以建议增加新站点，但不能自动修改列表。

## 7. 转载来源的信源主体

信源主体按实际发布关系填写：

```text
原创页面：原始主体
转载且原始主体明确：当前发布平台（原始主体）
转载但原始主体无法确认：当前发布平台（原始主体未明）
```

例如：

```text
腾讯新闻（中商产业研究院）
新浪财经（某证券研究所）
腾讯新闻（原始主体未明）
```

发现转载时先尝试追溯原始报告或原发布页。能使用原始来源时直接使用原始来源，不再提交转载页；只有原始来源不可访问而转载完整保留产业链证据时，才使用转载页。

## 8. 手动创建和管理 Runner

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

## 9. 来源组提交方式

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

### 重复来源错误

同一 Runner、同一主题中，Client 可能返回：

- `SOURCE_GROUP_DUPLICATE_URL`：已经存在相同 `信源URL`；
- `SOURCE_GROUP_DUPLICATE_CONTENT`：URL 不同，但能够识别出相同原始信源主体，且完整节点路径和每个节点的企业集合与已有来源完全相同。

原创页的原始主体就是 `信源主体` 本身；转载页按 `当前发布平台（原始主体）` 中括号内的主体判断。`当前发布平台（原始主体未明）` 不参与内容重复判定。不同原始主体即使业务内容完全一致，也不会仅凭内容被 Client 自动判重。

重复不变量不只在 `source_group insert` 时检查。后续 `source_group patch/replace`、`row insert/patch/replace/remove` 和带来源组的主题创建/替换，也不能制造父主题不一致或同主题确定性重复。

出现重复错误时，不应通过修改 URL、删节点、改公司字段、改备注或逐行提交绕过。直接跳过重复候选，或在人工审核修改时保留两个来源之间真实存在的差异。

仅节点结构相同但企业证据不同不会自动判重。去重只在当前 Runner 的当前主题内执行，不查询历史 Runner，也不做模糊相似度或模型判断。

## 10. 查看交付文件

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

## 11. 常见状态

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

## 12. 审核和纠正数据

使用 `dataset get` 读取主题、来源组或单行，再按修改范围选择：

- `patch`：修改指定字段，保留 ID 和位置；
- `replace`：原子替换整行、整篇来源组或整个主题；
- `remove`：删除单行、来源组或主题；
- `insert`：在末尾或指定 `before_id、after_id` 位置插入。

所有会改变来源组最终内容的操作都会重新执行来源组结构、父主题一致性和同主题确定性去重检查。

审核终态主题时不需要研究领取令牌，但不能把 `completed` 主题改成零来源组，也不能直接向 `no_qualified_source` 主题加入来源组。需要改变这种终态时，先显式重开主题。