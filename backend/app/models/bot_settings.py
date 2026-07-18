from typing import Literal, Optional
from pydantic import BaseModel, Field


class BotSettings(BaseModel):
    personality: Literal["professional", "friendly", "concise", "teacher"] = "teacher"
    response_length: Literal["brief", "balanced", "detailed"] = Field(
        default="detailed", alias="responseLength"
    )
    creativity: Literal["precise", "balanced", "creative"] = "balanced"
    clarify_questions: bool = Field(default=True, alias="clarifyQuestions")
    diagram_mode: Literal["auto", "on_request", "off"] = Field(
        default="auto", alias="diagramMode"
    )
    code_style: Literal["minimal", "commented", "production"] = Field(
        default="commented", alias="codeStyle"
    )
    custom_instructions: str = Field(default="", alias="customInstructions")
    model_selection: str = Field(default="mistral-large", alias="modelSelection")
    ocr_model_selection: str = Field(default="auto", alias="ocrModelSelection")
    web_search_mode: Literal["auto", "on", "off"] = Field(default="auto", alias="webSearchMode")
    active_github_repo_ids: list[str] = Field(default_factory=list, alias="activeGithubRepoIds")

    class Config:
        populate_by_name = True
