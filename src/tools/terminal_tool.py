"""Wrapper around the Terminal MCP server."""
import subprocess
import sys

from exception import MyException
from logger import GLOBAL_LOGGER as logger


def run_command(command: str, cwd: str | None = None, timeout: int = 120) -> dict:
    """Run a shell command and capture its result.

    TODO: replace with an actual MCP terminal tool call once the
    Terminal MCP server is wired up.
    """
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        logger.info("run_command", command=command, returncode=result.returncode)
        return {
            "status": "pass" if result.returncode == 0 else "fail",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as e:
        logger.error("run_command_failed", command=command, error=str(e))
        raise MyException(e, sys) from e
