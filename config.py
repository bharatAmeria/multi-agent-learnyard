"""Central configuration and environment loading."""
import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv
from exception import MyException
from logger import GLOBAL_LOGGER as logger
load_dotenv()
@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o")
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "memory/memory.db")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "ai-software-eng-team")
    max_debug_retries: int = int(os.getenv("MAX_DEBUG_RETRIES", "3"))
    max_review_revisions: int = int(os.getenv("MAX_REVIEW_REVISIONS", "3"))
    review_pass_threshold: float = float(os.getenv("REVIEW_PASS_THRESHOLD", "8.0"))
try:
    settings = Settings()
    logger.info(
        "settings_loaded",
        model_name=settings.model_name,
        llm_key_configured=bool(settings.openai_api_key),
    )
except Exception as e:
    raise MyException(e, sys)