import os
import signal
import sys
from datetime import datetime

from database.models import create_tables
from scheduler.jobs import create_scheduler
from alerts.telegram_bot import telegram_bot


def handle_shutdown(signum, frame):
    """Handle graceful shutdown"""
    print("\n⚠️ Shutdown signal received...")
    telegram_bot.send_message("⚠️ <b>Trading Tool shutting down...</b>")
    sys.exit(0)


def main():
    print("=" * 50)
    print("🚀 TRADING TOOL STARTING...")
    print(f"⏰ {datetime.now().strftime('%d %B %Y — %H:%M')}")
    print("=" * 50)

    # Step 1 — Create database tables
    print("\n📦 Setting up database...")
    create_tables()

    # Step 2 — Start scheduler (SAFE)
    print("\n⏱ Starting scheduler...")
    try:
        scheduler = create_scheduler()

        # Prevent duplicate start
        if not scheduler.running:
            scheduler.start()
            print("✅ Scheduler started")

        print("\n📋 Scheduled Jobs:")
        for job in scheduler.get_jobs():
            print(f"  → {job.name}")

    except Exception as e:
        print(f"❌ Scheduler failed: {e}")

    # Step 3 — Send startup alert
    print("\n📱 Sending startup alert...")
    telegram_bot.send_restart_alert()

    # Step 4 — Angel API (still disabled for safety)
    print("⚠️ Angel API disabled for now")

    # Handle shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("\n" + "=" * 50)
    print("✅ TRADING TOOL IS RUNNING")
    print("📱 Check Telegram for alerts")
    print("🌐 API starting...")
    print("=" * 50 + "\n")

    # Step 5 — Start FastAPI (MAIN THREAD)
    import uvicorn
    from api.routes import app

    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Running API on port {port}")

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()