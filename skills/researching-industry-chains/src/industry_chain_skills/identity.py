"""主题身份目录的读取和查询。"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import ClientError


@dataclass(frozen=True)
class TopicIdentity:
    """主题目录中的一个稳定条目。"""

    topic: str
    path: tuple[str, ...]
    aliases: tuple[str, ...]
    order: int


def _invalid(message: str, **details: object) -> ClientError:
    """构造主题配置格式错误。"""
    return ClientError("TOPIC_CONFIG_INVALID", message, details or None)


def load_catalog(config_path: Path) -> list[TopicIdentity]:
    """读取主题身份配置，并保留配置中的主题顺序。"""
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClientError(
            "TOPIC_CONFIG_NOT_FOUND",
            "无法读取主题身份配置文件",
            {"path": str(config_path)},
        ) from exc

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise _invalid("主题身份配置不是有效的 YAML", path=str(config_path)) from exc

    if not isinstance(data, dict) or not isinstance(data.get("themes"), dict):
        raise _invalid("主题身份配置必须包含对象类型的 themes")

    catalog: list[TopicIdentity] = []
    for order, (topic, raw_entry) in enumerate(data["themes"].items(), start=1):
        if not isinstance(topic, str) or not topic.strip():
            raise _invalid("主题名称必须是非空字符串", order=order)
        if not isinstance(raw_entry, dict):
            raise _invalid("主题条目必须是对象", topic=topic)

        path = raw_entry.get("path")
        aliases = raw_entry.get("aliases", [])
        if (
            not isinstance(path, list)
            or not path
            or any(not isinstance(item, str) or not item.strip() for item in path)
        ):
            raise _invalid("主题 path 必须是非空字符串数组", topic=topic)
        if not isinstance(aliases, list) or any(
            not isinstance(item, str) or not item.strip() for item in aliases
        ):
            raise _invalid("主题 aliases 必须是字符串数组", topic=topic)

        catalog.append(
            TopicIdentity(
                topic=topic,
                path=tuple(path),
                aliases=tuple(aliases),
                order=order,
            )
        )
    return catalog


def get_identity(config_path: Path, topic: str) -> TopicIdentity:
    """按正式主题名称精确读取主题身份。"""
    for identity in load_catalog(config_path):
        if identity.topic == topic:
            return identity
    raise ClientError("TOPIC_NOT_FOUND", "正式主题不存在", {"topic": topic})


def search_identities(config_path: Path, query: str) -> list[TopicIdentity]:
    """按正式主题、别名或路径片段进行不区分大小写的模糊查询。"""
    keyword = query.casefold()
    matches: list[TopicIdentity] = []
    for identity in load_catalog(config_path):
        candidates = (identity.topic, *identity.aliases, *identity.path)
        if any(keyword in candidate.casefold() for candidate in candidates):
            matches.append(identity)
    return matches
