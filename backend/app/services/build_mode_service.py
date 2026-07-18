"""Detect project-build intents and supply production-ready coding guidance."""

import re
from typing import List, Tuple

BUILD_ACTION = re.compile(
    r"\b(build|create|scaffold|implement|develop|generate|make|write|code|setup|bootstrap|architect)\b",
    re.IGNORECASE,
)
BUILD_TARGET = re.compile(
    r"\b(project|app|application|website|web\s*app|api|service|system|platform|tool|"
    r"dashboard|chatbot|todo|backend|frontend|fullstack|full[\s-]?stack|codebase|repo|repository)\b",
    re.IGNORECASE,
)
BUILD_THIS = re.compile(
    r"\b(build|create|implement|scaffold|develop)\s+(this|the)\s+(project|app|api|application|system)\b",
    re.IGNORECASE,
)
FULL_APP = re.compile(
    r"\b(full|complete|production[\s-]?ready|entire|end[\s-]?to[\s-]?end)\s+"
    r"(app|application|project|stack|codebase|solution|system)\b",
    re.IGNORECASE,
)
BUILD_ME = re.compile(r"\bbuild\s+(me|us)\b", re.IGNORECASE)

FENCE_RE = re.compile(r"```([^\n`]+)\n([\s\S]*?)```", re.MULTILINE)
PATH_INFO_RE = re.compile(r"^(?:[\w+-]+:)?([\w./\\-]+\.[\w]+)$")

BUILD_MODE_PROMPT = """## Production build mode (ACTIVE)
The user wants a **complete, production-ready project** — not a toy snippet or single-file demo.

### Output structure
1. Brief overview (stack, architecture, key decisions).
2. **File tree** in a plain text block showing the project layout.
3. **Every source file** in its own fenced code block using this exact fence format:
   ```language:path/to/file.ext
   (file contents)
   ```
   Examples: ```typescript:src/App.tsx```, ```python:backend/app/main.py```, ```json:package.json```
4. **Setup & run** section with numbered steps (install deps, env vars, start commands). Mention `.env.example` keys in comments inside code — do not create separate markdown docs unless essential.

### Production standards (required)
- Proper project structure (`src/`, `components/`, `api/`, `tests/`, etc.) matching the stack.
- Environment configuration via env vars; never hardcode secrets, API keys, or tokens.
- Input validation, typed interfaces (TypeScript types / Python type hints).
- Error handling at API boundaries and user-facing error states in UI.
- Security basics: parameterized queries, CORS awareness, auth patterns when relevant.
- Lint-friendly formatting; consistent naming with the ecosystem (PEP 8, ESLint defaults).
- Include dependency manifests (`package.json`, `requirements.txt`, `pyproject.toml`, etc.) when applicable.
- Add focused tests when they meaningfully cover core logic (not trivial placeholders).

### Constraints
- Deliver ALL files needed to run the project — no "add the rest yourself".
- Prefer complete files over truncated examples with `// ... rest of code`.
- If scope is large, prioritize a runnable MVP with clear extension points.
- When indexed GitHub repos are provided, mirror their patterns only when genuinely relevant."""

BUILD_MODE_META = "Production build mode"


def is_build_request(message: str) -> bool:
    """Return True when the user is asking to build/scaffold a full project."""
    text = (message or "").strip()
    if not text:
        return False
    if BUILD_THIS.search(text) or FULL_APP.search(text):
        return True
    if BUILD_ME.search(text) and BUILD_TARGET.search(text):
        return True
    if BUILD_ACTION.search(text) and BUILD_TARGET.search(text):
        return True
    if re.search(r"\bscaffold\b", text, re.IGNORECASE):
        return True
    # "build a todo app" — action + implicit target via noun phrase
    if BUILD_ACTION.search(text) and re.search(
        r"\b(a|an|my|the)\s+[\w-]+\s+(app|api|service|site|tool)\b", text, re.IGNORECASE
    ):
        return True
    return False


def get_build_mode_prompt() -> str:
    return BUILD_MODE_PROMPT


def parse_fence_info(info: str) -> Tuple[str, str | None]:
    """Parse fence info string into (language, optional_file_path)."""
    trimmed = (info or "").strip()
    if not trimmed or trimmed.lower() == "mermaid":
        return trimmed, None
    m = PATH_INFO_RE.match(trimmed)
    if m:
        path = m.group(1).replace("\\", "/")
        colon = trimmed.find(":")
        lang = trimmed[:colon].strip() if colon > 0 else _infer_language(path)
        return lang or "text", path
    return trimmed, None


def _infer_language(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "ts": "typescript",
        "tsx": "typescript",
        "js": "javascript",
        "jsx": "javascript",
        "py": "python",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "html": "html",
        "css": "css",
        "md": "markdown",
        "sql": "sql",
        "sh": "bash",
        "env": "bash",
    }.get(ext, ext or "text")


def extract_project_files(markdown: str) -> List[dict]:
    """Extract multi-file project blocks from assistant markdown."""
    files: List[dict] = []
    for match in FENCE_RE.finditer(markdown or ""):
        lang, path = parse_fence_info(match.group(1))
        if path:
            files.append(
                {
                    "path": path,
                    "language": lang,
                    "content": match.group(2).rstrip("\n"),
                }
            )
    return files


def count_project_files(markdown: str) -> int:
    return len(extract_project_files(markdown))
