from __future__ import annotations

import sqlite3
from pathlib import Path


class ClosingConnection(sqlite3.Connection):
    """Commit or roll back like sqlite3.Connection, then always close."""

    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def connect(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path, factory=ClosingConnection)
