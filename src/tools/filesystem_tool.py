"""Wrapper around the Filesystem MCP server."""
import sys
from pathlib import Path

from exception import MyException
from logger import GLOBAL_LOGGER as logger


def write_file(path: str, content: str) -> str:
    """Write content to path, creating parent directories as needed.

    TODO: replace with an actual MCP filesystem tool call once the
    Filesystem MCP server is wired up; this local fallback is fine for
    early development.
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        logger.info("file_written", path=str(p))
        return str(p)
    except Exception as e:
        logger.error("write_file_failed", path=path, error=str(e))
        raise MyException(e, sys) from e


def read_file(path: str) -> str:
    try:
        return Path(path).read_text()
    except Exception as e:
        logger.error("read_file_failed", path=path, error=str(e))
        raise MyException(e, sys) from e
