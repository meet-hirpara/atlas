"""Integration actions — one module per provider family."""

from __future__ import annotations

import base64
import json
import logging
import re
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.integrations.http_util import api_request

logger = logging.getLogger(__name__)


def require_confirm(confirm: bool, action: str) -> Optional[str]:
    """Gate destructive side-effects until the model passes confirm=true."""
    if confirm:
        return None
    return (
        f"Confirmation required before {action}. "
        "Ask the user to approve, then call again with confirm=true."
    )

# ── Slack ─────────────────────────────────────────────────────────────────────

def test_slack(creds: Dict[str, Any]) -> str:
    client = WebClient(token=creds["bot_token"])
    auth = client.auth_test()
    return f"Connected as {auth['user']} in {auth.get('team', 'workspace')}"


def slack_send(creds: Dict[str, Any], channel: str, text: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "sending a Slack message")
    if blocked:
        return blocked
    client = WebClient(token=creds["bot_token"])
    ch = channel if channel.startswith("#") else f"#{channel.lstrip('#')}"
    if creds.get("default_channel") and channel.lower() in ("default", "general"):
        ch = creds["default_channel"]
    try:
        resp = client.chat_postMessage(channel=ch, text=text)
        logger.info("Slack message sent to %s", ch)
        return f"Message sent to {ch} (ts: {resp['ts']})"
    except SlackApiError as e:
        logger.warning("Slack send failed: %s", e.response.get("error"))
        return f"Slack error: {e.response['error']}"


def slack_list_channels(creds: Dict[str, Any], limit: int = 15) -> str:
    client = WebClient(token=creds["bot_token"])
    try:
        resp = client.conversations_list(types="public_channel,private_channel", limit=limit)
        channels = [f"#{c['name']}" for c in resp.get("channels", [])]
        return "Channels: " + ", ".join(channels) if channels else "No channels found."
    except SlackApiError as e:
        return f"Slack error: {e.response['error']}"


# ── Mail (Gmail / Outlook / SMTP) ─────────────────────────────────────────────

MAIL_SERVERS = {
    "gmail": {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "imap_host": "imap.gmail.com", "imap_port": 993},
    "outlook": {"smtp_host": "smtp-mail.outlook.com", "smtp_port": 587, "imap_host": "outlook.office365.com", "imap_port": 993},
}


def test_mail(provider: str, creds: Dict[str, Any]) -> str:
    cfg = MAIL_SERVERS[provider]
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as smtp:
        smtp.starttls()
        smtp.login(creds["email"], creds["app_password"])
    return f"Mail connected for {creds['email']}"


def test_smtp(creds: Dict[str, Any]) -> str:
    with smtplib.SMTP(creds["smtp_host"], int(creds["smtp_port"]), timeout=15) as smtp:
        if creds.get("use_tls", "true").lower() != "false":
            smtp.starttls()
        smtp.login(creds["username"], creds["password"])
    return f"SMTP connected for {creds['username']}"


def mail_send(provider: str, creds: Dict[str, Any], to: str, subject: str, body: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, f"sending email via {provider}")
    if blocked:
        return blocked
    cfg = MAIL_SERVERS[provider]
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = creds["email"]
    msg["To"] = to
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=20) as smtp:
        smtp.starttls()
        smtp.login(creds["email"], creds["app_password"])
        smtp.send_message(msg)
    logger.info("Mail sent via %s to %s", provider, to)
    return f"Email sent to {to}"


def smtp_send(creds: Dict[str, Any], to: str, subject: str, body: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "sending email via SMTP")
    if blocked:
        return blocked
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = creds.get("from_email") or creds["username"]
    msg["To"] = to
    with smtplib.SMTP(creds["smtp_host"], int(creds["smtp_port"]), timeout=20) as smtp:
        if creds.get("use_tls", "true").lower() != "false":
            smtp.starttls()
        smtp.login(creds["username"], creds["password"])
        smtp.send_message(msg)
    logger.info("SMTP mail sent to %s", to)
    return f"Email sent to {to}"


def mail_search(provider: str, creds: Dict[str, Any], query: str, limit: int = 5) -> str:
    import email as email_lib
    import imaplib

    cfg = MAIL_SERVERS[provider]
    imap = imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"])
    try:
        imap.login(creds["email"], creds["app_password"])
        imap.select("INBOX")
        _, data = imap.search(None, "ALL")
        ids = data[0].split()[-50:]
        results: List[str] = []
        q = query.lower()
        for mid in reversed(ids):
            _, msg_data = imap.fetch(mid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)
            subject = msg.get("Subject", "")
            sender = msg.get("From", "")
            if q in subject.lower() or q in sender.lower() or not q:
                results.append(f"From: {sender} | Subject: {subject}")
            if len(results) >= limit:
                break
        return "\n".join(results) if results else "No matching emails found."
    finally:
        imap.logout()


# ── Discord / Teams / Mattermost (webhooks) ───────────────────────────────────

def test_webhook(creds: Dict[str, Any]) -> str:
    url = creds["webhook_url"].strip()
    if not url.startswith("http"):
        raise ValueError("Invalid webhook URL")
    return "Webhook URL validated"


def webhook_send(creds: Dict[str, Any], message: str, title: str = "", confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "sending a webhook message")
    if blocked:
        return blocked
    payload: Dict[str, Any] = {"content": message}
    if title:
        payload = {"embeds": [{"title": title, "description": message}]}
    api_request("POST", creds["webhook_url"], json=payload)
    logger.info("Webhook message sent")
    return "Webhook message sent"


# ── Telegram ──────────────────────────────────────────────────────────────────

def test_telegram(creds: Dict[str, Any]) -> str:
    data = api_request("GET", f"https://api.telegram.org/bot{creds['bot_token']}/getMe")
    return f"Connected as @{data['result']['username']}"


def telegram_send(creds: Dict[str, Any], chat_id: str, message: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "sending a Telegram message")
    if blocked:
        return blocked
    chat = chat_id or creds.get("default_chat_id", "")
    api_request(
        "POST",
        f"https://api.telegram.org/bot{creds['bot_token']}/sendMessage",
        json={"chat_id": chat, "text": message},
    )
    logger.info("Telegram message sent to %s", chat)
    return f"Telegram message sent to {chat}"


# ── SendGrid ──────────────────────────────────────────────────────────────────

def test_sendgrid(creds: Dict[str, Any]) -> str:
    api_request(
        "GET",
        "https://api.sendgrid.com/v3/user/profile",
        headers={"Authorization": f"Bearer {creds['api_key']}"},
    )
    return "SendGrid connected"


def sendgrid_send(creds: Dict[str, Any], to: str, subject: str, body: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "sending email via SendGrid")
    if blocked:
        return blocked
    api_request(
        "POST",
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {creds['api_key']}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": creds["from_email"]},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        },
    )
    logger.info("SendGrid email sent to %s", to)
    return f"Email sent via SendGrid to {to}"


# ── Twilio ────────────────────────────────────────────────────────────────────

def test_twilio(creds: Dict[str, Any]) -> str:
    sid = creds["account_sid"]
    auth = base64.b64encode(f"{sid}:{creds['auth_token']}".encode()).decode()
    api_request(
        "GET",
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
        headers={"Authorization": f"Basic {auth}"},
    )
    return "Twilio connected"


def twilio_send_sms(creds: Dict[str, Any], to: str, message: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "sending an SMS via Twilio")
    if blocked:
        return blocked
    sid = creds["account_sid"]
    auth = base64.b64encode(f"{sid}:{creds['auth_token']}".encode()).decode()
    api_request(
        "POST",
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        headers={"Authorization": f"Basic {auth}"},
        data={"From": creds["from_number"], "To": to, "Body": message},
    )
    logger.info("Twilio SMS sent to %s", to)
    return f"SMS sent to {to}"


# ── GitHub ────────────────────────────────────────────────────────────────────

def _gh_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def test_github(creds: Dict[str, Any]) -> str:
    data = api_request("GET", "https://api.github.com/user", headers=_gh_headers(creds["token"]))
    return f"Connected as {data.get('login', 'user')}"


def github_list_repos(creds: Dict[str, Any], limit: int = 10) -> str:
    data = api_request(
        "GET",
        "https://api.github.com/user/repos",
        headers=_gh_headers(creds["token"]),
        params={"per_page": limit, "sort": "updated"},
    )
    return "\n".join(f"{r['full_name']} ({r.get('private') and 'private' or 'public'})" for r in data)


def github_create_issue(creds: Dict[str, Any], repo: str, title: str, body: str = "", confirm: bool = False) -> str:
    blocked = require_confirm(confirm, f"creating a GitHub issue in {repo}")
    if blocked:
        return blocked
    owner, name = repo.split("/", 1)
    data = api_request(
        "POST",
        f"https://api.github.com/repos/{owner}/{name}/issues",
        headers=_gh_headers(creds["token"]),
        json={"title": title, "body": body},
    )
    logger.info("GitHub issue created in %s", repo)
    return f"Issue created: #{data['number']} — {data['html_url']}"


def github_search_code(creds: Dict[str, Any], query: str, limit: int = 5) -> str:
    data = api_request(
        "GET",
        "https://api.github.com/search/code",
        headers=_gh_headers(creds["token"]),
        params={"q": query, "per_page": limit},
    )
    items = data.get("items", [])
    return "\n".join(f"{i['repository']['full_name']}: {i['path']}" for i in items) or "No results."


# ── GitLab ────────────────────────────────────────────────────────────────────

def test_gitlab(creds: Dict[str, Any]) -> str:
    base = creds.get("base_url", "https://gitlab.com").rstrip("/")
    data = api_request("GET", f"{base}/api/v4/user", headers={"PRIVATE-TOKEN": creds["token"]})
    return f"Connected as {data.get('username', 'user')}"


def gitlab_list_projects(creds: Dict[str, Any], limit: int = 10) -> str:
    base = creds.get("base_url", "https://gitlab.com").rstrip("/")
    data = api_request(
        "GET",
        f"{base}/api/v4/projects",
        headers={"PRIVATE-TOKEN": creds["token"]},
        params={"membership": True, "per_page": limit},
    )
    return "\n".join(f"{p['path_with_namespace']}" for p in data)


def gitlab_create_issue(creds: Dict[str, Any], project_id: str, title: str, description: str = "") -> str:
    base = creds.get("base_url", "https://gitlab.com").rstrip("/")
    pid = quote(project_id, safe="")
    data = api_request(
        "POST",
        f"{base}/api/v4/projects/{pid}/issues",
        headers={"PRIVATE-TOKEN": creds["token"]},
        json={"title": title, "description": description},
    )
    return f"Issue created: #{data['iid']} — {data.get('web_url', '')}"


# ── Jira ──────────────────────────────────────────────────────────────────────

def test_jira(creds: Dict[str, Any]) -> str:
    base = creds["base_url"].rstrip("/")
    auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    data = api_request("GET", f"{base}/rest/api/3/myself", headers={"Authorization": f"Basic {auth}"})
    return f"Connected as {data.get('displayName', creds['email'])}"


def jira_search(creds: Dict[str, Any], jql: str, limit: int = 10) -> str:
    base = creds["base_url"].rstrip("/")
    auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    data = api_request(
        "GET",
        f"{base}/rest/api/3/search",
        headers={"Authorization": f"Basic {auth}"},
        params={"jql": jql, "maxResults": limit},
    )
    issues = data.get("issues", [])
    return "\n".join(f"{i['key']}: {i['fields']['summary']}" for i in issues) or "No issues found."


def jira_create_issue(creds: Dict[str, Any], project_key: str, summary: str, description: str = "") -> str:
    base = creds["base_url"].rstrip("/")
    auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    data = api_request(
        "POST",
        f"{base}/rest/api/3/issue",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        json={
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {"type": "doc", "version": 1, "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                ]},
                "issuetype": {"name": "Task"},
            }
        },
    )
    return f"Issue created: {data.get('key', data.get('id', 'ok'))}"


# ── Linear ────────────────────────────────────────────────────────────────────

def test_linear(creds: Dict[str, Any]) -> str:
    data = api_request(
        "POST",
        "https://api.linear.app/graphql",
        headers={"Authorization": creds["api_key"], "Content-Type": "application/json"},
        json={"query": "{ viewer { name email } }"},
    )
    viewer = data["data"]["viewer"]
    return f"Connected as {viewer.get('name', viewer.get('email', 'user'))}"


def linear_search_issues(creds: Dict[str, Any], query: str, limit: int = 10) -> str:
    gql = """
    query($q: String!, $n: Int!) {
      issueSearch(query: $q, first: $n) {
        nodes { issue { identifier title state { name } } }
      }
    }"""
    data = api_request(
        "POST",
        "https://api.linear.app/graphql",
        headers={"Authorization": creds["api_key"], "Content-Type": "application/json"},
        json={"query": gql, "variables": {"q": query, "n": limit}},
    )
    nodes = data.get("data", {}).get("issueSearch", {}).get("nodes", [])
    return "\n".join(f"{n['issue']['identifier']}: {n['issue']['title']}" for n in nodes) or "No issues."


def linear_create_issue(creds: Dict[str, Any], team_id: str, title: str, description: str = "") -> str:
    gql = """
    mutation($teamId: String!, $title: String!, $desc: String!) {
      issueCreate(input: { teamId: $teamId, title: $title, description: $desc }) {
        issue { identifier url }
      }
    }"""
    data = api_request(
        "POST",
        "https://api.linear.app/graphql",
        headers={"Authorization": creds["api_key"], "Content-Type": "application/json"},
        json={"query": gql, "variables": {"teamId": team_id, "title": title, "desc": description}},
    )
    issue = data["data"]["issueCreate"]["issue"]
    return f"Issue {issue['identifier']} created — {issue['url']}"


# ── Trello ────────────────────────────────────────────────────────────────────

def test_trello(creds: Dict[str, Any]) -> str:
    data = api_request(
        "GET",
        "https://api.trello.com/1/members/me",
        params={"key": creds["api_key"], "token": creds["token"]},
    )
    return f"Connected as {data.get('fullName', data.get('username', 'user'))}"


def trello_list_boards(creds: Dict[str, Any]) -> str:
    data = api_request(
        "GET",
        "https://api.trello.com/1/members/me/boards",
        params={"key": creds["api_key"], "token": creds["token"], "fields": "name,url"},
    )
    return "\n".join(f"{b['name']}: {b['url']}" for b in data)


def trello_create_card(creds: Dict[str, Any], list_id: str, name: str, desc: str = "") -> str:
    data = api_request(
        "POST",
        "https://api.trello.com/1/cards",
        params={"key": creds["api_key"], "token": creds["token"]},
        data={"idList": list_id, "name": name, "desc": desc},
    )
    return f"Card created: {data.get('name')} — {data.get('shortUrl', data.get('url', ''))}"


# ── Asana ─────────────────────────────────────────────────────────────────────

def test_asana(creds: Dict[str, Any]) -> str:
    data = api_request(
        "GET",
        "https://app.asana.com/api/1.0/users/me",
        headers={"Authorization": f"Bearer {creds['token']}"},
    )
    return f"Connected as {data['data']['name']}"


def asana_list_tasks(creds: Dict[str, Any], project_gid: str, limit: int = 10) -> str:
    data = api_request(
        "GET",
        f"https://app.asana.com/api/1.0/projects/{project_gid}/tasks",
        headers={"Authorization": f"Bearer {creds['token']}"},
        params={"limit": limit, "opt_fields": "name,completed"},
    )
    tasks = data.get("data", [])
    return "\n".join(f"{'[x]' if t.get('completed') else '[ ]'} {t['name']}" for t in tasks) or "No tasks."


def asana_create_task(creds: Dict[str, Any], project_gid: str, name: str, notes: str = "") -> str:
    data = api_request(
        "POST",
        "https://app.asana.com/api/1.0/tasks",
        headers={"Authorization": f"Bearer {creds['token']}", "Content-Type": "application/json"},
        json={"data": {"name": name, "notes": notes, "projects": [project_gid]}},
    )
    return f"Task created: {data['data']['name']} (gid: {data['data']['gid']})"


# ── Notion ────────────────────────────────────────────────────────────────────

def test_notion(creds: Dict[str, Any]) -> str:
    data = api_request(
        "GET",
        "https://api.notion.com/v1/users/me",
        headers={
            "Authorization": f"Bearer {creds['token']}",
            "Notion-Version": "2022-06-28",
        },
    )
    name = data.get("name") or data.get("bot", {}).get("owner", {}).get("user", {}).get("name", "Notion")
    return f"Connected to Notion ({name})"


def notion_search(creds: Dict[str, Any], query: str, limit: int = 10) -> str:
    data = api_request(
        "POST",
        "https://api.notion.com/v1/search",
        headers={
            "Authorization": f"Bearer {creds['token']}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={"query": query, "page_size": limit},
    )
    results = data.get("results", [])
    lines = []
    for r in results:
        title = "Untitled"
        props = r.get("properties", {})
        for v in props.values():
            if v.get("type") == "title" and v.get("title"):
                title = v["title"][0].get("plain_text", title)
                break
        lines.append(f"{r.get('object', 'item')}: {title} ({r.get('id', '')[:8]}…)")
    return "\n".join(lines) or "No results."


def notion_create_page(creds: Dict[str, Any], database_id: str, title: str, content: str = "") -> str:
    data = api_request(
        "POST",
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {creds['token']}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": title}}]},
            },
            "children": [
                {"object": "block", "type": "paragraph", "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }}
            ] if content else [],
        },
    )
    return f"Notion page created: {data.get('url', data.get('id', 'ok'))}"


# ── Confluence ────────────────────────────────────────────────────────────────

def test_confluence(creds: Dict[str, Any]) -> str:
    base = creds["base_url"].rstrip("/")
    auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    data = api_request("GET", f"{base}/wiki/rest/api/user/current", headers={"Authorization": f"Basic {auth}"})
    return f"Connected as {data.get('displayName', creds['email'])}"


def confluence_search(creds: Dict[str, Any], query: str, limit: int = 10) -> str:
    base = creds["base_url"].rstrip("/")
    auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    data = api_request(
        "GET",
        f"{base}/wiki/rest/api/content/search",
        headers={"Authorization": f"Basic {auth}"},
        params={"cql": f"text ~ \"{query}\"", "limit": limit},
    )
    results = data.get("results", [])
    return "\n".join(f"{r['title']} ({r['type']})" for r in results) or "No pages found."


# ── Airtable ──────────────────────────────────────────────────────────────────

def test_airtable(creds: Dict[str, Any]) -> str:
    api_request(
        "GET",
        f"https://api.airtable.com/v0/meta/bases",
        headers={"Authorization": f"Bearer {creds['token']}"},
    )
    return "Airtable connected"


def airtable_list_records(creds: Dict[str, Any], table: str, limit: int = 10) -> str:
    base_id = creds["base_id"]
    data = api_request(
        "GET",
        f"https://api.airtable.com/v0/{base_id}/{quote(table)}",
        headers={"Authorization": f"Bearer {creds['token']}"},
        params={"maxRecords": limit},
    )
    records = data.get("records", [])
    return json.dumps(records, indent=2)[:3000] or "No records."


def airtable_create_record(creds: Dict[str, Any], table: str, fields_json: str) -> str:
    base_id = creds["base_id"]
    fields = json.loads(fields_json)
    data = api_request(
        "POST",
        f"https://api.airtable.com/v0/{base_id}/{quote(table)}",
        headers={"Authorization": f"Bearer {creds['token']}", "Content-Type": "application/json"},
        json={"fields": fields},
    )
    return f"Record created: {data.get('id', 'ok')}"


# ── HubSpot ───────────────────────────────────────────────────────────────────

def test_hubspot(creds: Dict[str, Any]) -> str:
    api_request(
        "GET",
        "https://api.hubapi.com/crm/v3/objects/contacts",
        headers={"Authorization": f"Bearer {creds['token']}"},
        params={"limit": 1},
    )
    return "HubSpot connected"


def hubspot_search_contacts(creds: Dict[str, Any], query: str, limit: int = 10) -> str:
    data = api_request(
        "POST",
        "https://api.hubapi.com/crm/v3/objects/contacts/search",
        headers={"Authorization": f"Bearer {creds['token']}", "Content-Type": "application/json"},
        json={
            "query": query,
            "limit": limit,
            "properties": ["firstname", "lastname", "email"],
        },
    )
    results = data.get("results", [])
    lines = []
    for r in results:
        p = r.get("properties", {})
        lines.append(f"{p.get('firstname', '')} {p.get('lastname', '')} <{p.get('email', '')}>")
    return "\n".join(lines) or "No contacts found."


# ── Stripe ────────────────────────────────────────────────────────────────────

def test_stripe(creds: Dict[str, Any]) -> str:
    api_request(
        "GET",
        "https://api.stripe.com/v1/balance",
        headers={"Authorization": f"Bearer {creds['secret_key']}"},
    )
    return "Stripe connected"


def stripe_list_customers(creds: Dict[str, Any], limit: int = 10) -> str:
    data = api_request(
        "GET",
        "https://api.stripe.com/v1/customers",
        headers={"Authorization": f"Bearer {creds['secret_key']}"},
        params={"limit": limit},
    )
    return "\n".join(f"{c['id']}: {c.get('email', c.get('name', 'no email'))}" for c in data.get("data", []))


# ── OpenWeather ───────────────────────────────────────────────────────────────

def test_openweather(creds: Dict[str, Any]) -> str:
    api_request(
        "GET",
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": "London", "appid": creds["api_key"]},
    )
    return "OpenWeather connected"


def openweather_get(creds: Dict[str, Any], city: str) -> str:
    data = api_request(
        "GET",
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": creds["api_key"], "units": "metric"},
    )
    return (
        f"{data['name']}: {data['weather'][0]['description']}, "
        f"{data['main']['temp']}°C (feels like {data['main']['feels_like']}°C), "
        f"humidity {data['main']['humidity']}%"
    )


# ── NewsAPI ───────────────────────────────────────────────────────────────────

def test_newsapi(creds: Dict[str, Any]) -> str:
    api_request(
        "GET",
        "https://newsapi.org/v2/top-headlines",
        params={"country": "us", "pageSize": 1, "apiKey": creds["api_key"]},
    )
    return "NewsAPI connected"


def newsapi_search(creds: Dict[str, Any], query: str, limit: int = 5) -> str:
    data = api_request(
        "GET",
        "https://newsapi.org/v2/everything",
        params={"q": query, "pageSize": limit, "apiKey": creds["api_key"], "sortBy": "publishedAt"},
    )
    articles = data.get("articles", [])
    return "\n".join(f"{a['title']} — {a.get('source', {}).get('name', '')}" for a in articles) or "No articles."


# ── Dropbox ───────────────────────────────────────────────────────────────────

def test_dropbox(creds: Dict[str, Any]) -> str:
    data = api_request(
        "POST",
        "https://api.dropboxapi.com/2/users/get_current_account",
        headers={"Authorization": f"Bearer {creds['token']}"},
    )
    return f"Connected as {data.get('name', {}).get('display_name', 'user')}"


def dropbox_list_folder(creds: Dict[str, Any], path: str = "") -> str:
    data = api_request(
        "POST",
        "https://api.dropboxapi.com/2/files/list_folder",
        headers={"Authorization": f"Bearer {creds['token']}", "Content-Type": "application/json"},
        json={"path": path or "", "limit": 20},
    )
    entries = data.get("entries", [])
    return "\n".join(f"{'📁' if e.get('.tag') == 'folder' else '📄'} {e['name']}" for e in entries) or "Empty folder."


# ── Calendly ──────────────────────────────────────────────────────────────────

def test_calendly(creds: Dict[str, Any]) -> str:
    data = api_request(
        "GET",
        "https://api.calendly.com/users/me",
        headers={"Authorization": f"Bearer {creds['token']}"},
    )
    return f"Connected as {data['resource'].get('name', 'user')}"


def calendly_list_events(creds: Dict[str, Any], limit: int = 10) -> str:
    me = api_request(
        "GET",
        "https://api.calendly.com/users/me",
        headers={"Authorization": f"Bearer {creds['token']}"},
    )
    user_uri = me["resource"]["uri"]
    data = api_request(
        "GET",
        "https://api.calendly.com/scheduled_events",
        headers={"Authorization": f"Bearer {creds['token']}"},
        params={"user": user_uri, "count": limit, "status": "active"},
    )
    events = data.get("collection", [])
    return "\n".join(f"{e['name']} @ {e['start_time']}" for e in events) or "No upcoming events."


# ── Mailchimp ─────────────────────────────────────────────────────────────────

def test_mailchimp(creds: Dict[str, Any]) -> str:
    dc = creds["api_key"].split("-")[-1]
    api_request(
        "GET",
        f"https://{dc}.api.mailchimp.com/3.0/ping",
        headers={"Authorization": f"Bearer {creds['api_key']}"},
    )
    return "Mailchimp connected"


def mailchimp_list_audiences(creds: Dict[str, Any], limit: int = 10) -> str:
    dc = creds["api_key"].split("-")[-1]
    data = api_request(
        "GET",
        f"https://{dc}.api.mailchimp.com/3.0/lists",
        headers={"Authorization": f"Bearer {creds['api_key']}"},
        params={"count": limit},
    )
    lists = data.get("lists", [])
    return "\n".join(f"{l['name']} ({l['stats']['member_count']} members)" for l in lists) or "No audiences."


# ── PostgreSQL (read-only) ────────────────────────────────────────────────────

_SQL_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"call|execute|do|merge|replace|attach|detach|pragma|vacuum|reindex|"
    r"comment|security|owner|into\s+outfile|load_file)\b",
    re.IGNORECASE,
)


def _is_readonly_select(sql: str) -> bool:
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        return False
    if ";" in cleaned:
        return False
    lower = cleaned.lower()
    if not (lower.startswith("select") or lower.startswith("with")):
        return False
    if _SQL_FORBIDDEN.search(cleaned):
        return False
    return True


def test_postgres(creds: Dict[str, Any]) -> str:
    try:
        import psycopg2
    except ImportError:
        raise ValueError("psycopg2 not installed — run: pip install psycopg2-binary")
    conn = psycopg2.connect(creds["connection_string"])
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
    return "PostgreSQL connected (read-only)"


def postgres_query(creds: Dict[str, Any], sql: str, limit: int = 20) -> str:
    import psycopg2

    if not _is_readonly_select(sql):
        return (
            "Only a single read-only SELECT / WITH…SELECT is allowed. "
            "INSERT/UPDATE/DELETE/DDL and multi-statements are blocked."
        )
    safe_limit = max(1, min(int(limit or 20), 100))
    conn = psycopg2.connect(creds["connection_string"])
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"{sql.rstrip(';')} LIMIT {safe_limit}")
            cols = [d[0] for d in cur.description or []]
            rows = cur.fetchall()
            if not rows:
                return "No rows."
            lines = [" | ".join(cols)]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))
            return "\n".join(lines)
    finally:
        conn.close()


# ── MongoDB ───────────────────────────────────────────────────────────────────

def test_mongodb(creds: Dict[str, Any]) -> str:
    try:
        from pymongo import MongoClient
    except ImportError:
        raise ValueError("pymongo not installed — run: pip install pymongo")
    client = MongoClient(creds["connection_string"], serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    client.close()
    return "MongoDB connected"


def mongodb_find(creds: Dict[str, Any], database: str, collection: str, query_json: str = "{}", limit: int = 10) -> str:
    from pymongo import MongoClient

    client = MongoClient(creds["connection_string"])
    try:
        q = json.loads(query_json or "{}")
        docs = list(client[database][collection].find(q).limit(limit))
        for d in docs:
            d.pop("_id", None)
        return json.dumps(docs, indent=2, default=str)[:4000] or "No documents."
    finally:
        client.close()


# ── Generic webhook / Zapier ──────────────────────────────────────────────────

def zapier_send(creds: Dict[str, Any], payload_json: str, confirm: bool = False) -> str:
    blocked = require_confirm(confirm, "triggering a Zapier webhook")
    if blocked:
        return blocked
    payload = json.loads(payload_json or "{}")
    api_request("POST", creds["webhook_url"], json=payload)
    logger.info("Zapier webhook triggered")
    return "Zapier webhook triggered"
