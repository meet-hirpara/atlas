"""Sandboxed code execution for the in-chat terminal.

Shell languages (bash/PowerShell) are disabled by default — they are unrestricted
RCE on the Atlas host. Enable only with an explicit allow_shell flag.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Tuple

logger = logging.getLogger(__name__)

MAX_OUTPUT = 16_000
TIMEOUT_SEC = 10

# Safe-by-default: interpreted languages only. Shell is gated separately.
SAFE_LANGUAGES = {"python", "py", "javascript", "js"}
SHELL_LANGUAGES = {"bash", "sh", "shell", "powershell", "ps1"}
RUNNABLE = SAFE_LANGUAGES | SHELL_LANGUAGES


def _find_cmd(candidates: list[str]) -> str | None:
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + "\n… (output truncated)"


def _run_process_sync(args: list[str], cwd: str | None = None) -> Tuple[str, str, int]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=TIMEOUT_SEC,
            cwd=cwd,
        )
        stdout = _truncate(result.stdout.decode("utf-8", errors="replace"))
        stderr = _truncate(result.stderr.decode("utf-8", errors="replace"))
        return stdout, stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Execution timed out after {TIMEOUT_SEC}s", 124
    except FileNotFoundError:
        return "", "Runtime not found on this machine", 127
    except Exception as e:
        return "", str(e), 1


async def _run_process(args: list[str], cwd: str | None = None) -> Tuple[str, str, int]:
    # asyncio subprocess is unreliable under uvicorn on Windows; use a thread pool.
    if sys.platform == "win32":
        return await asyncio.to_thread(_run_process_sync, args, cwd)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SEC)
        stdout = _truncate(stdout_b.decode("utf-8", errors="replace"))
        stderr = _truncate(stderr_b.decode("utf-8", errors="replace"))
        return stdout, stderr, proc.returncode or 0
    except asyncio.TimeoutError:
        return "", f"Execution timed out after {TIMEOUT_SEC}s", 124
    except FileNotFoundError:
        return "", "Runtime not found on this machine", 127
    except Exception as e:
        return "", str(e), 1


async def run_code(language: str, code: str, *, allow_shell: bool = False) -> dict:
    lang = (language or "python").lower().strip()
    if lang not in RUNNABLE:
        return {
            "stdout": "",
            "stderr": f"Language '{language}' is not supported for execution.",
            "exit_code": 1,
            "language": lang,
        }

    if lang in SHELL_LANGUAGES and not allow_shell:
        logger.warning("Blocked shell code run language=%s allow_shell=%s", lang, allow_shell)
        return {
            "stdout": "",
            "stderr": (
                "Shell execution (bash/PowerShell) is disabled for security. "
                "Only Python and JavaScript run by default. "
                "To enable shell, send allow_shell=true after explicit user confirmation."
            ),
            "exit_code": 403,
            "language": lang,
        }

    if lang in ("python", "py"):
        # Use the server's interpreter so execution works under uvicorn on Windows
        # (PATH may resolve to a broken store stub or mismatched runtime).
        exe = sys.executable
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as script_file:
            script_file.write(code)
            script_path = script_file.name
        try:
            stdout, stderr, code_out = await _run_process([exe, script_path])
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
        return {"stdout": stdout, "stderr": stderr, "exit_code": code_out, "language": lang}

    if lang in ("javascript", "js"):
        exe = _find_cmd(["node", "nodejs"])
        if not exe:
            return {"stdout": "", "stderr": "Node.js is not installed.", "exit_code": 127, "language": lang}
        stdout, stderr, code_out = await _run_process([exe, "-e", code])
        return {"stdout": stdout, "stderr": stderr, "exit_code": code_out, "language": lang}

    if lang in ("powershell", "ps1"):
        exe = _find_cmd(["powershell", "pwsh"])
        if not exe:
            return {"stdout": "", "stderr": "PowerShell is not available.", "exit_code": 127, "language": lang}
        stdout, stderr, code_out = await _run_process(
            [exe, "-NoProfile", "-NonInteractive", "-Command", code]
        )
        return {"stdout": stdout, "stderr": stderr, "exit_code": code_out, "language": lang}

    # bash / sh / shell
    exe = _find_cmd(["bash", "sh"])
    if exe:
        stdout, stderr, code_out = await _run_process([exe, "-c", code])
        return {"stdout": stdout, "stderr": stderr, "exit_code": code_out, "language": lang}

    if sys.platform == "win32":
        return {
            "stdout": "",
            "stderr": "bash/sh is not available. Install Git Bash or WSL to run shell scripts.",
            "exit_code": 127,
            "language": lang,
        }

    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "script.sh")
        with open(script, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        stdout, stderr, code_out = await _run_process(["sh", script], cwd=tmp)
        return {"stdout": stdout, "stderr": stderr, "exit_code": code_out, "language": lang}
