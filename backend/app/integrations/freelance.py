"""Freelance platform integrations — profile-linked assistant tools (no fake API access)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.web_search_service import format_results_for_llm, search_web

# ── Platform metadata ────────────────────────────────────────────────────────

PLATFORM_DOMAINS: Dict[str, str] = {
    "upwork": "upwork.com",
    "fiverr": "fiverr.com",
    "freelancer": "freelancer.com",
    "toptal": "toptal.com",
    "peopleperhour": "peopleperhour.com",
    "guru": "guru.com",
    "malt": "malt.com",
    "contra": "contra.com",
    "99designs": "99designs.com",
    "designcrowd": "designcrowd.com",
    "workana": "workana.com",
    "truelancer": "truelancer.com",
    "bark": "bark.com",
}

PLATFORM_JOB_SEARCH_URLS: Dict[str, str] = {
    "upwork": "https://www.upwork.com/nx/search/jobs/?q={query}",
    "fiverr": "https://www.fiverr.com/search/gigs?query={query}",
    "freelancer": "https://www.freelancer.com/jobs/{query}/",
    "peopleperhour": "https://www.peopleperhour.com/freelance-jobs?q={query}",
    "guru": "https://www.guru.com/d/jobs/q/{query}/",
    "contra": "https://contra.com/opportunities?q={query}",
    "99designs": "https://99designs.com/contests?search={query}",
    "designcrowd": "https://www.designcrowd.com/jobs?search={query}",
    "workana": "https://www.workana.com/jobs?query={query}",
    "truelancer": "https://www.truelancer.com/freelance-jobs?q={query}",
    "bark": "https://www.bark.com/en/us/{query}/",
}

ASSISTANT_CAPABILITIES = [
    "Search public job listings via web search (not authenticated platform API)",
    "Draft tailored proposals from job descriptions you paste or link",
    "Summarize your saved freelancer profile, skills, and rates",
    "Track active gigs you list manually during setup",
    "Draft client follow-up messages for proposals and projects",
]

API_LIMITATION_NOTE = (
    "These tools use your saved profile plus public web search. "
    "They do NOT access your logged-in account, messages, or private job feeds."
)


def get_freelance_capabilities() -> List[str]:
    return list(ASSISTANT_CAPABILITIES)


# ── Validation & labels ──────────────────────────────────────────────────────

def _require_profile_identifier(creds: Dict[str, Any]) -> None:
    profile = str(creds.get("profile_url", "")).strip()
    username = str(creds.get("username", "")).strip()
    api_key = str(creds.get("api_key", "")).strip()
    api_token = str(creds.get("api_token", "")).strip()
    if not profile and not username and not api_key and not api_token:
        raise ValueError("Provide at least a profile URL, username, or API key")


def _validate_profile_url(url: str) -> None:
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Profile URL must be a valid http(s) link")


def validate_freelance_connection(platform_name: str, status: str, docs_url: str, creds: Dict[str, Any]) -> str:
    """Validate and save freelance profile."""
    _require_profile_identifier(creds)
    _validate_profile_url(str(creds.get("profile_url", "")).strip())

    profile = str(creds.get("profile_url", "")).strip() or str(creds.get("username", "")).strip()
    niche = str(creds.get("niche", "")).strip()
    skills = str(creds.get("skills", "")).strip()

    parts = [f"{platform_name} profile saved ({profile})."]
    if niche or skills:
        parts.append(f"Niche: {niche or 'not set'}. Skills: {skills or 'not set'}.")

    if status in ("coming_soon", "oauth_required", "manual_token"):
        parts.append(
            f"No live {platform_name} API is connected — assistant mode is active: "
            "job search (public web), proposal drafts, follow-ups, and profile summary."
        )
        if status == "oauth_required":
            parts.append(f"Full OAuth automation pending — docs: {docs_url or 'platform developer portal'}.")
        elif status == "manual_token":
            has_key = bool(str(creds.get("api_key", "")).strip() or str(creds.get("api_token", "")).strip())
            if has_key:
                parts.append("API key stored for future use when developer access is approved.")
            else:
                parts.append(f"Add an API key later if you receive developer access — {docs_url or 'see platform docs'}.")
    else:
        parts.append("Freelance assistant tools are ready.")

    return " ".join(parts)


def build_freelance_label(creds: Dict[str, Any], fallback: str) -> str:
    url = str(creds.get("profile_url", "")).strip()
    if url:
        try:
            host = urlparse(url).netloc.replace("www.", "")
            if host:
                username = str(creds.get("username", "")).strip()
                return f"{username}@{host}" if username else host
        except Exception:
            pass
    username = str(creds.get("username", "")).strip()
    niche = str(creds.get("niche", "")).strip()
    if username and niche:
        return f"{username} · {niche}"
    return username or fallback


# ── Profile helpers ──────────────────────────────────────────────────────────

def _parse_skills(raw: str) -> List[str]:
    if not raw.strip():
        return []
    parts = re.split(r"[,;\n|]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _parse_active_gigs(raw: str) -> List[Dict[str, str]]:
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [g for g in data if isinstance(g, dict)]
    except json.JSONDecodeError:
        pass
    gigs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            title, status = line.split("|", 1)
            gigs.append({"title": title.strip(), "status": status.strip()})
        else:
            gigs.append({"title": line, "status": "active"})
    return gigs


def _profile_context(creds: Dict[str, Any], platform_name: str) -> Dict[str, Any]:
    return {
        "platform": platform_name,
        "profile_url": str(creds.get("profile_url", "")).strip(),
        "username": str(creds.get("username", "")).strip(),
        "niche": str(creds.get("niche", "")).strip(),
        "skills": _parse_skills(str(creds.get("skills", ""))),
        "hourly_rate": str(creds.get("hourly_rate", "")).strip(),
        "notes": str(creds.get("notes", "")).strip(),
        "active_gigs": _parse_active_gigs(str(creds.get("active_gigs", ""))),
    }


def _match_score(job_text: str, skills: List[str], niche: str) -> int:
    text = job_text.lower()
    score = 0
    if niche and niche.lower() in text:
        score += 2
    for skill in skills:
        if skill.lower() in text:
            score += 1
    return score


# ── Tool actions ─────────────────────────────────────────────────────────────

def freelance_profile_summary(
    platform_id: str,
    platform_name: str,
    status: str,
    docs_url: str,
    creds: Dict[str, Any],
) -> str:
    ctx = _profile_context(creds, platform_name)
    lines = [
        f"## {platform_name} profile summary",
        f"- **Profile URL:** {ctx['profile_url'] or 'not set'}",
        f"- **Username:** {ctx['username'] or 'not set'}",
        f"- **Niche:** {ctx['niche'] or 'not set'}",
        f"- **Hourly rate:** {ctx['hourly_rate'] or 'not set'}",
        f"- **Skills:** {', '.join(ctx['skills']) if ctx['skills'] else 'not set'}",
    ]
    if ctx["notes"]:
        lines.append(f"- **Notes:** {ctx['notes']}")
    if ctx["active_gigs"]:
        lines.append(f"- **Active gigs tracked:** {len(ctx['active_gigs'])}")
        for g in ctx["active_gigs"][:5]:
            lines.append(f"  - {g.get('title', 'Untitled')} ({g.get('status', 'active')})")

    lines.append("")
    lines.append(f"**Connection mode:** Profile-linked assistant (not live {platform_name} API).")
    if status == "oauth_required":
        lines.append(f"OAuth/API automation requires approval — {docs_url or 'see platform developer docs'}.")
    elif status == "manual_token":
        has_key = bool(str(creds.get("api_key", "")).strip() or str(creds.get("api_token", "")).strip())
        lines.append(f"API key stored: {'yes' if has_key else 'no'}. Live sync pending developer access.")
    elif status == "coming_soon":
        lines.append(f"{platform_name} has no public freelancer API; assistant uses profile + web search.")

    lines.append(f"\n_{API_LIMITATION_NOTE}_")
    return "\n".join(lines)


def freelance_search_jobs(
    platform_id: str,
    platform_name: str,
    creds: Dict[str, Any],
    query: str,
    limit: int = 5,
) -> str:
    ctx = _profile_context(creds, platform_name)
    limit = max(1, min(limit, 8))

    search_terms = query.strip()
    if not search_terms:
        parts = []
        if ctx["niche"]:
            parts.append(ctx["niche"])
        parts.extend(ctx["skills"][:3])
        search_terms = " ".join(parts) or "freelance"

    domain = PLATFORM_DOMAINS.get(platform_id, platform_name.lower().replace(" ", "") + ".com")
    web_query = f"site:{domain} {search_terms} jobs freelance"

    lines = [
        f"## {platform_name} job search (public sources)",
        f"**Query:** {search_terms}",
        f"**Profile match context:** niche={ctx['niche'] or 'any'}, skills={', '.join(ctx['skills'][:5]) or 'not set'}",
        "",
        f"_{API_LIMITATION_NOTE}_",
        "",
    ]

    url_template = PLATFORM_JOB_SEARCH_URLS.get(platform_id)
    if url_template:
        lines.append(f"**Search on {platform_name}:** {url_template.format(query=quote_plus(search_terms))}")
        lines.append("")

    try:
        results, provider = search_web(web_query, limit + 2)
        if results:
            lines.append(f"**Public listings found via {provider}:**")
            lines.append(format_results_for_llm(results, web_query, provider))
        else:
            lines.append("No public listings returned from web search. Try pasting a specific job URL or description.")
    except Exception as exc:
        lines.append(f"Web search unavailable ({exc}). Use the platform search link above or paste job posts directly.")

    lines.append("")
    lines.append(
        "**Next steps:** Pick a listing, paste the job description, and ask me to draft a proposal "
        f"using `{platform_id}_draft_proposal`."
    )
    return "\n".join(lines)


def freelance_draft_proposal(
    platform_id: str,
    platform_name: str,
    creds: Dict[str, Any],
    job_title: str,
    job_description: str,
    tone: str = "professional",
) -> str:
    ctx = _profile_context(creds, platform_name)
    job_text = f"{job_title}\n{job_description}"
    score = _match_score(job_text, ctx["skills"], ctx["niche"])

    skills_line = ", ".join(ctx["skills"][:6]) if ctx["skills"] else "relevant technologies"
    rate_line = f"My rate is {ctx['hourly_rate']}." if ctx["hourly_rate"] else "I'm happy to discuss rate based on scope."
    profile_ref = ctx["profile_url"] or ctx["username"] or f"my {platform_name} profile"

    matched = [s for s in ctx["skills"] if s.lower() in job_description.lower()]
    match_note = f"I noticed you need {', '.join(matched[:4])}." if matched else f"I specialize in {ctx['niche'] or skills_line}."

    opening = (
        f"Hi — I'm interested in \"{job_title.strip() or 'your project'}\". "
        f"{match_note} I'd love to help you ship this on {platform_name}."
    )

    body_points = []
    if job_description.strip():
        reqs = [ln.strip("- •*") for ln in job_description.splitlines() if ln.strip()][:4]
        if reqs:
            body_points.append("Here's how I'd approach your requirements:")
            for r in reqs[:4]:
                body_points.append(f"- {r[:200]}")
        else:
            body_points.append(f"Based on your description, I can deliver quality work using {skills_line}.")
    else:
        body_points.append(f"I bring hands-on experience with {skills_line} and clear communication throughout.")

    closing = (
        f"{rate_line} You can review my work at {profile_ref}. "
        "Would you like to hop on a quick call or chat to align on timeline and milestones?"
    )

    lines = [
        f"## Proposal draft for {platform_name}",
        f"**Tone:** {tone}",
        f"**Profile fit score:** {score}/10 (keyword match — refine with your portfolio details)",
        "",
        "---",
        "",
        opening,
        "",
        "\n".join(body_points),
        "",
        closing,
        "",
        "---",
        "",
        f"_{API_LIMITATION_NOTE} Copy this into {platform_name} and personalize with specific portfolio links._",
    ]
    if ctx["notes"]:
        lines.insert(8, f"\n*Profile notes to weave in:* {ctx['notes']}\n")
    return "\n".join(lines)


def freelance_list_active_gigs(
    platform_id: str,
    platform_name: str,
    creds: Dict[str, Any],
) -> str:
    ctx = _profile_context(creds, platform_name)
    gigs = ctx["active_gigs"]

    lines = [f"## Active gigs on {platform_name} (manually tracked)"]
    if not gigs:
        lines.append(
            "No active gigs saved. Add them in Settings → Integrations → your platform profile "
            "under \"Active gigs\" (one per line, optional status after | e.g. \"React app | in progress\")."
        )
        lines.append(f"\n_{API_LIMITATION_NOTE}_")
        return "\n".join(lines)

    for i, g in enumerate(gigs, 1):
        title = g.get("title", "Untitled")
        status = g.get("status", "active")
        client = g.get("client", "")
        line = f"{i}. **{title}** — {status}"
        if client:
            line += f" (client: {client})"
        lines.append(line)

    lines.append(f"\n_{API_LIMITATION_NOTE} Update this list in your connection settings._")
    return "\n".join(lines)


def freelance_draft_follow_up(
    platform_id: str,
    platform_name: str,
    creds: Dict[str, Any],
    context: str,
    follow_up_type: str = "proposal",
) -> str:
    ctx = _profile_context(creds, platform_name)
    name = ctx["username"] or "there"
    profile_ref = ctx["profile_url"] or f"my {platform_name} profile"

    templates = {
        "proposal": (
            f"Hi — I wanted to follow up on my proposal for the project we discussed. "
            f"I'm still very interested and available to start this week. "
            f"Happy to answer any questions or adjust scope — you can also review {profile_ref}. "
            f"Looking forward to hearing from you!"
        ),
        "interview": (
            f"Hi — thank you for considering my application. "
            f"I remain excited about this opportunity and would welcome a brief chat "
            f"to walk through my approach and timeline. Let me know what time works for you."
        ),
        "project": (
            f"Hi — quick check-in on the project. I've completed the latest milestone and am ready for your feedback. "
            f"Please let me know if you'd like any adjustments before we move to the next phase."
        ),
        "payment": (
            f"Hi — hope you're doing well. When you have a moment, could you please approve the latest milestone "
            f"so we can keep momentum on the project? Happy to share a quick status summary if helpful."
        ),
    }

    body = templates.get(follow_up_type.lower(), templates["proposal"])
    if context.strip():
        body = f"Re: {context.strip()[:120]}\n\n{body}"

    lines = [
        f"## Follow-up draft ({follow_up_type}) for {platform_name}",
        f"**Sign as:** {name}",
        "",
        "---",
        "",
        body,
        "",
        "---",
        "",
        f"_{API_LIMITATION_NOTE} Send this via {platform_name} messaging — Atlas cannot post it for you._",
    ]
    return "\n".join(lines)


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class JobSearchInput(BaseModel):
    query: str = Field(
        default="",
        description="Job search keywords e.g. 'React developer' or 'logo design'. Uses profile skills/niche if empty.",
    )
    limit: int = Field(default=5, description="Max results from public web search (1-8)")


class ProposalInput(BaseModel):
    job_title: str = Field(description="Job or project title")
    job_description: str = Field(description="Full job description or requirements pasted by the user")
    tone: str = Field(default="professional", description="Tone: professional, friendly, or concise")


class FollowUpInput(BaseModel):
    context: str = Field(
        default="",
        description="Brief context e.g. job title, client name, or last message summary",
    )
    follow_up_type: str = Field(
        default="proposal",
        description="Type: proposal, interview, project, or payment",
    )


class ProfileInfoInput(BaseModel):
    query: str = Field(default="", description="Optional question about this freelance connection")


# ── Tool builder ─────────────────────────────────────────────────────────────

def build_freelance_tools(
    platform_id: str,
    platform_name: str,
    status: str,
    docs_url: str,
    creds: Dict[str, Any],
) -> List[StructuredTool]:
    """Actionable profile-linked tools — honest about no live platform API."""

    prefix = platform_id

    def _profile_summary(**kwargs: Any) -> str:
        return freelance_profile_summary(platform_id, platform_name, status, docs_url, creds)

    def _search_jobs(query: str = "", limit: int = 5) -> str:
        return freelance_search_jobs(platform_id, platform_name, creds, query, limit)

    def _draft_proposal(job_title: str, job_description: str, tone: str = "professional") -> str:
        return freelance_draft_proposal(platform_id, platform_name, creds, job_title, job_description, tone)

    def _list_gigs() -> str:
        return freelance_list_active_gigs(platform_id, platform_name, creds)

    def _follow_up(context: str = "", follow_up_type: str = "proposal") -> str:
        return freelance_draft_follow_up(platform_id, platform_name, creds, context, follow_up_type)

    return [
        StructuredTool.from_function(
            func=_profile_summary,
            name=f"{prefix}_profile_summary",
            description=(
                f"Summarize the user's saved {platform_name} profile (skills, rate, niche, active gigs). "
                f"Does NOT fetch live data from {platform_name}."
            ),
            args_schema=ProfileInfoInput,
        ),
        StructuredTool.from_function(
            func=_search_jobs,
            name=f"{prefix}_search_jobs",
            description=(
                f"Search public {platform_name} job listings via web search and platform search links. "
                f"NOT a live authenticated API — results are from public sources. "
                f"Use when user asks to find clients or jobs on {platform_name}."
            ),
            args_schema=JobSearchInput,
        ),
        StructuredTool.from_function(
            func=_draft_proposal,
            name=f"{prefix}_draft_proposal",
            description=(
                f"Draft a tailored {platform_name} proposal from a job title and description "
                f"using the user's saved profile. User must paste/submit the job post — not fetched live."
            ),
            args_schema=ProposalInput,
        ),
        StructuredTool.from_function(
            func=_list_gigs,
            name=f"{prefix}_list_active_gigs",
            description=(
                f"List the user's manually tracked active gigs/projects on {platform_name}. "
                f"Does NOT sync from the platform automatically."
            ),
        ),
        StructuredTool.from_function(
            func=_follow_up,
            name=f"{prefix}_draft_follow_up",
            description=(
                f"Draft a client follow-up message for {platform_name} "
                f"(proposal, interview, project check-in, or payment reminder)."
            ),
            args_schema=FollowUpInput,
        ),
    ]
