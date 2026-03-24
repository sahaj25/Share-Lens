import os
import signal
import sys
from datetime import datetime

from database.models import create_tables
from alerts.telegram_bot import telegram_bot


def handle_shutdown(signum, frame):
    """Handle graceful shutdown"""
    print("\n⚠️ Shutdown signal received...")

    try:
        telegram_bot.send_message("⚠️ <b>Trading Tool shutting down...</b>")
    except Exception as e:
        print(f"⚠️ Could not send shutdown alert: {e}")

    sys.exit(0)


def main():
    print("=" * 50)
    print("🚀 TRADING TOOL STARTING...")
    print(f"⏰ {datetime.now().strftime('%d %B %Y — %H:%M')}")
    print("=" * 50)

    # Step 1 — DB setup
    print("\n📦 Setting up database...")
    try:
        create_tables()
        print("✅ Database ready")
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        sys.exit(1)

    # Step 2 — Register shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    print("✅ Shutdown handlers registered")

    # Step 3 — Startup alert
    print("\n📱 Sending startup alert...")
    try:
        telegram_bot.send_restart_alert()
    except Exception as e:
        print(f"⚠️ Startup alert failed: {e}")

    print("\n" + "=" * 50)
    print("✅ TRADING TOOL IS RUNNING")
    print("🌐 API starting...")
    print("=" * 50 + "\n")

    # Step 4 — Run FastAPI
    import uvicorn
    from api.routes import app

    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Running API on port {port}")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()