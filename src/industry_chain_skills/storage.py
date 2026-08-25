"""Runner 状态、文件锁和交付文件持久化。"""

import copy
import json
import os
import shutil
from pathlib import Path
from typing import Callable, TypeVar
from uuid import uuid4

from filelock import FileLock, Timeout

from .errors import ClientError
from .excel import write_workbook


T = TypeVar("T")


class RunnerStore:
    """在独立 Runner 目录中维护 JSON 状态和 XLSX 投影。"""

    def __init__(self, runs_root: Path, lock_timeout: float = 10.0) -> None:
        self.runs_root = runs_root
        self.lock_timeout = lock_timeout

    def _runner_dir(self, runner_id: str) -> Path:
        """返回 Runner 目录。"""
        return self.runs_root / runner_id

    def _json_path(self, runner_id: str) -> Path:
        """返回 Runner 状态文件。"""
        return self._runner_dir(runner_id) / "runner.json"

    def _workbook_path(self, runner_id: str) -> Path:
        """返回 Runner 交付工作簿。"""
        return self._runner_dir(runner_id) / f"{runner_id}_交付数据.xlsx"

    def _lock(self, runner_id: str) -> FileLock:
        """创建 Runner 级文件锁。"""
        lock_path = self.runs_root / ".locks" / f"{runner_id}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(lock_path, timeout=self.lock_timeout)

    @staticmethod
    def _validate_state(state: dict) -> None:
        """检查持久化所需的最小 Runner 结构。"""
        if (
            not isinstance(state, dict)
            or not isinstance(state.get("runner_id"), str)
            or not state["runner_id"]
            or not isinstance(state.get("topics"), list)
        ):
            raise ClientError("RUNNER_STATE_INVALID", "Runner 状态结构无效")

    @staticmethod
    def _write_json(state: dict, target: Path) -> None:
        """写入 UTF-8 JSON 状态文件。"""
        target.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _read_json(path: Path) -> dict:
        """读取并解析 Runner 状态文件。"""
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ClientError("RUNNER_NOT_FOUND", "Runner 不存在") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ClientError("RUNNER_STATE_INVALID", "Runner 状态无法读取") from exc
        RunnerStore._validate_state(state)
        return state

    def create(self, state: dict) -> Path:
        """创建 Runner，并同时生成初始 JSON 和 XLSX。"""
        self._validate_state(state)
        runner_id = state["runner_id"]
        runner_dir = self._runner_dir(runner_id)
        try:
            with self._lock(runner_id):
                if runner_dir.exists():
                    raise ClientError("RUNNER_STATE_INVALID", "Runner 已存在")
                runner_dir.mkdir(parents=True)
                json_path = self._json_path(runner_id)
                workbook_path = self._workbook_path(runner_id)
                try:
                    self._write_json(state, json_path)
                    write_workbook(state, workbook_path)
                except Exception:
                    shutil.rmtree(runner_dir, ignore_errors=True)
                    raise
                return workbook_path
        except Timeout as exc:
            raise ClientError("RUNNER_LOCK_TIMEOUT", "等待 Runner 文件锁超时") from exc
        except ClientError:
            raise
        except PermissionError as exc:
            raise ClientError("XLSX_LOCKED", "交付工作簿被占用") from exc
        except OSError as exc:
            raise ClientError("RUNNER_STATE_INVALID", "Runner 创建失败") from exc

    def read(self, runner_id: str) -> dict:
        """在锁内读取 Runner 当前状态。"""
        try:
            with self._lock(runner_id):
                return self._read_json(self._json_path(runner_id))
        except Timeout as exc:
            raise ClientError("RUNNER_LOCK_TIMEOUT", "等待 Runner 文件锁超时") from exc

    def mutate_state(self, runner_id: str, mutation: Callable[[dict], T]) -> T:
        """原子修改 JSON 状态，不重建 XLSX。"""
        try:
            with self._lock(runner_id):
                json_path = self._json_path(runner_id)
                state = copy.deepcopy(self._read_json(json_path))
                result = mutation(state)
                self._validate_state(state)
                temp_path = json_path.with_name(f"runner.{uuid4().hex}.tmp.json")
                try:
                    self._write_json(state, temp_path)
                    os.replace(temp_path, json_path)
                finally:
                    temp_path.unlink(missing_ok=True)
                return result
        except Timeout as exc:
            raise ClientError("RUNNER_LOCK_TIMEOUT", "等待 Runner 文件锁超时") from exc
        except ClientError:
            raise
        except OSError as exc:
            raise ClientError("RUNNER_STATE_INVALID", "Runner 状态保存失败") from exc

    def mutate_dataset(self, runner_id: str, mutation: Callable[[dict], T]) -> T:
        """原子修改数据状态，并刷新与之匹配的 XLSX。"""
        try:
            with self._lock(runner_id):
                json_path = self._json_path(runner_id)
                workbook_path = self._workbook_path(runner_id)
                state = copy.deepcopy(self._read_json(json_path))
                result = mutation(state)
                self._validate_state(state)
                token = uuid4().hex
                temp_json = json_path.with_name(f"runner.{token}.tmp.json")
                temp_xlsx = workbook_path.with_name(f"delivery.{token}.tmp.xlsx")
                backup_json = json_path.with_name(f"runner.{token}.bak.json")
                backup_xlsx = workbook_path.with_name(f"delivery.{token}.bak.xlsx")
                try:
                    self._write_json(state, temp_json)
                    write_workbook(state, temp_xlsx)
                    shutil.copy2(json_path, backup_json)
                    shutil.copy2(workbook_path, backup_xlsx)
                    try:
                        os.replace(temp_json, json_path)
                        os.replace(temp_xlsx, workbook_path)
                    except OSError:
                        os.replace(backup_json, json_path)
                        os.replace(backup_xlsx, workbook_path)
                        raise
                finally:
                    for path in (temp_json, temp_xlsx, backup_json, backup_xlsx):
                        path.unlink(missing_ok=True)
                return result
        except Timeout as exc:
            raise ClientError("RUNNER_LOCK_TIMEOUT", "等待 Runner 文件锁超时") from exc
        except ClientError:
            raise
        except PermissionError as exc:
            raise ClientError("XLSX_LOCKED", "交付工作簿被占用") from exc
        except OSError as exc:
            raise ClientError("RUNNER_STATE_INVALID", "Runner 数据保存失败") from exc

    def export(self, runner_id: str) -> Path:
        """以当前 JSON 状态重新生成交付工作簿。"""
        try:
            with self._lock(runner_id):
                state = self._read_json(self._json_path(runner_id))
                workbook_path = self._workbook_path(runner_id)
                temp_path = workbook_path.with_name(
                    f"delivery.{uuid4().hex}.tmp.xlsx"
                )
                try:
                    write_workbook(state, temp_path)
                    os.replace(temp_path, workbook_path)
                finally:
                    temp_path.unlink(missing_ok=True)
                return workbook_path
        except Timeout as exc:
            raise ClientError("RUNNER_LOCK_TIMEOUT", "等待 Runner 文件锁超时") from exc
        except ClientError:
            raise
        except PermissionError as exc:
            raise ClientError("XLSX_LOCKED", "交付工作簿被占用") from exc
        except OSError as exc:
            raise ClientError("RUNNER_STATE_INVALID", "交付工作簿导出失败") from exc

    def list_summaries(self) -> list[dict]:
        """按 Runner 创建时间列出可读状态摘要。"""
        if not self.runs_root.exists():
            return []
        summaries: list[dict] = []
        for json_path in self.runs_root.glob("*/runner.json"):
            state = self._read_json(json_path)
            summaries.append(
                {
                    "runner_id": state["runner_id"],
                    "name": state.get("name", ""),
                    "created_at": state.get("created_at", ""),
                    "updated_at": state.get("updated_at", ""),
                }
            )
        return sorted(summaries, key=lambda item: item["created_at"])
