import json
import re
from dataclasses import dataclass
from typing import List, Optional

from app.services.model_registry import get_composer_model, resolve_mistral_model_id
from app.services.model_service import pick_specialist

CODE_PATTERNS = re.compile(
    r"\b(code|python|javascript|typescript|java|rust|golang|debug|function|class|api|sql|regex|algorithm|implement|refactor)\b",
    re.I,
)
DESIGN_PATTERNS = re.compile(
    r"\b(diagram|flowchart|architecture|design|ui|ux|wireframe|mockup|mermaid|visual|layout|prototype)\b",
    re.I,
)
OCR_PATTERNS = re.compile(
    r"\b(ocr|scan|scanned|extract text|read (this |the )?pdf|document extraction|handwriting|receipt|invoice)\b",
    re.I,
)
COMPLEX_PATTERNS = re.compile(
    r"\b(and also|compare|analyze|research|step by step|multiple|both|as well as|then|after that)\b",
    re.I,
)


@dataclass
class SubTask:
    role: str  # thinker | worker | verifier | synthesizer
    task_type: str
    prompt: str
    model_id: str


@dataclass
class RoutingPlan:
    mode: str  # single | multi
    primary_model: str
    subtasks: List[SubTask]
    explanation: str


def _detect_primary_type(message: str) -> str:
    if CODE_PATTERNS.search(message) and DESIGN_PATTERNS.search(message):
        return "multi"
    if CODE_PATTERNS.search(message):
        return "code"
    if OCR_PATTERNS.search(message):
        return "ocr"
    if DESIGN_PATTERNS.search(message):
        return "design"
    return "qa"


def _needs_multi_model(message: str) -> bool:
    if CODE_PATTERNS.search(message) and DESIGN_PATTERNS.search(message):
        return True
    if len(message) > 400 and COMPLEX_PATTERNS.search(message):
        return True
    bullets = message.count("\n-") + message.count("\n1.")
    if bullets >= 2:
        return True
    return False


def build_routing_plan(
    message: str,
    models: List[dict],
    user_model: str = "auto",
) -> RoutingPlan:
    if user_model and user_model != "auto":
        resolved = resolve_mistral_model_id(user_model) or user_model
        preset = get_composer_model(user_model)
        label = preset.display_name if preset else user_model
        return RoutingPlan(
            mode="single",
            primary_model=resolved,
            subtasks=[],
            explanation=f"Using {label}",
        )

    primary_type = _detect_primary_type(message)

    if not _needs_multi_model(message):
        task_type = (
            "code" if primary_type == "code"
            else "ocr" if primary_type == "ocr"
            else "design" if primary_type == "design"
            else "qa"
        )
        model = pick_specialist(models, task_type)
        labels = {
            "code": "Codestral for coding",
            "design": "Pixtral for design & diagrams",
            "ocr": "Mistral OCR for documents",
            "qa": "Fable 5 for Q&A",
        }
        return RoutingPlan(
            mode="single",
            primary_model=model,
            subtasks=[],
            explanation=f"Auto → {labels.get(task_type, model)}",
        )

    # Fugu-inspired Trinity: Thinker → Workers → Synthesizer
    subtasks: List[SubTask] = []
    planner = pick_specialist(models, "plan")

    subtasks.append(SubTask(
        role="thinker",
        task_type="plan",
        prompt=(
            f"Analyze this user request and outline the key sub-problems (max 3). "
            f"Be concise.\n\nUser request:\n{message}"
        ),
        model_id=planner,
    ))

    workers_needed = []
    if CODE_PATTERNS.search(message):
        workers_needed.append(("code", "Solve the coding/programming aspects of this request in detail."))
    if DESIGN_PATTERNS.search(message):
        workers_needed.append(("design", "Address the design, architecture, or diagram aspects."))
    if not workers_needed or COMPLEX_PATTERNS.search(message):
        workers_needed.append(("qa", "Answer the general knowledge and reasoning parts."))

    for task_type, instruction in workers_needed[:3]:
        subtasks.append(SubTask(
            role="worker",
            task_type=task_type,
            prompt=f"{instruction}\n\nOriginal request:\n{message}",
            model_id=pick_specialist(models, task_type),
        ))

    synthesizer = pick_specialist(models, "synthesis")
    subtasks.append(SubTask(
        role="synthesizer",
        task_type="synthesis",
        prompt="",  # filled after workers run
        model_id=synthesizer,
    ))

    used = ", ".join({t.model_id for t in subtasks})
    return RoutingPlan(
        mode="multi",
        primary_model=synthesizer,
        subtasks=subtasks,
        explanation=f"Auto → Multi-model orchestration (Fugu-style): {used}",
    )


def parse_thinker_outline(text: str) -> str:
    return text.strip()[:1500]
