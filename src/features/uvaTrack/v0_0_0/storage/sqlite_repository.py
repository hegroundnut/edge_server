"""
SQLite 数据持久化实现

使用标准库 sqlite3，无需额外依赖。
切换 PostgreSQL 时只需新建 PostgreSQLRepository 实现 BaseRepository 接口，
将 SQL 语法适配即可（如 ? → %s，AUTOINCREMENT → SERIAL 等）。
"""
import json
import logging
import sqlite3
import threading
from typing import Dict, Any, List, Optional

from .repository import BaseRepository

logger = logging.getLogger(__name__)


class SQLiteRepository(BaseRepository):
    """SQLite 持久化实现"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        """每线程独立连接（sqlite3 不支持跨线程共享连接）"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    # ------------------------------------------------------------------
    #  生命周期
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info("SQLite database initialized: %s", self._db_path)

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ------------------------------------------------------------------
    #  导航任务
    # ------------------------------------------------------------------

    def save_task(self, task_dict: Dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO navigation_tasks
                (task_id, instruction_id, box_id, device_id,
                 target_position, algorithm, parameters,
                 status, trajectory_id, created_at, submitted_at,
                 completed_at, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_dict["task_id"],
                task_dict.get("instruction_id", ""),
                task_dict.get("box_id", ""),
                task_dict.get("device_id", ""),
                json.dumps(task_dict.get("target_position", {})),
                task_dict.get("algorithm", "simple_linear"),
                json.dumps(task_dict.get("parameters", {})),
                task_dict.get("status", "pending"),
                task_dict.get("trajectory_id"),
                task_dict.get("created_at", 0),
                task_dict.get("submitted_at"),
                task_dict.get("completed_at"),
                json.dumps(task_dict.get("result", {})),
            ),
        )
        conn.commit()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM navigation_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return _row_to_task(row) if row else None

    def list_tasks(
        self,
        box_id: str = "all",
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        clauses: List[str] = []
        params: List[Any] = []
        if box_id != "all":
            clauses.append("box_id = ?")
            params.append(box_id)
        if status:
            clauses.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM navigation_tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_task(r) for r in rows]

    def count_tasks(self, box_id: str = "all", status: Optional[str] = None) -> int:
        conn = self._get_conn()
        clauses: List[str] = []
        params: List[Any] = []
        if box_id != "all":
            clauses.append("box_id = ?")
            params.append(box_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        row = conn.execute(f"SELECT COUNT(*) FROM navigation_tasks {where}", params).fetchone()
        return row[0]

    def update_task(self, task_id: str, **fields) -> bool:
        if not fields:
            return False
        conn = self._get_conn()
        set_parts = []
        params: List[Any] = []
        for key, value in fields.items():
            if key in ("target_position", "parameters", "result"):
                value = json.dumps(value)
            set_parts.append(f"{key} = ?")
            params.append(value)
        params.append(task_id)
        cursor = conn.execute(
            f"UPDATE navigation_tasks SET {', '.join(set_parts)} WHERE task_id = ?",
            params,
        )
        conn.commit()
        return cursor.rowcount > 0

    def find_task_by_trajectory(self, trajectory_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM navigation_tasks WHERE trajectory_id = ? AND status = 'executing' LIMIT 1",
            (trajectory_id,),
        ).fetchone()
        return _row_to_task(row) if row else None

    def find_pending_task(self, box_id: str, device_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            """SELECT * FROM navigation_tasks
               WHERE box_id = ? AND device_id = ? AND status IN ('pending', 'executing')
               ORDER BY created_at DESC LIMIT 1""",
            (box_id, device_id),
        ).fetchone()
        return _row_to_task(row) if row else None

    # ------------------------------------------------------------------
    #  无人机设备
    # ------------------------------------------------------------------

    def save_device(self, device_dict: Dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO drone_devices
                (device_id, box_id, device_type, protocol,
                 status, last_heartbeat, position, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_dict["device_id"],
                device_dict.get("box_id", ""),
                device_dict.get("device_type", "quadcopter"),
                device_dict.get("protocol", "mavlink"),
                device_dict.get("status", "online"),
                device_dict.get("last_heartbeat", 0),
                json.dumps(device_dict.get("position", {})),
                json.dumps(device_dict.get("metadata", {})),
            ),
        )
        conn.commit()

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM drone_devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        return _row_to_device(row) if row else None

    def list_devices(self, box_id: str = "all") -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if box_id == "all":
            rows = conn.execute("SELECT * FROM drone_devices ORDER BY device_id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM drone_devices WHERE box_id = ? ORDER BY device_id",
                (box_id,),
            ).fetchall()
        return [_row_to_device(r) for r in rows]

    def delete_devices_by_box(self, box_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM drone_devices WHERE box_id = ?", (box_id,))
        conn.commit()
        return cursor.rowcount

    def update_device_status_by_box(self, box_id: str, status: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE drone_devices SET status = ? WHERE box_id = ? AND status != ?",
            (status, box_id, status),
        )
        conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    #  心跳日志
    # ------------------------------------------------------------------

    def save_heartbeat_log(self, log_dict: Dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO heartbeat_logs (box_id, timestamp, drone_count, online_count, raw_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                log_dict.get("box_id", ""),
                log_dict.get("timestamp", 0),
                log_dict.get("drone_count", 0),
                log_dict.get("online_count", 0),
                json.dumps(log_dict),
            ),
        )
        conn.commit()

    def list_heartbeat_logs(
        self,
        box_id: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if box_id == "all":
            rows = conn.execute(
                "SELECT * FROM heartbeat_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM heartbeat_logs WHERE box_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (box_id, limit, offset),
            ).fetchall()
        return [_row_to_heartbeat_log(r) for r in rows]

    def cleanup_heartbeat_logs(self, older_than_timestamp: float) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM heartbeat_logs WHERE timestamp < ?", (older_than_timestamp,)
        )
        conn.commit()
        return cursor.rowcount


# ======================================================================
#  建表 SQL
# ======================================================================

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS navigation_tasks (
    task_id         TEXT PRIMARY KEY,
    instruction_id  TEXT NOT NULL DEFAULT '',
    box_id          TEXT NOT NULL DEFAULT '',
    device_id       TEXT NOT NULL DEFAULT '',
    target_position TEXT NOT NULL DEFAULT '{}',
    algorithm       TEXT NOT NULL DEFAULT 'simple_linear',
    parameters      TEXT NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending',
    trajectory_id   TEXT,
    created_at      REAL NOT NULL DEFAULT 0,
    submitted_at    REAL,
    completed_at    REAL,
    result          TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tasks_box_id ON navigation_tasks(box_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON navigation_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_trajectory ON navigation_tasks(trajectory_id);

CREATE TABLE IF NOT EXISTS drone_devices (
    device_id       TEXT PRIMARY KEY,
    box_id          TEXT NOT NULL DEFAULT '',
    device_type     TEXT NOT NULL DEFAULT 'quadcopter',
    protocol        TEXT NOT NULL DEFAULT 'mavlink',
    status          TEXT NOT NULL DEFAULT 'online',
    last_heartbeat  REAL NOT NULL DEFAULT 0,
    position        TEXT NOT NULL DEFAULT '{}',
    metadata        TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_devices_box_id ON drone_devices(box_id);

CREATE TABLE IF NOT EXISTS heartbeat_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    box_id          TEXT NOT NULL DEFAULT '',
    timestamp       REAL NOT NULL DEFAULT 0,
    drone_count     INTEGER NOT NULL DEFAULT 0,
    online_count    INTEGER NOT NULL DEFAULT 0,
    raw_data        TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_box_id ON heartbeat_logs(box_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_timestamp ON heartbeat_logs(timestamp);
"""


# ======================================================================
#  行转字典
# ======================================================================

def _row_to_task(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "instruction_id": row["instruction_id"],
        "box_id": row["box_id"],
        "device_id": row["device_id"],
        "target_position": json.loads(row["target_position"]),
        "algorithm": row["algorithm"],
        "parameters": json.loads(row["parameters"]),
        "status": row["status"],
        "trajectory_id": row["trajectory_id"],
        "created_at": row["created_at"],
        "submitted_at": row["submitted_at"],
        "completed_at": row["completed_at"],
        "result": json.loads(row["result"]),
    }


def _row_to_device(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "device_id": row["device_id"],
        "box_id": row["box_id"],
        "device_type": row["device_type"],
        "protocol": row["protocol"],
        "status": row["status"],
        "last_heartbeat": row["last_heartbeat"],
        "position": json.loads(row["position"]),
        "metadata": json.loads(row["metadata"]),
    }


def _row_to_heartbeat_log(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "box_id": row["box_id"],
        "timestamp": row["timestamp"],
        "drone_count": row["drone_count"],
        "online_count": row["online_count"],
        "raw_data": json.loads(row["raw_data"]),
    }
