import asyncio
import ast
import textwrap
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: dict[str, Any], view) -> Any: ...


class CodeExecTool(Tool):
    """
    Code execution tool with sandbox security and concurrency limits.
    
    🔧 PERFORMANCE FIX: Added Semaphore to limit concurrent subprocesses.
    Without this limit, 100 concurrent requests could spawn 100 Python processes,
    overwhelming system resources (CPU, memory, PID limit).
    """
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
                       "importlib", "platform", "getpass", "pwd", "grp", "signal",
                       "builtins", "__builtins__"}
    BLOCKED_BUILTINS = {"__import__", "eval", "exec", "compile", "open", "input",
                        "globals", "locals", "vars", "dir", "setattr", "getattr",
                        "delattr", "breakpoint", "exit", "quit"}

    # 🔧 PERFORMANCE FIX: Class-level semaphore for concurrent execution limit
    # This prevents resource exhaustion from too many subprocesses
    _semaphore: asyncio.Semaphore | None = None
    MAX_CONCURRENT_EXEC = 5  # Maximum 5 concurrent code executions

    def __init__(self, timeout: int = 10, max_output_length: int = 10000):
        self.timeout = timeout
        self.max_output_length = max_output_length
        
        # Initialize semaphore if not already done
        if CodeExecTool._semaphore is None:
            CodeExecTool._semaphore = asyncio.Semaphore(CodeExecTool.MAX_CONCURRENT_EXEC)

    @classmethod
    def _check_safety_ast(cls, code: str) -> str | None:
        """
        🔒 SECURITY FIX: Use AST parsing for robust safety analysis.
        
        Previous string-matching implementation could be bypassed by:
        - import os as x
        - __import__('os')
        - getattr(__builtins__, 'eval')(...)
        - Indirect imports via importlib
        
        AST-based analysis catches:
        - All import statements (import x, from x import y, import x as z)
        - All calls to blocked builtins
        - Attribute access patterns that might bypass restrictions
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"Syntax error in code: {e}"
        
        for node in ast.walk(tree):
            # Check import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]  # Handle os.path
                    if module_name in cls.BLOCKED_IMPORTS:
                        return f"Import '{alias.name}' is not allowed in sandbox"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name in cls.BLOCKED_IMPORTS:
                        return f"Import from '{node.module}' is not allowed in sandbox"
                # Also check imported names
                for alias in node.names:
                    if alias.name in cls.BLOCKED_BUILTINS:
                        return f"Importing '{alias.name}' is not allowed"
            
            # Check function calls
            elif isinstance(node, ast.Call):
                # Direct name calls: eval(...)
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.BLOCKED_BUILTINS:
                        return f"Call to '{node.func.id}()' is not allowed in sandbox"
                
                # Attribute calls: getattr(...) or obj.eval(...)
                elif isinstance(node.func, ast.Attribute):
                    # Check for getattr(__builtins__, 'eval') pattern
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id in ("__builtins__", "builtins"):
                            return f"Accessing builtins via attributes is not allowed"
                    # Check for obj.__import__ style
                    if node.func.attr in cls.BLOCKED_BUILTINS:
                        return f"Call to '{node.func.attr}()' via attribute is not allowed"
            
            # Check attribute access that might be dangerous
            elif isinstance(node, ast.Attribute):
                if node.attr in cls.BLOCKED_BUILTINS:
                    return f"Access to '{node.attr}' attribute is restricted"
        
        return None

    async def run(self, input, view):
        code = input.get("code", "")
        timeout = input.get("timeout", self.timeout)

        # 🔒 SECURITY FIX: Use AST-based safety check instead of string matching
        safety_check = self._check_safety_ast(code)
        if safety_check:
            return {"error": safety_check}

        # 🔧 PERFORMANCE FIX: Acquire semaphore before creating subprocess
        # This ensures max MAX_CONCURRENT_EXEC processes running simultaneously
        async with CodeExecTool._semaphore:
            return await self._execute_code(code, timeout)

    async def _execute_code(self, code: str, timeout: int) -> dict:
        """Internal execution with subprocess (called under semaphore)."""
        
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
            return {"error": f"Execution failed: {e!s}"}
    
    @classmethod
    def set_concurrency_limit(cls, limit: int):
        """Adjust the maximum concurrent executions (for tuning)."""
        cls.MAX_CONCURRENT_EXEC = limit
        cls._semaphore = asyncio.Semaphore(limit)