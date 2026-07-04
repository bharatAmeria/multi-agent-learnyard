"""Pydantic models for structured agent I/O."""
from pydantic import BaseModel


class StructuredRequirement(BaseModel):
    project_type: str
    summary: str
    key_features: list[str] = []


class ArchitectureDoc(BaseModel):
    summary: str
    components: list[str] = []
    tech_stack: list[str] = []


class CodingTask(BaseModel):
    file_path: str
    description: str


class ExecutionResult(BaseModel):
    status: str  # "pass" | "fail"
    log: str = ""


class ReviewResult(BaseModel):
    feedback: str
    quality_score: float
