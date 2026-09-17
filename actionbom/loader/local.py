from __future__ import annotations

import os
from typing import Optional


class LocalLoader:
    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = base_dir or os.getcwd()

    def abspath(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(self.base_dir, path))

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        full = self.abspath(path)
        with open(full, "r", encoding=encoding) as f:
            return f.read()

    def exists(self, path: str) -> bool:
        return os.path.exists(self.abspath(path))
