import os
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: Dict[str, Any], view) -> Any: ...


class FileIOTool(Tool):
    name = "file_io"
    description = "Read, write, list, or delete files safely. Supports path validation."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"enum": ["read", "write", "append", "list", "delete"]},
            "path": {"type": "string"},
            "content": {"type": "string"},
            "mode": {"enum": ["text", "json", "binary"], "default": "text"}
        },
        "required": ["action", "path"]
    }

    def __init__(
        self,
        allowed_base_dirs: Optional[list] = None,
        max_read_size: int = 1_000_000,
        max_write_size: int = 5_000_000,
    ):
        self.allowed_base_dirs = allowed_base_dirs
        self.max_read_size = max_read_size
        self.max_write_size = max_write_size

    def _safe_path(self, path: str) -> Path:
        p = Path(path).resolve()
        if self.allowed_base_dirs:
            allowed = any(p == Path(d).resolve() or str(p).startswith(str(Path(d).resolve())) for d in self.allowed_base_dirs)
            if not allowed:
                raise PermissionError(f"Path outside allowed directories: {path}")
        return p

    async def run(self, input, view):
        action = input["action"]
        path = input["path"]
        mode = input.get("mode", "text")
        try:
            safe = self._safe_path(path)
        except PermissionError as e:
            return {"error": str(e)}

        try:
            if action == "read":
                if not safe.exists():
                    return {"error": f"File not found: {path}"}
                if safe.is_dir():
                    return {"error": f"Path is a directory: {path}"}
                if mode == "json":
                    content = await asyncio.to_thread(safe.read_text, encoding="utf-8")
                    return json.loads(content)
                elif mode == "text":
                    stat = safe.stat()
                    if stat.st_size > self.max_read_size:
                        return {"error": f"File too large ({stat.st_size} bytes), max {self.max_read_size}"}
                    content = await asyncio.to_thread(safe.read_text, encoding="utf-8")
                    return content
                else:
                    return {"error": "Binary mode not supported for safety"}

            elif action == "write":
                content = input.get("content", "")
                if len(content) > self.max_write_size:
                    return {"error": f"Content too large ({len(content)} bytes)"}
                safe.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(safe.write_text, content, encoding="utf-8")
                return f"Written {len(content)} bytes to {path}"

            elif action == "append":
                content = input.get("content", "")
                if len(content) > self.max_write_size:
                    return {"error": f"Content too large ({len(content)} bytes)"}
                safe.parent.mkdir(parents=True, exist_ok=True)
                f = await asyncio.to_thread(safe.open, "a", encoding="utf-8")
                try:
                    f.write(content)
                finally:
                    f.close()
                return f"Appended {len(content)} bytes to {path}"

            elif action == "list":
                if not safe.exists():
                    return {"error": f"Directory not found: {path}"}
                if not safe.is_dir():
                    return {"error": f"Path is not a directory: {path}"}
                entries = []
                for item in safe.iterdir():
                    entries.append({"name": item.name, "is_dir": item.is_dir(), "is_file": item.is_file()})
                return {"path": str(safe), "entries": entries}

            elif action == "delete":
                if not safe.exists():
                    return {"error": f"File not found: {path}"}
                if safe.is_dir():
                    await asyncio.to_thread(lambda: safe.rmdir())
                else:
                    await asyncio.to_thread(safe.unlink)
                return f"Deleted {path}"

            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}
