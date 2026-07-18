from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.services.code_runner_service import run_code
from app.services.local_auth import require_local_auth

router = APIRouter(prefix="/api/code", tags=["code"])


class CodeRunRequest(BaseModel):
    language: str = Field(default="python")
    code: str = Field(min_length=1, max_length=50_000)
    # Shell languages require explicit confirmation — unrestricted host RCE otherwise.
    allow_shell: bool = Field(default=False, alias="allowShell")

    class Config:
        populate_by_name = True


@router.post("/run", dependencies=[Depends(require_local_auth)])
async def execute_code(body: CodeRunRequest):
    result = await run_code(body.language, body.code, allow_shell=body.allow_shell)
    return result
