# 产业链检索与交付客户端

本项目用于管理产业链资料检索批次，并把研究 Agent 生成的九字段来源组实时保存为 Runner JSON 和可交付 XLSX。Client 提供主题目录快照、并发领取租约、数据校验、稳定定位修改和超链接工作簿导出；搜索、浏览器操作、截图和视觉判断由外部 Agent 完成。

## 安装

要求 Python 3.11 或更高版本。

```text
python -m pip install -e ./skills/researching-industry-chains
```

`SKILL.md`、Client 源码、Schema 和安装配置位于同一个独立 Skill 包`skills/researching-industry-chains/`。外部 Agent 需要具备互联网搜索、可操作网页和 PDF 的浏览器、截图或高分辨率渲染、实际视觉读图以及调用本地 CLI 的能力。

## 命令

安装后使用`industry-chain`。命令组包括：

- `identity get|search`：读取外部主题身份配置；
- `runner create|list|status|export`：创建、查看和导出批次；
- `topic search|get|claim-next|claim|renew|finish|fail`：查询主题并管理状态和租约；
- `dataset get|insert|patch|replace|remove`：按主题、来源组或数据行操作交付数据。

所有 Runner 相关命令必须显式传入`--runner-id`。命令成功时输出`{"ok": true, "data": ...}`，业务错误时输出`{"ok": false, "error": ...}`。

## Runner 使用

新建批次：

```text
industry-chain runner create --name 产业链批次 --config E:\path\topic_identity.yaml
```

继续批次：

```text
industry-chain runner status --runner-id <runner_id>
industry-chain topic claim-next --runner-id <runner_id>
```

指定补跑失败主题：

```text
industry-chain topic claim --runner-id <runner_id> --node-id <node_id>
```

显式重开终态主题：

```text
industry-chain topic claim --runner-id <runner_id> --node-id <node_id> --reopen
```

Runner 文件位于：

```text
runs/<runner_id>/runner.json
runs/<runner_id>/<runner_id>_交付数据.xlsx
```

`runner.json`是当前状态和编辑依据。XLSX 是实时刷新的九列交付文件，信源 URL 单元格包含可点击超链接。

## 文档

- [使用指南](USAGE.md)
- [通用运行 Skill](skills/researching-industry-chains/SKILL.md)
- [项目指令](AGENTS.md)
