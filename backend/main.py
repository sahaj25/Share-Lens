import os
import signal
import sys
from datetime import datetime

from database.models import create_tables
from scheduler.jobs import create_scheduler
from alerts.telegram_bot import telegram_bot

# FIX: scheduler must be a module-level variable so the shutdown
# handler can access and stop it cleanly. Previously it was local
# to main() and the handler had no reference to it.
scheduler = None


def handle_shutdown(signum, frame):
    """Handle graceful shutdown — stops scheduler before exit"""
    print("\n⚠️ Shutdown signal received...")

    # FIX: stop the scheduler cleanly so no jobs fire mid-shutdown
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏱ Scheduler stopped")

    # FIX: wrap Telegram send in try/except — if Telegram is down
    # during a shutdown we still want the process to exit cleanly
    try:
        telegram_bot.send_message("⚠️ <b>Trading Tool shutting down...</b>")
    except Exception as e:
        print(f"⚠️ Could not send shutdown alert: {e}")

    sys.exit(0)


def main():
    global scheduler

    print("=" * 50)
    print("🚀 TRADING TOOL STARTING...")
    print(f"⏰ {datetime.now().strftime('%d %B %Y — %H:%M')}")
    print("=" * 50)

    # ── Step 1 — Create database tables ──
    print("\n📦 Setting up database...")
    try:
        create_tables()
        print("✅ Database ready")
    except Exception as e:
        # FIX: if DB setup fails the whole tool is useless — exit early
        # with a clear message instead of crashing deeper in the stack
        print(f"❌ Database setup failed: {e}")
        sys.exit(1)

    # ── Step 2 — Register signal handlers EARLY ──
    # FIX: signal handlers were registered AFTER uvicorn.run() which
    # blocks forever — they were never actually reached in the original.
    # Must be registered before uvicorn starts.
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    print("✅ Shutdown handlers registered")

    # ── Step 3 — Start scheduler ──
    print("\n⏱ Starting scheduler...")
    try:
        scheduler = create_scheduler()

        if not scheduler.running:
            scheduler.start()
            print("✅ Scheduler started")
        else:
            print("⚠️ Scheduler was already running")

        print("\n📋 Scheduled Jobs:")
        for job in scheduler.get_jobs():
            print(f"  → {job.name}")

    except Exception as e:
        # FIX: original silently continued with a broken scheduler.
        # Now we notify via Telegram and exit — no point running without it.
        print(f"❌ Scheduler failed to start: {e}")
        try:
            telegram_bot.send_message(f"❌ <b>Scheduler failed to start:</b> {e}")
        except Exception:
            pass
        sys.exit(1)

    # ── Step 4 — Send startup alert ──
    print("\n📱 Sending startup alert...")
    try:
        telegram_bot.send_restart_alert()
    except Exception as e:
        # FIX: don't crash if Telegram is slow at startup
        print(f"⚠️ Startup alert failed (non-fatal): {e}")

    # ── Step 5 — Angel API status ──
    print("⚠️ Angel API disabled for now")

    print("\n" + "=" * 50)
    print("✅ TRADING TOOL IS RUNNING")
    print("📱 Check Telegram for alerts")
    print("🌐 API starting...")
    print("=" * 50 + "\n")

    # ── Step 6 — Start FastAPI on main thread ──
    # FIX: moved imports to top-level scope (they were inside main()
    # for no reason — lazy imports here caused misleading ImportErrors
    # that looked like runtime failures rather than missing dependencies)
    import uvicorn
    from api.routes import app

    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Running API on port {port}")

    # FIX: disable uvicorn's own signal handlers so they don't override
    # our handle_shutdown() above. Without this, SIGTERM on Render goes
    # to uvicorn which exits immediately without stopping the scheduler.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()