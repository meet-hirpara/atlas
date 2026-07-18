"""Tests for freelance platform assistant tools."""

from unittest.mock import patch

from app.integrations.freelance import (
    build_freelance_tools,
    freelance_draft_follow_up,
    freelance_draft_proposal,
    freelance_list_active_gigs,
    freelance_profile_summary,
    freelance_search_jobs,
    validate_freelance_connection,
)
from app.integrations.registry import get_provider
from app.services.tools_service import build_integrations_prompt


SAMPLE_CREDS = {
    "profile_url": "https://www.upwork.com/freelancers/~abc123",
    "username": "jdev",
    "niche": "React full-stack",
    "skills": "React, TypeScript, Node.js",
    "hourly_rate": "$55/hr",
    "active_gigs": "SaaS dashboard | in progress\nLogo pack | delivered",
    "notes": "5+ years experience, US timezone",
}


def test_validate_freelance_connection_message():
    msg = validate_freelance_connection("Upwork", "oauth_required", "https://docs.example.com", SAMPLE_CREDS)
    assert "Upwork profile saved" in msg
    assert "assistant mode" in msg.lower() or "assistant" in msg.lower()


def test_validate_freelance_requires_identifier():
    try:
        validate_freelance_connection("Fiverr", "coming_soon", "", {})
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "profile URL" in str(e) or "username" in str(e)


def test_profile_summary_includes_skills_and_rate():
    out = freelance_profile_summary("upwork", "Upwork", "oauth_required", "", SAMPLE_CREDS)
    assert "React full-stack" in out
    assert "$55/hr" in out
    assert "React, TypeScript, Node.js" in out
    assert "Profile-linked assistant" in out or "profile-linked" in out.lower()


def test_list_active_gigs_parses_lines():
    out = freelance_list_active_gigs("upwork", "Upwork", SAMPLE_CREDS)
    assert "SaaS dashboard" in out
    assert "Logo pack" in out


def test_draft_proposal_uses_profile():
    out = freelance_draft_proposal(
        "upwork",
        "Upwork",
        SAMPLE_CREDS,
        "React Developer Needed",
        "Looking for React and TypeScript expert to build a dashboard.",
    )
    assert "React Developer Needed" in out
    assert "React" in out
    assert "$55/hr" in out
    assert "proposal" in out.lower()


def test_draft_follow_up_types():
    out = freelance_draft_follow_up(
        "fiverr", "Fiverr", SAMPLE_CREDS, "Logo design gig", "project"
    )
    assert "check-in" in out.lower() or "milestone" in out.lower()
    assert "jdev" in out or "Fiverr" in out


def test_build_freelance_tools_count_and_names():
    tools = build_freelance_tools("upwork", "Upwork", "oauth_required", "", SAMPLE_CREDS)
    names = {t.name for t in tools}
    assert names == {
        "upwork_profile_summary",
        "upwork_search_jobs",
        "upwork_draft_proposal",
        "upwork_list_active_gigs",
        "upwork_draft_follow_up",
    }


@patch("app.integrations.freelance.search_web")
def test_search_jobs_includes_platform_link(mock_search):
    mock_search.return_value = ([], "duckduckgo")
    out = freelance_search_jobs("upwork", "Upwork", SAMPLE_CREDS, "React developer", 3)
    assert "upwork.com" in out
    assert "React" in out
    mock_search.assert_called_once()
    call_query = mock_search.call_args[0][0]
    assert "site:upwork.com" in call_query


def test_upwork_provider_has_capabilities():
    p = get_provider("upwork")
    assert p is not None
    assert len(p.capabilities) >= 4
    assert any("proposal" in c.lower() for c in p.capabilities)


def test_integrations_prompt_freelance_mode():
    prompt = build_integrations_prompt(["upwork", "slack"])
    assert "Freelance assistant mode" in prompt
    assert "upwork_search_jobs" in prompt
    assert "upwork_draft_proposal" in prompt
    assert "NEVER claim live API" in prompt
