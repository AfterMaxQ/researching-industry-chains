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

主题配置使用 YAML。`themes`下的键是正式主题，`path`用于理解主题在目录中的位置，`aliases`是允许用于搜索和主题匹配的别名。

```yaml
themes:
  半导体与精密装备:
    path: [先进制造, 半导体与精密装备]
    aliases: [半导体及设备, 先进半导体装备]
  服务器散热:
    path: [数字基础设施, 服务器散热]
    aliases: [数据中心散热]
```

创建 Runner 后，Client 会保存这份目录的内部快照。以后修改外部 YAML，只影响新建 Runner，不改变已有 Runner 的主题名称、编号和状态。

可以在创建任务前查询配置：

```powershell
industry-chain identity get --config E:\data\topic_identity.yaml --topic 半导体与精密装备
industry-chain identity search --config E:\data\topic_identity.yaml --query 半导体
```

## 4. 让研究 Agent 加载 Skill

按照所用 Agent 的 Skill 配置方式，把`E:\researching-industry-chains\skills\researching-industry-chains`注册为 Skill 包。该目录同时包含`SKILL.md`、`pyproject.toml`、Client 源码和 Schema。Agent 应能够读取其中的`SKILL.md`，并调用安装后生成的`industry-chain`命令。

启动前确认 Agent 同时拥有搜索、浏览器、截图或 PDF 渲染、图像视觉理解和终端命令能力。只有文本抓取或 OCR、但不能实际看图的 Agent 不满足本 Skill 的执行条件。

可以直接给 Agent 以下三类任务之一。

### 新建批次

```text
使用 researching-industry-chains Skill 新建一个名为“产业链检索”的批次。
主题配置位于 E:\data\topic_identity.yaml。
依次处理全部待处理主题，按 Skill 规则搜索、读图、写入并提交主题状态。
```

### 继续已有批次

```text
使用 researching-industry-chains Skill 继续 Runner：<runner_id>。
只处理这个 Runner 中尚未尝试的 pending 主题。
```

### 指定补跑

```text
使用 researching-industry-chains Skill 补跑 Runner：<runner_id>中的节点：<node_id>。
如果该主题已经是终态，显式重开后继续处理。
```

## 5. 理解 Agent 的处理过程

研究 Agent 对每个主题执行以下闭环：

1. 领取主题，保存`node_id、claim_token、lease_expires_at`；
2. 使用正式主题、批准别名和产业链限定词搜索多个独立来源；
3. 在浏览器中检查完整网页或报告，包括后续产业链图、企业图、表格和正文；
4. 对所有用于节点或企业判断的图片页实际执行视觉检查；
5. 先按原图还原产业链树，再把每条根到节点路径转换成一条九字段记录；
6. 企业只写在来源直接支持的节点行，父节点企业不继承给子节点；
7. 完整解析一个来源后，一次提交该来源的全部`records`；
8. 继续搜索，直到连续两个完整搜索轮次都没有新增独立合格来源；
9. 有来源组时提交`completed`，没有合格来源时提交`no_qualified_source`，运行异常时提交`failed`。

长时间处理时，Agent 至少每20分钟续期一次。租约过期后，原令牌不能再修改该主题。

## 6. 手动创建和管理 Runner

研究 Agent 通常会自动执行这些命令。需要人工检查时，也可以直接运行。

创建 Runner：

```powershell
industry-chain runner create --name 产业链检索 --config E:\data\topic_identity.yaml
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

## 7. 来源组 JSON 的含义

一个网页、报告或 PDF 对应一个独立来源组。Agent 完整扫描该来源后，生成以下格式：

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

遇到来源组校验错误时，应修正当前来源的完整 JSON 后重新提交，不能拆成逐行写入来绕过来源级校验。

## 10. 审核和纠正数据

使用`dataset get`读取主题、来源组或单行的当前内容，再按修改范围选择操作：

- `patch`：只修改指定字段，保留 ID 和位置；
- `replace`：原子替换整行、整篇来源组或整个主题，保留目标 ID 和位置；
- `remove`：删除单行、来源组或主题，并保持其余数据相对顺序；
- `insert`：在末尾或指定`before_id、after_id`位置插入。

审核终态主题时不需要研究领取令牌，但不能把`completed`主题改成零来源组，也不能直接向`no_qualified_source`主题加入来源组。需要改变这种终态时，应先显式重开主题。
