import asyncio
import textwrap
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: Dict[str, Any], view) -> Any: ...


class CodeExecTool(Tool):
    name = "code_exec"
    description = "Execute Python code in a restricted sandbox with timeout."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "language": {"enum": ["python"], "default": "python"},
            "timeout": {"type": "integer", "default": 10}
        },
        "required": ["code"]
    }

    BLOCKED_IMPORTS = {"os", "sys", "subprocess", "socket", "http", "urllib", "requests",
                       "shutil", "pathlib", "io", "ctypes", "pickle", "marshal",
                       "importlib", "platform", "getpass", "pwd", "grp", "signal"}
    BLOCKED_BUILTINS = {"__import__", "eval", "exec", "compile", "open", "input",
                        "globals", "locals", "vars", "dir", "setattr", "getattr",
                        "delattr", "breakpoint"}

    def __init__(self, timeout: int = 10, max_output_length: int = 10000):
        self.timeout = timeout
        self.max_output_length = max_output_length

    @classmethod
    def _check_safety(cls, code: str) -> Optional[str]:
        """Quick static check for dangerous imports/calls."""
        for banned in cls.BLOCKED_IMPORTS:
            if f"import {banned}" in code or f"from {banned}" in code:
                return f"Import '{banned}' is not allowed in sandbox"
        for banned in cls.BLOCKED_BUILTINS:
            if f"{banned}(" in code:
                return f"Call to '{banned}()' is not allowed in sandbox"
        return None

    async def run(self, input, view):
        code = input.get("code", "")
        timeout = input.get("timeout", self.timeout)

        safety_check = self._check_safety(code)
        if safety_check:
            return {"error": safety_check}

        # Wrap code to capture stdout and result
        wrapped = textwrap.dedent(f"""
import sys
from io import StringIO
_old_stdout = sys.stdout
sys.stdout = StringIO()
_result = None
try:
    _result = eval(compile('''{code}''', '<sandbox>', 'exec'))
except Exception as _e:
    _result = f"RuntimeError: {{_e}}"
_output = sys.stdout.getvalue()
sys.stdout = _old_stdout
""")

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", wrapped,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            # Truncate if too long
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length] + "\n...(truncated)"

            return {
                "stdout": output.strip() if output else None,
                "stderr": error.strip() if error else None,
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"error": f"Code execution timed out after {timeout}s"}
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}
