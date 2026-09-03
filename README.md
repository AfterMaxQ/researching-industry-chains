# 产业链检索、审核与交付客户端

本项目管理产业链研究批次，并把研究 Agent 提交的 `SourceResult(Tree)` 确定性转换为 Runner JSON 和九字段 XLSX。

职责边界：

- Agent：找来源、浏览和视觉读取、判断来源资格、还原产业链 Tree、表达企业直接归属和不确定性；
- Client：主题快照、统一工作租约、SourceResult/Tree 校验、Tree → 九字段、审核状态机、稳定 ID、原子持久化和 XLSX；
- Runner JSON：任务事实源；
- XLSX：已正式采用来源的交付投影。

待审核 SourceResult 不进入正式来源和 XLSX。人工通过后，Client 使用同一个 Tree compiler 和 DatasetService 原子写入最终数据。

## 安装

要求 Python 3.11 或更高版本：

```text
python -m pip install -e ./skills/researching-industry-chains
```

`industry-chain` 是安装后的快捷入口。仓库内的研究 Agent 优先使用当前 checkout，避免 PATH 中的旧安装干扰：

```text
python skills/researching-industry-chains/run_cli.py --help
```

## 创建 Runner

主题输入必须二选一。

单主题：

```text
industry-chain runner create --name 锡膏 --topic 锡膏
```

批量主题：

```text
industry-chain runner create --name 产业链批次 --config <topic_identity.yaml>
```

批量配置顶层是 `themes`；每个键是正式主题，`path` 是目录位置，`aliases` 是已经批准的别名：

```yaml
themes:
  正式主题示例:
    path:
      - 一级目录
      - 二级目录
    aliases:
      - 已批准别名
```

Runner 创建时保存主题快照，之后外部 YAML 的变化不影响已有 Runner。单主题 Runner 使用 `node_0001`，`path` 为 `[主题]`，`aliases` 为空。

## Agent 工作协议

Agent-facing 命令组是：

- `work claim-next`：统一领取交回 AI 的 review 或 pending topic；
- `source submit`：提交完整 SourceResult；
- `work done`：仅结束 topic 的自动搜索阶段；
- `work fail`：记录真实执行异常。

领取：

```text
industry-chain work claim-next --runner-id <runner_id> --worker-label Codex
```

可靠来源提交 `accept`：

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

仍需人工确认的来源提交 `review`，并在来源根级或 Tree 节点内就地放置 uncertainty；Evidence 只包含 `locator + description`。

通过标准输入提交：

```powershell
$payload | industry-chain source submit --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token> --input -
```

topic 搜索完成：

```text
industry-chain work done --runner-id <runner_id> --work-id <work_id> --claim-token <claim_token>
```

review work 在一次 `source submit` 后自动结束，不调用 `work done`。Agent 不提交 topic 终态；Client 根据正式来源和开放审核推导 `awaiting_review`、`completed` 或 `no_qualified_source`。

## 命令组

- `identity get|search`：读取外部主题身份配置；
- `runner create|list|status|export`：创建、查看和导出 Runner；
- `topic search|get`：查询 Runner 主题快照；
- `work claim-next|done|fail`：统一调度 Agent 工作；
- `source submit`：提交完整 SourceResult；
- `dataset get|insert|patch|replace|remove`：低层人工精确维护正式数据。

命令成功时输出 `{"ok": true, "data": ...}`；业务错误输出 `{"ok": false, "error": ...}`。

## 数据与文件

每个 Runner 使用独立目录：

```text
runs/<runner_id>/runner.json
runs/<runner_id>/<runner_id>_交付数据.xlsx
```

XLSX 固定包含：

```text
主题、信源主体、分类1、分类2、分类3、分类4、公司、信源URL、备注
```

Client 为 Tree 的每个节点生成一行，父节点先于后代；同节点企业按数组顺序用顿号合并；`description` 写入来源组第一行备注；URL 单元格生成可点击超链接。

`dataset` 命令保留给人工维护稳定 ID 对象，不是研究 Agent 的来源提交方式。审核数据中的 uncertainty、Evidence、version 和 events 不进入 XLSX。

## 文档

- [使用指南](USAGE.md)
- [研究 Agent Skill](skills/researching-industry-chains/SKILL.md)
- [项目指令](AGENTS.md)
