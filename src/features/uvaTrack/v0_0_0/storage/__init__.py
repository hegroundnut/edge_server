"""
数据持久化模块

提供通用 Repository 接口和 SQLite 默认实现。
切换数据库只需替换实现类（如 PostgreSQLRepository）。
"""
from .repository import BaseRepository
from .sqlite_repository import SQLiteRepository

__all__ = [
    "BaseRepository",
    "SQLiteRepository",
]
