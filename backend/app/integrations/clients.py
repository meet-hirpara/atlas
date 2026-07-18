import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

MAIL_SERVERS = {
    "gmail": {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
    },
    "outlook": {
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
}


def test_slack(creds: Dict[str, Any]) -> str:
    client = WebClient(token=creds["bot_token"])
    auth = client.auth_test()
    return f"Connected as {auth['user']} in workspace {auth.get('team', 'unknown')}"


def test_mail(provider: str, creds: Dict[str, Any]) -> str:
    cfg = MAIL_SERVERS[provider]
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as smtp:
        smtp.starttls()
        smtp.login(creds["email"], creds["app_password"])
    return f"Mail connected for {creds['email']}"


def slack_send(creds: Dict[str, Any], channel: str, text: str) -> str:
    client = WebClient(token=creds["bot_token"])
    ch = channel if channel.startswith("#") else f"#{channel.lstrip('#')}"
    if creds.get("default_channel") and channel.lower() in ("default", "general"):
        ch = creds["default_channel"]
    try:
        resp = client.chat_postMessage(channel=ch, text=text)
        return f"Message sent to {ch} (ts: {resp['ts']})"
    except SlackApiError as e:
        return f"Slack error: {e.response['error']}"


def slack_list_channels(creds: Dict[str, Any], limit: int = 15) -> str:
    client = WebClient(token=creds["bot_token"])
    try:
        resp = client.conversations_list(types="public_channel,private_channel", limit=limit)
        channels = [f"#{c['name']}" for c in resp.get("channels", [])]
        return "Channels: " + ", ".join(channels) if channels else "No channels found."
    except SlackApiError as e:
        return f"Slack error: {e.response['error']}"


def mail_send(provider: str, creds: Dict[str, Any], to: str, subject: str, body: str) -> str:
    cfg = MAIL_SERVERS[provider]
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = creds["email"]
    msg["To"] = to
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=20) as smtp:
        smtp.starttls()
        smtp.login(creds["email"], creds["app_password"])
        smtp.send_message(msg)
    return f"Email sent to {to}"


def mail_search(provider: str, creds: Dict[str, Any], query: str, limit: int = 5) -> str:
    cfg = MAIL_SERVERS[provider]
    imap = imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"])
    try:
        imap.login(creds["email"], creds["app_password"])
        imap.select("INBOX")
        _, data = imap.search(None, "ALL")
        ids = data[0].split()
        ids = ids[-50:]
        results: List[str] = []
        q = query.lower()
        for mid in reversed(ids):
            _, msg_data = imap.fetch(mid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = msg.get("Subject", "")
            sender = msg.get("From", "")
            if q in subject.lower() or q in sender.lower() or not q:
                results.append(f"From: {sender} | Subject: {subject}")
            if len(results) >= limit:
                break
        return "\n".join(results) if results else "No matching emails found."
    finally:
        imap.logout()
