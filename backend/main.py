import time
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

    # Step 2 — Start scheduler
    print("\n⏱ Starting scheduler...")
    scheduler = create_scheduler()
    scheduler.start()
    print("✅ Scheduler started — all jobs scheduled")

    # Print scheduled jobs
    print("\n📋 Scheduled Jobs:")
    for job in scheduler.get_jobs():
        print(f"  → {job.name}")

    # Step 3 — Start FastAPI in background thread
    print("\n🌐 Starting FastAPI server...")
    import threading
    import uvicorn
    from api.routes import app

    def run_api():
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    print("✅ API server running on port 8000")

    # Step 4 — Send startup alert to Telegram
    print("\n📱 Sending startup alert...")
    telegram_bot.send_restart_alert()

    # Step 5 — Login to Angel One
    print("\n🔐 Logging into Angel One...")
    from data.angel_api import angel
    login_success = angel.login()

    if login_success:
        print("✅ Angel One connected")
    else:
        print("⚠️ Angel One login failed — check credentials in .env")
        telegram_bot.send_message(
            "⚠️ <b>WARNING:</b> Angel One login failed. Check API credentials."
        )

    # Handle shutdown gracefully
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("\n" + "=" * 50)
    print("✅ TRADING TOOL IS RUNNING")
    print("📱 Check Telegram for alerts")
    print("🌐 API running at http://localhost:8000")
    print("Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    # Keep running forever
    while True:
        time.sleep(60)
        # Re-login to Angel One every 6 hours
        # (sessions expire)
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        if current_minute == 0 and current_hour in [6, 12, 18, 0]:
            print("🔄 Re-logging into Angel One...")
            angel.login()


if __name__ == "__main__":
    main()