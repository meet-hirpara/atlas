"""Provider registry — add new integrations here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.integrations import actions as A

ValidateFn = Callable[[Dict[str, Any]], str]
LabelFn = Callable[[Dict[str, Any]], str]
ToolsFn = Callable[[Dict[str, Any]], List[StructuredTool]]


@dataclass
class FieldDef:
    key: str
    label: str
    field_type: str = "text"  # text | password | email | url
    placeholder: str = ""
    required: bool = True
    hint: str = ""
    default: str = ""


@dataclass
class ProviderDef:
    id: str
    name: str
    category: str
    description: str
    color: str
    fields: List[FieldDef]
    validate: ValidateFn
    build_label: LabelFn
    build_tools: ToolsFn
    tool_summary: str = ""
    auth_type: str = "api_key"  # api_key | oauth | manual_token | none
    status: str = "available"  # available | coming_soon | oauth_required | manual_token
    setup_help: str = ""
    docs_url: str = ""
    capabilities: List[str] = field(default_factory=list)


def _mask_secret(value: str, visible: int = 4) -> str:
    if len(value) <= visible:
        return "***"
    return f"{'*' * (len(value) - visible)}{value[-visible:]}"


def _mask_email(email: str) -> str:
    if "@" not in email:
        return _mask_secret(email)
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _require_keys(creds: Dict[str, Any], keys: List[str]) -> None:
    for k in keys:
        if not str(creds.get(k, "")).strip():
            raise ValueError(f"Missing required field: {k}")


# ── Shared Pydantic tool schemas ──────────────────────────────────────────────

class MessageInput(BaseModel):
    message: str = Field(description="Message text to send")
    title: str = Field(default="", description="Optional title for embed-style webhooks")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves sending")


class SlackSendInput(BaseModel):
    channel: str = Field(description="Slack channel e.g. #general")
    message: str = Field(description="Message text")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves sending")


class EmailSendInput(BaseModel):
    to: str = Field(description="Recipient email")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves sending")


class EmailSearchInput(BaseModel):
    query: str = Field(description="Search term for subject or sender")
    limit: int = Field(default=5, description="Max results")


class TelegramSendInput(BaseModel):
    chat_id: str = Field(default="", description="Chat ID (uses default if empty)")
    message: str = Field(description="Message text")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves sending")


class SmsInput(BaseModel):
    to: str = Field(description="Phone number with country code e.g. +15551234567")
    message: str = Field(description="SMS body")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves sending")


class RepoInput(BaseModel):
    repo: str = Field(description="owner/repo e.g. octocat/Hello-World")


class IssueInput(BaseModel):
    repo: str = Field(default="", description="GitHub repo owner/name")
    project_key: str = Field(default="", description="Jira project key")
    project_id: str = Field(default="", description="GitLab project path or ID")
    project_gid: str = Field(default="", description="Asana project GID")
    team_id: str = Field(default="", description="Linear team ID")
    list_id: str = Field(default="", description="Trello list ID")
    title: str = Field(description="Title or summary")
    body: str = Field(default="", description="Description or body")
    description: str = Field(default="", description="Description")
    summary: str = Field(default="", description="Issue summary")
    notes: str = Field(default="", description="Task notes")
    name: str = Field(default="", description="Card or task name")
    desc: str = Field(default="", description="Card description")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves creating")


class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=10, description="Max results")
    jql: str = Field(default="", description="JQL query for Jira")


class NotionPageInput(BaseModel):
    database_id: str = Field(description="Notion database ID")
    title: str = Field(description="Page title")
    content: str = Field(default="", description="Page body text")


class AirtableRecordInput(BaseModel):
    table: str = Field(description="Table name")
    fields_json: str = Field(description='JSON object of fields e.g. {"Name": "Alice"}')
    limit: int = Field(default=10, description="Max records to list")


class SqlInput(BaseModel):
    sql: str = Field(description="SELECT query only")
    limit: int = Field(default=20, description="Row limit")


class MongoInput(BaseModel):
    database: str = Field(description="Database name")
    collection: str = Field(description="Collection name")
    query_json: str = Field(default="{}", description="MongoDB query as JSON")
    limit: int = Field(default=10, description="Max documents")


class WeatherInput(BaseModel):
    city: str = Field(description="City name e.g. London,UK")


class WebhookPayloadInput(BaseModel):
    payload_json: str = Field(default="{}", description="JSON payload to POST")
    confirm: bool = Field(default=False, description="Set true only after the user explicitly approves triggering")


class FolderInput(BaseModel):
    path: str = Field(default="", description="Folder path (empty for root)")


# ── Tool builders ─────────────────────────────────────────────────────────────

def _slack_tools(c: Dict[str, Any]) -> List[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=lambda channel, message, confirm=False: A.slack_send(c, channel, message, confirm=confirm),
            name="slack_send_message",
            description="Send a message to a Slack channel. Requires confirm=true after user approval.",
            args_schema=SlackSendInput,
        ),
        StructuredTool.from_function(
            func=lambda: A.slack_list_channels(c),
            name="slack_list_channels",
            description="List Slack channels the bot can access.",
        ),
    ]


def _mail_tools(provider: str, label: str, c: Dict[str, Any]) -> List[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=lambda to, subject, body, confirm=False, p=provider, cr=c: A.mail_send(p, cr, to, subject, body, confirm=confirm),
            name=f"{provider}_send_email",
            description=f"Send email via {label}. Requires confirm=true after user approval.",
            args_schema=EmailSendInput,
        ),
        StructuredTool.from_function(
            func=lambda query, limit=5, p=provider, cr=c: A.mail_search(p, cr, query, limit),
            name=f"{provider}_search_email",
            description=f"Search {label} inbox by subject or sender.",
            args_schema=EmailSearchInput,
        ),
    ]


def _webhook_tools(provider: str, c: Dict[str, Any]) -> List[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=lambda message, title="", confirm=False, cr=c: A.webhook_send(cr, message, title, confirm=confirm),
            name=f"{provider}_send_message",
            description=f"Send a message via {provider} webhook. Requires confirm=true after user approval.",
            args_schema=MessageInput,
        ),
    ]


# ── Provider list ─────────────────────────────────────────────────────────────

PROVIDERS: Dict[str, ProviderDef] = {}


def _register(p: ProviderDef) -> None:
    PROVIDERS[p.id] = p


# Messaging
_register(ProviderDef(
    id="slack", name="Slack", category="messaging",
    description="Send messages and list channels",
    color="#E01E5A",
    fields=[
        FieldDef("bot_token", "Bot token", "password", "xoxb-…", hint="api.slack.com → OAuth → Bot Token Scopes: chat:write, channels:read"),
        FieldDef("default_channel", "Default channel", "text", "#general", required=False, default="#general"),
    ],
    validate=lambda c: (_require_keys(c, ["bot_token"]), A.test_slack(c))[1],
    build_label=lambda c: "Slack",
    build_tools=_slack_tools,
    tool_summary="Slack messaging",
))

_register(ProviderDef(
    id="discord", name="Discord", category="messaging",
    description="Send messages via Discord webhook",
    color="#5865F2",
    fields=[FieldDef("webhook_url", "Webhook URL", "url", "https://discord.com/api/webhooks/…")],
    validate=lambda c: (_require_keys(c, ["webhook_url"]), A.test_webhook(c))[1],
    build_label=lambda c: "Discord webhook",
    build_tools=lambda c: _webhook_tools("discord", c),
    tool_summary="Discord webhook",
))

_register(ProviderDef(
    id="telegram", name="Telegram", category="messaging",
    description="Send messages via Telegram bot. Tip: create a bot with @BotFather, then paste the token here. Deep link: https://t.me/BotFather",
    color="#26A5E4",
    fields=[
        FieldDef("bot_token", "Bot token", "password", "From @BotFather"),
        FieldDef("default_chat_id", "Default chat ID", "text", "e.g. -1001234567890", required=False),
    ],
    validate=lambda c: (_require_keys(c, ["bot_token"]), A.test_telegram(c))[1],
    build_label=lambda c: "Telegram",
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda chat_id, message, confirm=False, cr=c: A.telegram_send(cr, chat_id, message, confirm=confirm),
            name="telegram_send_message",
            description="Send a Telegram message.",
            args_schema=TelegramSendInput,
        ),
    ],
    tool_summary="Telegram bot",
    setup_help="1) Message @BotFather on Telegram → /newbot. 2) Copy the token. 3) Start a chat with your bot and get your chat ID (e.g. via @userinfobot). Deep link: https://t.me/BotFather",
    docs_url="https://core.telegram.org/bots",
))

_register(ProviderDef(
    id="whatsapp", name="WhatsApp", category="messaging",
    description="WhatsApp Business API — coming soon. For messaging today, use Telegram.",
    color="#25D366",
    status="coming_soon",
    fields=[],
    validate=lambda c: "Coming soon",
    build_label=lambda c: "WhatsApp",
    build_tools=lambda c: [],
    tool_summary="WhatsApp (coming soon)",
    setup_help="WhatsApp Business Cloud API is not wired yet. Use Telegram for chat alerts, or check back later.",
    docs_url="https://developers.facebook.com/docs/whatsapp",
))

_register(ProviderDef(
    id="teams", name="Microsoft Teams", category="messaging",
    description="Send messages via Teams incoming webhook",
    color="#6264A7",
    fields=[FieldDef("webhook_url", "Incoming webhook URL", "url")],
    validate=lambda c: (_require_keys(c, ["webhook_url"]), A.test_webhook(c))[1],
    build_label=lambda c: "Microsoft Teams",
    build_tools=lambda c: _webhook_tools("teams", c),
    tool_summary="Teams webhook",
))

_register(ProviderDef(
    id="mattermost", name="Mattermost", category="messaging",
    description="Send messages via Mattermost webhook",
    color="#0058CC",
    fields=[FieldDef("webhook_url", "Webhook URL", "url")],
    validate=lambda c: (_require_keys(c, ["webhook_url"]), A.test_webhook(c))[1],
    build_label=lambda c: "Mattermost",
    build_tools=lambda c: _webhook_tools("mattermost", c),
    tool_summary="Mattermost webhook",
))

# Email
for _pid, _pname in [("gmail", "Gmail"), ("outlook", "Outlook")]:
    _register(ProviderDef(
        id=_pid, name=_pname, category="email",
        description=f"Send and search {_pname} mail",
        color="#EA4335" if _pid == "gmail" else "#0078D4",
        fields=[
            FieldDef("email", "Email address", "email"),
            FieldDef("app_password", "App password", "password", hint="Use an app-specific password, not your login password"),
        ],
        validate=lambda c, p=_pid: (_require_keys(c, ["email", "app_password"]), A.test_mail(p, c))[1],
        build_label=lambda c: _mask_email(c["email"]),
        build_tools=lambda c, p=_pid, n=_pname: _mail_tools(p, n, c),
        tool_summary=f"{_pname} email",
    ))

_register(ProviderDef(
    id="smtp", name="Custom SMTP", category="email",
    description="Send email via any SMTP server",
    color="#6B7280",
    fields=[
        FieldDef("smtp_host", "SMTP host", "text", "smtp.example.com"),
        FieldDef("smtp_port", "SMTP port", "text", "587", default="587"),
        FieldDef("username", "Username", "text"),
        FieldDef("password", "Password", "password"),
        FieldDef("from_email", "From email", "email", required=False),
        FieldDef("use_tls", "Use TLS", "text", "true", required=False, default="true"),
    ],
    validate=lambda c: (_require_keys(c, ["smtp_host", "smtp_port", "username", "password"]), A.test_smtp(c))[1],
    build_label=lambda c: _mask_email(c.get("from_email") or c["username"]),
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda to, subject, body, confirm=False, cr=c: A.smtp_send(cr, to, subject, body, confirm=confirm),
            name="smtp_send_email",
            description="Send email via custom SMTP.",
            args_schema=EmailSendInput,
        ),
    ],
    tool_summary="SMTP email",
))

_register(ProviderDef(
    id="sendgrid", name="SendGrid", category="email",
    description="Transactional email via SendGrid API",
    color="#1A82E2",
    fields=[
        FieldDef("api_key", "API key", "password"),
        FieldDef("from_email", "From email", "email"),
    ],
    validate=lambda c: (_require_keys(c, ["api_key", "from_email"]), A.test_sendgrid(c))[1],
    build_label=lambda c: _mask_email(c["from_email"]),
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda to, subject, body, confirm=False, cr=c: A.sendgrid_send(cr, to, subject, body, confirm=confirm),
            name="sendgrid_send_email",
            description="Send email via SendGrid.",
            args_schema=EmailSendInput,
        ),
    ],
    tool_summary="SendGrid email",
))

_register(ProviderDef(
    id="twilio", name="Twilio", category="messaging",
    description="Send SMS messages",
    color="#F22F46",
    fields=[
        FieldDef("account_sid", "Account SID", "text"),
        FieldDef("auth_token", "Auth token", "password"),
        FieldDef("from_number", "From number", "text", "+15551234567"),
    ],
    validate=lambda c: (_require_keys(c, ["account_sid", "auth_token", "from_number"]), A.test_twilio(c))[1],
    build_label=lambda c: c["from_number"],
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda to, message, confirm=False, cr=c: A.twilio_send_sms(cr, to, message, confirm=confirm),
            name="twilio_send_sms",
            description="Send an SMS via Twilio.",
            args_schema=SmsInput,
        ),
    ],
    tool_summary="Twilio SMS",
))

# Developer
_register(ProviderDef(
    id="github", name="GitHub", category="developer",
    description="Repos, issues, and code search",
    color="#24292F",
    fields=[FieldDef("token", "Personal access token", "password", hint="github.com/settings/tokens")],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_github(c))[1],
    build_label=lambda c: _mask_secret(c["token"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda limit=10, cr=c: A.github_list_repos(cr, limit), name="github_list_repos", description="List GitHub repositories."),
        StructuredTool.from_function(func=lambda repo, title, body="", confirm=False, cr=c: A.github_create_issue(cr, repo, title, body, confirm=confirm), name="github_create_issue", description="Create a GitHub issue. Requires confirm=true after user approval.", args_schema=IssueInput),
        StructuredTool.from_function(func=lambda query, limit=5, cr=c: A.github_search_code(cr, query, limit), name="github_search_code", description="Search code on GitHub.", args_schema=SearchInput),
    ],
    tool_summary="GitHub",
))

_register(ProviderDef(
    id="gitlab", name="GitLab", category="developer",
    description="Projects and issues on GitLab",
    color="#FC6D26",
    fields=[
        FieldDef("token", "Personal access token", "password"),
        FieldDef("base_url", "GitLab URL", "url", "https://gitlab.com", required=False, default="https://gitlab.com"),
    ],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_gitlab(c))[1],
    build_label=lambda c: _mask_secret(c["token"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda limit=10, cr=c: A.gitlab_list_projects(cr, limit), name="gitlab_list_projects", description="List GitLab projects."),
        StructuredTool.from_function(func=lambda project_id, title, description="", cr=c: A.gitlab_create_issue(cr, project_id, title, description), name="gitlab_create_issue", description="Create a GitLab issue.", args_schema=IssueInput),
    ],
    tool_summary="GitLab",
))

_register(ProviderDef(
    id="jira", name="Jira", category="developer",
    description="Search and create Jira issues",
    color="#0052CC",
    fields=[
        FieldDef("base_url", "Jira site URL", "url", "https://yourorg.atlassian.net"),
        FieldDef("email", "Account email", "email"),
        FieldDef("api_token", "API token", "password", hint="id.atlassian.com → Security → API tokens"),
    ],
    validate=lambda c: (_require_keys(c, ["base_url", "email", "api_token"]), A.test_jira(c))[1],
    build_label=lambda c: _mask_email(c["email"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda jql, limit=10, cr=c: A.jira_search(cr, jql or "order by created DESC", limit), name="jira_search_issues", description="Search Jira issues with JQL.", args_schema=SearchInput),
        StructuredTool.from_function(func=lambda project_key, summary, description="", cr=c: A.jira_create_issue(cr, project_key, summary, description), name="jira_create_issue", description="Create a Jira issue.", args_schema=IssueInput),
    ],
    tool_summary="Jira",
))

_register(ProviderDef(
    id="linear", name="Linear", category="developer",
    description="Issue tracking with Linear",
    color="#5E6AD2",
    fields=[
        FieldDef("api_key", "API key", "password"),
        FieldDef("default_team_id", "Default team ID", "text", required=False),
    ],
    validate=lambda c: (_require_keys(c, ["api_key"]), A.test_linear(c))[1],
    build_label=lambda c: _mask_secret(c["api_key"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda query, limit=10, cr=c: A.linear_search_issues(cr, query, limit), name="linear_search_issues", description="Search Linear issues.", args_schema=SearchInput),
        StructuredTool.from_function(
            func=lambda team_id, title, description="", cr=c: A.linear_create_issue(cr, team_id or cr.get("default_team_id", ""), title, description),
            name="linear_create_issue", description="Create a Linear issue.", args_schema=IssueInput,
        ),
    ],
    tool_summary="Linear",
))

# Productivity
_register(ProviderDef(
    id="notion", name="Notion", category="productivity",
    description="Search and create Notion pages",
    color="#000000",
    fields=[FieldDef("token", "Integration token", "password", hint="notion.so/my-integrations")],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_notion(c))[1],
    build_label=lambda c: "Notion",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda query, limit=10, cr=c: A.notion_search(cr, query, limit), name="notion_search", description="Search Notion workspace.", args_schema=SearchInput),
        StructuredTool.from_function(func=lambda database_id, title, content="", cr=c: A.notion_create_page(cr, database_id, title, content), name="notion_create_page", description="Create a Notion page in a database.", args_schema=NotionPageInput),
    ],
    tool_summary="Notion",
))

_register(ProviderDef(
    id="confluence", name="Confluence", category="productivity",
    description="Search Confluence pages",
    color="#172B4D",
    fields=[
        FieldDef("base_url", "Confluence URL", "url", "https://yourorg.atlassian.net"),
        FieldDef("email", "Account email", "email"),
        FieldDef("api_token", "API token", "password"),
    ],
    validate=lambda c: (_require_keys(c, ["base_url", "email", "api_token"]), A.test_confluence(c))[1],
    build_label=lambda c: _mask_email(c["email"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda query, limit=10, cr=c: A.confluence_search(cr, query, limit), name="confluence_search", description="Search Confluence pages.", args_schema=SearchInput),
    ],
    tool_summary="Confluence",
))

_register(ProviderDef(
    id="trello", name="Trello", category="productivity",
    description="Boards and cards on Trello",
    color="#0079BF",
    fields=[
        FieldDef("api_key", "API key", "text"),
        FieldDef("token", "Token", "password"),
    ],
    validate=lambda c: (_require_keys(c, ["api_key", "token"]), A.test_trello(c))[1],
    build_label=lambda c: "Trello",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda cr=c: A.trello_list_boards(cr), name="trello_list_boards", description="List Trello boards."),
        StructuredTool.from_function(func=lambda list_id, name, desc="", cr=c: A.trello_create_card(cr, list_id, name, desc), name="trello_create_card", description="Create a Trello card.", args_schema=IssueInput),
    ],
    tool_summary="Trello",
))

_register(ProviderDef(
    id="asana", name="Asana", category="productivity",
    description="Tasks and projects in Asana",
    color="#F06A6A",
    fields=[FieldDef("token", "Personal access token", "password")],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_asana(c))[1],
    build_label=lambda c: "Asana",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda project_gid, limit=10, cr=c: A.asana_list_tasks(cr, project_gid, limit), name="asana_list_tasks", description="List tasks in an Asana project.", args_schema=IssueInput),
        StructuredTool.from_function(func=lambda project_gid, name, notes="", cr=c: A.asana_create_task(cr, project_gid, name, notes), name="asana_create_task", description="Create an Asana task.", args_schema=IssueInput),
    ],
    tool_summary="Asana",
))

_register(ProviderDef(
    id="airtable", name="Airtable", category="productivity",
    description="Read and write Airtable records",
    color="#18BFFF",
    fields=[
        FieldDef("token", "Personal access token", "password"),
        FieldDef("base_id", "Base ID", "text", "appXXXXXXXXXXXXXX"),
    ],
    validate=lambda c: (_require_keys(c, ["token", "base_id"]), A.test_airtable(c))[1],
    build_label=lambda c: c["base_id"][:8] + "…",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda table, limit=10, cr=c: A.airtable_list_records(cr, table, limit), name="airtable_list_records", description="List records from an Airtable table.", args_schema=AirtableRecordInput),
        StructuredTool.from_function(func=lambda table, fields_json, cr=c: A.airtable_create_record(cr, table, fields_json), name="airtable_create_record", description="Create an Airtable record.", args_schema=AirtableRecordInput),
    ],
    tool_summary="Airtable",
))

# CRM & marketing
_register(ProviderDef(
    id="hubspot", name="HubSpot", category="crm",
    description="Search CRM contacts",
    color="#FF7A59",
    fields=[FieldDef("token", "Private app access token", "password")],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_hubspot(c))[1],
    build_label=lambda c: "HubSpot",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda query, limit=10, cr=c: A.hubspot_search_contacts(cr, query, limit), name="hubspot_search_contacts", description="Search HubSpot contacts.", args_schema=SearchInput),
    ],
    tool_summary="HubSpot CRM",
))

_register(ProviderDef(
    id="mailchimp", name="Mailchimp", category="crm",
    description="Email marketing audiences",
    color="#FFE01B",
    fields=[FieldDef("api_key", "API key", "password", hint="Includes datacenter suffix e.g. …-us21")],
    validate=lambda c: (_require_keys(c, ["api_key"]), A.test_mailchimp(c))[1],
    build_label=lambda c: _mask_secret(c["api_key"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda limit=10, cr=c: A.mailchimp_list_audiences(cr, limit), name="mailchimp_list_audiences", description="List Mailchimp audiences."),
    ],
    tool_summary="Mailchimp",
))

# Payments
_register(ProviderDef(
    id="stripe", name="Stripe", category="payments",
    description="List customers and payment data",
    color="#635BFF",
    fields=[FieldDef("secret_key", "Secret key", "password", "sk_live_… or sk_test_…")],
    validate=lambda c: (_require_keys(c, ["secret_key"]), A.test_stripe(c))[1],
    build_label=lambda c: _mask_secret(c["secret_key"]),
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda limit=10, cr=c: A.stripe_list_customers(cr, limit), name="stripe_list_customers", description="List Stripe customers."),
    ],
    tool_summary="Stripe",
))

# Storage & files
_register(ProviderDef(
    id="dropbox", name="Dropbox", category="storage",
    description="Browse Dropbox folders",
    color="#0061FF",
    fields=[FieldDef("token", "Access token", "password")],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_dropbox(c))[1],
    build_label=lambda c: "Dropbox",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda path="", cr=c: A.dropbox_list_folder(cr, path), name="dropbox_list_folder", description="List files in a Dropbox folder.", args_schema=FolderInput),
    ],
    tool_summary="Dropbox",
))

# Calendar
_register(ProviderDef(
    id="calendly", name="Calendly", category="calendar",
    description="View scheduled Calendly events",
    color="#006BFF",
    fields=[FieldDef("token", "Personal access token", "password")],
    validate=lambda c: (_require_keys(c, ["token"]), A.test_calendly(c))[1],
    build_label=lambda c: "Calendly",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda limit=10, cr=c: A.calendly_list_events(cr, limit), name="calendly_list_events", description="List upcoming Calendly events."),
    ],
    tool_summary="Calendly",
))

# Data
_register(ProviderDef(
    id="postgres", name="PostgreSQL", category="data",
    description="Run read-only SQL queries",
    color="#336791",
    fields=[FieldDef("connection_string", "Connection string", "password", "postgresql://user:pass@host:5432/db")],
    validate=lambda c: (_require_keys(c, ["connection_string"]), A.test_postgres(c))[1],
    build_label=lambda c: "PostgreSQL",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda sql, limit=20, cr=c: A.postgres_query(cr, sql, limit), name="postgres_query", description="Run a read-only SELECT query on PostgreSQL.", args_schema=SqlInput),
    ],
    tool_summary="PostgreSQL",
))

_register(ProviderDef(
    id="mongodb", name="MongoDB", category="data",
    description="Query MongoDB collections",
    color="#47A248",
    fields=[FieldDef("connection_string", "Connection URI", "password", "mongodb+srv://…")],
    validate=lambda c: (_require_keys(c, ["connection_string"]), A.test_mongodb(c))[1],
    build_label=lambda c: "MongoDB",
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda database, collection, query_json="{}", limit=10, cr=c: A.mongodb_find(cr, database, collection, query_json, limit),
            name="mongodb_find", description="Find documents in a MongoDB collection.", args_schema=MongoInput,
        ),
    ],
    tool_summary="MongoDB",
))

# Utilities & automation
_register(ProviderDef(
    id="openweather", name="OpenWeather", category="utilities",
    description="Current weather for any city",
    color="#EB6E4B",
    fields=[FieldDef("api_key", "API key", "password")],
    validate=lambda c: (_require_keys(c, ["api_key"]), A.test_openweather(c))[1],
    build_label=lambda c: "OpenWeather",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda city, cr=c: A.openweather_get(cr, city), name="openweather_get_weather", description="Get current weather for a city.", args_schema=WeatherInput),
    ],
    tool_summary="OpenWeather",
))

_register(ProviderDef(
    id="newsapi", name="NewsAPI", category="utilities",
    description="Search latest news articles",
    color="#1A1A1A",
    fields=[FieldDef("api_key", "API key", "password")],
    validate=lambda c: (_require_keys(c, ["api_key"]), A.test_newsapi(c))[1],
    build_label=lambda c: "NewsAPI",
    build_tools=lambda c: [
        StructuredTool.from_function(func=lambda query, limit=5, cr=c: A.newsapi_search(cr, query, limit), name="newsapi_search", description="Search news articles.", args_schema=SearchInput),
    ],
    tool_summary="NewsAPI",
))

_register(ProviderDef(
    id="webhook", name="Custom Webhook", category="automation",
    description="POST JSON to any HTTP webhook",
    color="#8B5CF6",
    fields=[FieldDef("webhook_url", "Webhook URL", "url")],
    validate=lambda c: (_require_keys(c, ["webhook_url"]), A.test_webhook(c))[1],
    build_label=lambda c: "Webhook",
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda message, title="", confirm=False, cr=c: A.webhook_send(cr, message, title, confirm=confirm),
            name="webhook_send",
            description="Send a message to a custom webhook URL.",
            args_schema=MessageInput,
        ),
        StructuredTool.from_function(
            func=lambda payload_json, confirm=False, cr=c: A.zapier_send(cr, payload_json, confirm=confirm),
            name="webhook_send_json",
            description="POST raw JSON payload to webhook.",
            args_schema=WebhookPayloadInput,
        ),
    ],
    tool_summary="Custom webhook",
))

_register(ProviderDef(
    id="zapier", name="Zapier", category="automation",
    description="Trigger Zapier Zaps via catch hook",
    color="#FF4A00",
    fields=[FieldDef("webhook_url", "Catch hook URL", "url", "hooks.zapier.com/hooks/catch/…")],
    validate=lambda c: (_require_keys(c, ["webhook_url"]), A.test_webhook(c))[1],
    build_label=lambda c: "Zapier",
    build_tools=lambda c: [
        StructuredTool.from_function(
            func=lambda payload_json="{}", confirm=False, cr=c: A.zapier_send(cr, payload_json, confirm=confirm),
            name="zapier_trigger",
            description="Trigger a Zapier Zap with a JSON payload.",
            args_schema=WebhookPayloadInput,
        ),
    ],
    tool_summary="Zapier",
))

# Freelance platforms (profile-linked assistant — no fake live API)
from app.integrations import freelance as F

_FREELANCE_CAPS = F.get_freelance_capabilities()

_PROFILE = [
    FieldDef("profile_url", "Profile URL", "url", placeholder="https://…", required=False,
             hint="Your public freelancer profile link on the platform"),
    FieldDef("username", "Username / handle", "text", placeholder="your-handle", required=False,
             hint="Platform username if you do not have a profile URL handy"),
    FieldDef("niche", "Niche / specialty", "text", placeholder="e.g. React full-stack, logo design", required=False,
             hint="Primary focus area — used for job matching and proposals"),
    FieldDef("skills", "Skills", "text", placeholder="React, TypeScript, Node.js", required=False,
             hint="Comma-separated skills for job search and proposal tailoring"),
    FieldDef("hourly_rate", "Hourly rate", "text", placeholder="e.g. $45/hr or €40/hr", required=False,
             hint="Included in proposal drafts"),
    FieldDef("active_gigs", "Active gigs", "text", placeholder="Project A | in progress", required=False,
             hint="One per line — optional status after | e.g. \"Logo redesign | awaiting feedback\""),
]
_NOTES = FieldDef("notes", "Notes (optional)", "text", placeholder="Portfolio highlights, availability", required=False)


def _freelance(
    id: str, name: str, description: str, color: str, status: str, auth_type: str,
    fields: List[FieldDef], setup_help: str, docs_url: str, tool_summary: str,
) -> ProviderDef:
    return ProviderDef(
        id=id, name=name, category="freelance", description=description, color=color, fields=fields,
        validate=lambda c, n=name, s=status, d=docs_url: F.validate_freelance_connection(n, s, d, c),
        build_label=lambda c, n=name: F.build_freelance_label(c, n),
        build_tools=lambda c, pid=id, pn=name, st=status, doc=docs_url: F.build_freelance_tools(pid, pn, st, doc, c),
        tool_summary=tool_summary, auth_type=auth_type, status=status, setup_help=setup_help, docs_url=docs_url,
        capabilities=_FREELANCE_CAPS,
    )


_register(_freelance(
    "upwork", "Upwork", "Freelance assistant for Upwork — job search, proposals, follow-ups", "#14A800",
    "available", "none",
    _PROFILE + [
        _NOTES,
    ],
    "Save your Upwork profile to enable job search (public web), proposal drafts, and follow-ups. "
    "This is NOT the live Upwork API — for GraphQL jobs/proposals/contracts, connect Upwork under Settings → MCP.",
    "https://www.upwork.com/developer/documentation/graphql/api/docs/index.html",
    "Upwork assistant: search, proposals, follow-ups",
))

_register(_freelance(
    "fiverr", "Fiverr", "Freelance assistant for Fiverr — gigs, proposals, client messages", "#1DBF73",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your Fiverr seller profile for proposal drafts and gig tracking. "
    "No public Fiverr API — assistant uses your profile + public job search.",
    "https://www.fiverr.com/legal/terms", "Fiverr assistant: proposals, gig tracking",
))

_register(_freelance(
    "freelancer", "Freelancer.com", "Freelance assistant for Freelancer.com", "#29B2FE",
    "manual_token", "api_key",
    _PROFILE + [
        FieldDef("api_key", "API key", "password", required=False,
                 hint="From freelancer.com/users/settings/developer — requires developer approval"),
        _NOTES,
    ],
    "Save your profile for job search, bidding drafts, and follow-ups. "
    "Live API bidding requires approved developer access.",
    "https://developers.freelancer.com/", "Freelancer assistant: search, proposals",
))

_register(_freelance(
    "toptal", "Toptal", "Freelance assistant for Toptal talent", "#204ECF",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your Toptal profile for proposal drafts and project tracking. "
    "Toptal has no public API — assistant mode uses your saved profile.",
    "https://www.toptal.com/", "Toptal assistant: proposals, tracking",
))

_register(_freelance(
    "peopleperhour", "PeoplePerHour", "Freelance assistant for PeoplePerHour", "#E8618C",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your profile for job search and proposal drafts on PeoplePerHour.",
    "https://www.peopleperhour.com/", "PPH assistant: search, proposals",
))

_register(_freelance(
    "guru", "Guru", "Freelance assistant for Guru.com", "#FF6B35",
    "manual_token", "api_key",
    _PROFILE + [
        FieldDef("api_key", "API token", "password", required=False,
                 hint="Contact Guru support for API/partner access if available to your account"),
        _NOTES,
    ],
    "Save your Guru profile for job search, proposal drafts, and follow-ups.",
    "https://www.guru.com/", "Guru assistant: search, proposals",
))

_register(_freelance(
    "malt", "Malt", "Freelance assistant for Malt", "#000000",
    "oauth_required", "oauth",
    _PROFILE + [
        FieldDef("api_token", "Partner API token", "password", required=False,
                 hint="Only for approved Malt business/partner integrations"),
        _NOTES,
    ],
    "Save your Malt profile for proposal drafts and project tracking.",
    "https://www.malt.com/developers", "Malt assistant: proposals, tracking",
))

_register(_freelance(
    "contra", "Contra", "Freelance assistant for Contra", "#6366F1",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your Contra profile for opportunity search and proposal drafts.",
    "https://contra.com/", "Contra assistant: search, proposals",
))

_register(_freelance(
    "99designs", "99designs", "Freelance assistant for 99designs designers", "#FF6B00",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your 99designs designer profile for contest briefs and client proposal drafts. "
    "No public API — assistant uses your profile + public contest search.",
    "https://99designs.com/", "99designs assistant: contests, proposals",
))

_register(_freelance(
    "designcrowd", "DesignCrowd", "Freelance assistant for DesignCrowd", "#00AEEF",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your DesignCrowd profile for design job search and proposal drafts.",
    "https://www.designcrowd.com/", "DesignCrowd assistant: search, proposals",
))

_register(_freelance(
    "workana", "Workana", "Freelance assistant for Workana (LATAM)", "#6C63FF",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your Workana profile for project search and proposal drafts across Latin America.",
    "https://www.workana.com/", "Workana assistant: search, proposals",
))

_register(_freelance(
    "truelancer", "Truelancer", "Freelance assistant for Truelancer", "#2D9CDB",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your Truelancer profile for job search and bidding drafts.",
    "https://www.truelancer.com/", "Truelancer assistant: search, proposals",
))

_register(_freelance(
    "bark", "Bark", "Freelance assistant for Bark leads", "#00B67A",
    "coming_soon", "none", _PROFILE + [_NOTES],
    "Save your Bark professional profile for lead follow-ups and proposal drafts.",
    "https://www.bark.com/", "Bark assistant: leads, proposals",
))


PROVIDER_IDS = tuple(PROVIDERS.keys())
CATEGORY_LABELS = {
    "messaging": "Messaging & chat",
    "email": "Email",
    "developer": "Developer tools",
    "productivity": "Productivity",
    "crm": "CRM & marketing",
    "payments": "Payments",
    "storage": "Storage & files",
    "calendar": "Calendar",
    "data": "Databases",
    "utilities": "Utilities & APIs",
    "automation": "Automation & webhooks",
    "freelance": "Freelance platforms",
}
CATEGORY_ORDER = [
    "messaging", "email", "developer", "productivity", "crm",
    "payments", "storage", "calendar", "data", "utilities", "automation", "freelance",
]


def get_provider(provider_id: str) -> Optional[ProviderDef]:
    return PROVIDERS.get(provider_id)


def list_provider_catalog() -> List[dict]:
    items = []
    for pid in sorted(PROVIDERS.keys(), key=lambda x: (CATEGORY_ORDER.index(PROVIDERS[x].category) if PROVIDERS[x].category in CATEGORY_ORDER else 99, PROVIDERS[x].name)):
        p = PROVIDERS[pid]
        items.append({
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "category_label": CATEGORY_LABELS.get(p.category, p.category),
            "description": p.description,
            "color": p.color,
            "tool_summary": p.tool_summary,
            "fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "type": f.field_type,
                    "placeholder": f.placeholder,
                    "required": f.required,
                    "hint": f.hint,
                    "default": f.default,
                }
                for f in p.fields
            ],
            "auth_type": p.auth_type,
            "status": p.status,
            "setup_help": p.setup_help,
            "docs_url": p.docs_url,
            "capabilities": p.capabilities,
        })
    return items


def normalize_credentials(provider_id: str, raw: Dict[str, Any]) -> Dict[str, str]:
    p = get_provider(provider_id)
    if not p:
        raise ValueError(f"Unknown provider: {provider_id}")
    creds: Dict[str, str] = {}
    for f in p.fields:
        val = raw.get(f.key, raw.get(_camel(f.key), f.default))
        if f.required and not str(val or "").strip():
            raise ValueError(f"Missing required field: {f.label}")
        creds[f.key] = str(val or "").strip()
    return creds


def _camel(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])
