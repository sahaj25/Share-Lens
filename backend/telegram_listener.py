"""
telegram_listener.py
--------------------
Runs as a long-polling Telegram bot.
Listens for commands and triggers GitHub Actions workflows on demand.

Commands:
  /scan   — Trigger the Share-Lens Stock Scan pipeline immediately
  /status — Check the status of the last GitHub Actions run
  /help   — Show available commands

Setup:
  Add to your .env file:
    GITHUB_PAT=your_personal_access_token
    GITHUB_OWNER=sahaj25
    GITHUB_REPO=Share-Lens
    GITHUB_WORKFLOW=stock_scan.yml
    GITHUB_BRANCH=main
    ALLOWED_CHAT_IDS=123456789,987654321   ← only these chats can trigger scans
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Telegram config ────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Only these chat IDs can trigger scans (security guard)
ALLOWED_IDS = {
    int(cid.strip())
    for cid in os.getenv("ALLOWED_CHAT_IDS", os.getenv("TELEGRAM_CHAT_ID", "")).split(",")
    if cid.strip()
}

# ── GitHub config ──────────────────────────────────────────────────────────────
GITHUB_PAT      = os.getenv("GITHUB_PAT")
GITHUB_OWNER    = os.getenv("GITHUB_OWNER", "sahaj25")
GITHUB_REPO     = os.getenv("GITHUB_REPO", "Share-Lens")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "stock_scan.yml")
GITHUB_BRANCH   = os.getenv("GITHUB_BRANCH", "main")

GITHUB_DISPATCH_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    f"/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
)
GITHUB_RUNS_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    f"/actions/workflows/{GITHUB_WORKFLOW}/runs?per_page=1"
)

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_PAT}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def trigger_pipeline():
    """Dispatch a workflow_dispatch event to GitHub Actions."""
    resp = requests.post(
        GITHUB_DISPATCH_URL,
        headers=GITHUB_HEADERS,
        json={"ref": GITHUB_BRANCH},
        timeout=10,
    )
    return resp.status_code == 204   # 204 No Content = success


def get_last_run_status():
    """Return a human-readable status of the most recent workflow run."""
    resp = requests.get(GITHUB_RUNS_URL, headers=GITHUB_HEADERS, timeout=10)
    if resp.status_code != 200:
        return "⚠️ Could not fetch run status from GitHub."

    runs = resp.json().get("workflow_runs", [])
    if not runs:
        return "ℹ️ No runs found yet."

    run = runs[0]
    status     = run.get("status")       # queued / in_progress / completed
    conclusion = run.get("conclusion")   # success / failure / cancelled / None
    run_number = run.get("run_number")
    started_at = run.get("run_started_at", "")[:16].replace("T", " ")
    url        = run.get("html_url")

    status_emoji = {
        "queued":      "⏳",
        "in_progress": "🔄",
        "completed":   "✅" if conclusion == "success" else "❌",
    }.get(status, "❓")

    conclusion_text = conclusion.upper() if conclusion else status.upper()

    return (
        f"{status_emoji} <b>Run #{run_number}</b>\n"
        f"Status: <b>{conclusion_text}</b>\n"
        f"Started: {started_at} UTC\n"
        f"<a href='{url}'>View on GitHub →</a>"
    )


# ── Telegram helpers ───────────────────────────────────────────────────────────

def send(chat_id, text):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    try:
        resp = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
        return resp.json().get("result", [])
    except Exception:
        return []


# ── Command handlers ───────────────────────────────────────────────────────────

def handle_scan(chat_id):
    send(chat_id, "⏳ Triggering scan pipeline on GitHub Actions...")
    if trigger_pipeline():
        send(
            chat_id,
            "✅ <b>Scan pipeline triggered!</b>\n\n"
            "The scan will start in ~30 seconds.\n"
            "You'll receive results here when it completes.\n\n"
            "Use /status to check progress.",
        )
    else:
        send(chat_id, "❌ Failed to trigger pipeline. Check your GITHUB_PAT secret.")


def handle_status(chat_id):
    send(chat_id, get_last_run_status())


def handle_help(chat_id):
    send(
        chat_id,
        "🤖 <b>Share-Lens Bot Commands</b>\n\n"
        "/scan — Trigger a stock scan right now\n"
        "/status — Check the latest pipeline run\n"
        "/help — Show this message",
    )


HANDLERS = {
    "/scan":   handle_scan,
    "/start":  handle_scan,   # /start also triggers a scan
    "/status": handle_status,
    "/help":   handle_help,
}


# ── Main polling loop ──────────────────────────────────────────────────────────

def main():
    print("🤖 Share-Lens Telegram listener started...")
    print(f"   Allowed chat IDs: {ALLOWED_IDS}")
    offset = None

    while True:
        updates = get_updates(offset)

        for update in updates:
            offset = update["update_id"] + 1

            message = update.get("message") or update.get("channel_post")
            if not message:
                continue

            chat_id = message["chat"]["id"]
            parts = message.get("text", "").strip().lower().split()
            if not parts:
                continue
            text = parts[0]
            # Security: ignore messages from unknown chats
            if ALLOWED_IDS and chat_id not in ALLOWED_IDS:
                send(chat_id, "⛔ Unauthorized. Your chat ID is not whitelisted.")
                continue

            handler = HANDLERS.get(text)
            if handler:
                handler(chat_id)
            else:
                send(chat_id, "❓ Unknown command. Send /help to see what I can do.")

        time.sleep(1)


if __name__ == "__main__":
    main()