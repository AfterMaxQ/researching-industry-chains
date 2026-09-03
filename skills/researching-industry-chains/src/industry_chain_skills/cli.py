"""跨 Agent 使用的产业链 JSON 命令行接口。"""

import argparse
import json
import sys
from pathlib import Path

from .dataset import DatasetService
from .errors import ClientError
from .identity import get_identity, search_identities
from .runner import RunnerService
from .source_service import SourceService
from .storage import RunnerStore
from .work import WorkService


def _identity_dict(identity) -> dict:
    """把主题身份转换为 JSON 对象。"""
    return {
        "主题": identity.topic,
        "path": list(identity.path),
        "aliases": list(identity.aliases),
        "order": identity.order,
    }


def _add_runner_id(parser: argparse.ArgumentParser) -> None:
    """加入必填 Runner ID 参数。"""
    parser.add_argument("--runner-id", required=True)


def _add_dataset_target(parser: argparse.ArgumentParser, require_id: bool) -> None:
    """加入数据操作共用参数。"""
    _add_runner_id(parser)
    parser.add_argument("--scope", choices=("topic", "source_group", "row"), required=True)
    parser.add_argument("--id", required=require_id)
    parser.add_argument("--claim-token")


def build_parser() -> argparse.ArgumentParser:
    """构建完整命令树。"""
    parser = argparse.ArgumentParser(description="产业链检索与交付数据客户端")
    parser.add_argument("--runs-root", type=Path, default=Path.cwd() / "runs")
    commands = parser.add_subparsers(dest="command", required=True)

    identity = commands.add_parser("identity", help="查询外部主题身份配置")
    identity_commands = identity.add_subparsers(dest="action", required=True)
    identity_get = identity_commands.add_parser("get", help="精确查询正式主题")
    identity_get.add_argument("--config", type=Path, required=True)
    identity_get.add_argument("--topic", required=True)
    identity_search = identity_commands.add_parser("search", help="模糊查询主题")
    identity_search.add_argument("--config", type=Path, required=True)
    identity_search.add_argument("--query", required=True)

    runner = commands.add_parser("runner", help="管理 Runner")
    runner_commands = runner.add_subparsers(dest="action", required=True)
    runner_create = runner_commands.add_parser("create", help="创建 Runner")
    runner_create.add_argument("--name", required=True)
    topic_source = runner_create.add_mutually_exclusive_group(required=True)
    topic_source.add_argument("--config", type=Path)
    topic_source.add_argument("--topic")
    runner_commands.add_parser("list", help="列出 Runner")
    for action in ("status", "export"):
        child = runner_commands.add_parser(action, help=f"Runner {action}")
        _add_runner_id(child)

    topic = commands.add_parser("topic", help="管理 Runner 主题")
    topic_commands = topic.add_subparsers(dest="action", required=True)
    topic_search = topic_commands.add_parser("search", help="搜索快照主题")
    _add_runner_id(topic_search)
    topic_search.add_argument("--query", required=True)
    topic_get = topic_commands.add_parser("get", help="读取主题")
    _add_runner_id(topic_get)
    topic_get.add_argument("--node-id", required=True)

    work = commands.add_parser("work", help="领取或结束 Agent 工作")
    work_commands = work.add_subparsers(dest="action", required=True)
    work_claim = work_commands.add_parser("claim-next", help="领取下一份工作")
    _add_runner_id(work_claim)
    work_claim.add_argument("--worker-label")
    work_done = work_commands.add_parser("done", help="结束 topic 自动搜索阶段")
    _add_runner_id(work_done)
    work_done.add_argument("--work-id", required=True)
    work_done.add_argument("--claim-token", required=True)
    work_fail = work_commands.add_parser("fail", help="记录工作执行异常")
    _add_runner_id(work_fail)
    work_fail.add_argument("--work-id", required=True)
    work_fail.add_argument("--claim-token", required=True)
    work_fail.add_argument("--code", required=True)
    work_fail.add_argument("--message", required=True)

    source = commands.add_parser("source", help="提交完整 SourceResult")
    source_commands = source.add_subparsers(dest="action", required=True)
    source_submit = source_commands.add_parser("submit", help="提交来源研究结果")
    _add_runner_id(source_submit)
    source_submit.add_argument("--work-id", required=True)
    source_submit.add_argument("--claim-token", required=True)
    source_submit.add_argument("--input", required=True)

    dataset = commands.add_parser("dataset", help="管理交付数据")
    dataset_commands = dataset.add_subparsers(dest="action", required=True)
    dataset_get = dataset_commands.add_parser("get", help="读取数据对象")
    _add_dataset_target(dataset_get, require_id=True)
    dataset_insert = dataset_commands.add_parser("insert", help="插入数据对象")
    _add_dataset_target(dataset_insert, require_id=False)
    dataset_insert.add_argument("--parent-id")
    dataset_insert.add_argument("--before-id")
    dataset_insert.add_argument("--after-id")
    dataset_insert.add_argument("--input", required=True)
    for action in ("patch", "replace"):
        child = dataset_commands.add_parser(action, help=f"数据 {action}")
        _add_dataset_target(child, require_id=True)
        child.add_argument("--input", required=True)
    dataset_remove = dataset_commands.add_parser("remove", help="删除数据对象")
    _add_dataset_target(dataset_remove, require_id=True)
    return parser


def _read_input(value: str) -> dict:
    """从标准输入或 UTF-8 文件读取 JSON 对象。"""
    try:
        content = sys.stdin.read() if value == "-" else Path(value).read_text(encoding="utf-8")
        payload = json.loads(content)
    except OSError as exc:
        raise ClientError("INPUT_NOT_READABLE", "无法读取输入 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ClientError("INPUT_JSON_INVALID", "输入内容不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ClientError("INPUT_JSON_INVALID", "输入 JSON 顶层必须是对象")
    return payload


def _with_xlsx(data: dict, runs_root: Path, runner_id: str) -> dict:
    """在 Runner 响应中加入当前交付文件路径。"""
    return {
        **data,
        "xlsx_path": str((runs_root / runner_id / f"{runner_id}_交付数据.xlsx").resolve()),
    }


def dispatch(args: argparse.Namespace) -> object:
    """执行已解析命令并返回可序列化数据。"""
    store = RunnerStore(args.runs_root)
    runner = RunnerService(store)
    dataset = DatasetService(store)
    work = WorkService(store)
    source = SourceService(store)

    if args.command == "identity":
        if args.action == "get":
            return _identity_dict(get_identity(args.config, args.topic))
        return [_identity_dict(item) for item in search_identities(args.config, args.query)]

    if args.command == "runner":
        if args.action == "create":
            data = runner.create(args.name, args.config, args.topic)
            return _with_xlsx(data, args.runs_root, data["runner_id"])
        if args.action == "list":
            return store.list_summaries()
        if args.action == "status":
            return _with_xlsx(runner.status(args.runner_id), args.runs_root, args.runner_id)
        return {"runner_id": args.runner_id, "xlsx_path": str(store.export(args.runner_id).resolve())}

    if args.command == "topic":
        if args.action == "search":
            keyword = args.query.casefold()
            state = store.read(args.runner_id)
            return [
                topic
                for topic in state["topics"]
                if any(
                    keyword in value.casefold()
                    for value in (topic["主题"], *topic["aliases"], *topic["path"])
                )
            ]
        if args.action == "get":
            return dataset.get(args.runner_id, "topic", args.node_id)

    if args.command == "work":
        if args.action == "claim-next":
            return work.claim_next(args.runner_id, args.worker_label)
        if args.action == "done":
            return work.done(args.runner_id, args.work_id, args.claim_token)
        return work.fail(
            args.runner_id,
            args.work_id,
            args.claim_token,
            args.code,
            args.message,
        )

    if args.command == "source":
        return source.submit(
            args.runner_id,
            args.work_id,
            args.claim_token,
            _read_input(args.input),
        )

    if args.action == "get":
        return dataset.get(args.runner_id, args.scope, args.id)
    if args.action == "insert":
        if args.scope in ("source_group", "row") and not args.parent_id:
            raise ClientError("PARENT_ID_REQUIRED", "插入来源组或数据行必须指定 parent_id")
        return dataset.insert(
            args.runner_id,
            args.scope,
            _read_input(args.input),
            args.parent_id,
            args.before_id,
            args.after_id,
            args.claim_token,
        )
    if args.action == "patch":
        return dataset.patch(
            args.runner_id,
            args.scope,
            args.id,
            _read_input(args.input),
            args.claim_token,
        )
    if args.action == "replace":
        return dataset.replace(
            args.runner_id,
            args.scope,
            args.id,
            _read_input(args.input),
            args.claim_token,
        )
    return dataset.remove(
        args.runner_id, args.scope, args.id, args.claim_token
    )


def main(argv: list[str] | None = None) -> int:
    """运行 CLI，并只向标准输出写入统一 JSON 响应。"""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = dispatch(args)
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))
        return 0
    except ClientError as error:
        print(json.dumps({"ok": False, "error": error.as_dict()}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
