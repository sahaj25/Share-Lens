from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import requests
import os

# NSE Holiday list 2026 — update every year
NSE_HOLIDAYS_2026 = [
    "2026-01-26",  # Republic Day
    "2026-03-25",  # Holi
    "2026-04-02",  # Ram Navami
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-04-17",  # Good Friday
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-08-27",  # Ganesh Chaturthi
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-20",  # Diwali Laxmi Pujan
    "2026-10-21",  # Diwali Balipratipada
    "2026-11-04",  # Gurunanak Jayanti
    "2026-12-25",  # Christmas
]

def is_market_holiday():
    """Check if today is a market holiday"""
    today = datetime.now().strftime("%Y-%m-%d")
    return today in NSE_HOLIDAYS_2026

def is_weekday():
    """Check if today is a weekday (Mon–Fri)"""
    return datetime.now().weekday() < 5

def should_run():
    """Combined check — weekday and not a market holiday"""
    return is_weekday() and not is_market_holiday()

# ─────────────────────────────────────────
# Job Functions
# ─────────────────────────────────────────

def job_health_check():
    """8:00 AM — daily health check"""
    from alerts.telegram_bot import telegram_bot
    if not should_run():
        return
    print("⏰ Running health check...")
    telegram_bot.send_health_check()

def job_swing_scan():
    """8:30 AM — morning swing scan"""
    from scanners.swing_scanner import swing_scanner
    from ai.gemini_agent import gemini_agent
    from alerts.telegram_bot import telegram_bot
    from database.queries import db_queries

    if not should_run():
        today = datetime.now().strftime("%d %B %Y")
        telegram_bot.send_holiday_alert(today)
        return

    print("🔍 Running swing scan...")
    opportunities = swing_scanner.scan_all()
    mood, bullish_count, total = swing_scanner.get_market_mood()
    ai_commentary = gemini_agent.analyze_market_mood(bullish_count, total, mood)

    for opp in opportunities:
        ai_analysis = gemini_agent.analyze_swing_signal(opp)
        opp["ai_analysis"] = ai_analysis
        db_queries.save_signal(opp, ai_analysis, "SWING")

    telegram_bot.send_swing_report(
        opportunities=opportunities,
        market_mood=mood,
        bullish_count=bullish_count,
        total=total,
        ai_commentary=ai_commentary
    )
    print(f"✅ Swing scan complete — {len(opportunities)} opportunities sent")

def job_intraday_scan():
    """Every 5 mins 9:15 AM – 11:00 AM"""
    from scanners.intraday_scanner import intraday_scanner
    from ai.gemini_agent import gemini_agent
    from alerts.telegram_bot import telegram_bot
    from database.queries import db_queries

    if not should_run():
        return

    now = datetime.now().time()
    start = datetime.strptime("09:15", "%H:%M").time()
    end = datetime.strptime("11:00", "%H:%M").time()
    if not (start <= now <= end):
        return

    print(f"⚡ Intraday scan — {datetime.now().strftime('%H:%M')}")
    opportunities = intraday_scanner.scan_all()

    for opp in opportunities:
        ai_analysis = gemini_agent.analyze_intraday_signal(opp)
        opp["ai_analysis"] = ai_analysis
        db_queries.save_signal(opp, ai_analysis, "INTRADAY")
        telegram_bot.send_intraday_alert(opp)

    if opportunities:
        print(f"✅ {len(opportunities)} intraday signal(s) sent")

def job_position_monitor():
    """Every 1 min during market hours 9:15 AM – 3:30 PM"""
    from monitor.position_monitor import position_monitor
    if not should_run():
        return

    now = datetime.now().time()
    start = datetime.strptime("09:15", "%H:%M").time()
    end = datetime.strptime("15:30", "%H:%M").time()
    if not (start <= now <= end):
        return

    position_monitor.monitor_all()

def job_eod_summary():
    """3:20 PM — end of day summary"""
    from monitor.position_monitor import position_monitor
    from scanners.swing_scanner import swing_scanner
    from alerts.telegram_bot import telegram_bot

    if not should_run():
        return

    print("📊 Running EOD summary...")
    open_positions = position_monitor.get_open_positions_summary()
    new_setups = swing_scanner.scan_all()
    mood, bullish_count, total = swing_scanner.get_market_mood()

    telegram_bot.send_eod_summary(
        open_positions=open_positions,
        new_setups=new_setups,
        market_mood=mood,
        bullish_count=bullish_count,
        total=total
    )
    print("✅ EOD summary sent")

def job_intraday_reset():
    """9:00 AM — reset intraday scanner for new day"""
    from scanners.intraday_scanner import intraday_scanner
    if not should_run():
        return
    intraday_scanner.reset_daily()
    print("🔄 Intraday scanner reset")

def job_keep_alive():
    """Pings own /health endpoint every 10 mins to prevent Render sleep"""
    try:
        url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")
        requests.get(f"{url}/health", timeout=5)
        print("💓 Keep-alive ping sent")
    except Exception as e:
        print(f"⚠️ Keep-alive failed: {e}")

# ─────────────────────────────────────────
# Scheduler Setup
# ─────────────────────────────────────────

def create_scheduler():
    """Create, configure, and START the APScheduler instance"""
    
    # Define scheduler with India Timezone
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # 1. 8:00 AM — Health check
    scheduler.add_job(
        job_health_check,
        CronTrigger(hour=8, minute=0, day_of_week="mon-fri"),
        id="health_check",
        name="Daily Health Check"
    )

    # 2. 8:30 AM — Swing scan
    scheduler.add_job(
        job_swing_scan,
        CronTrigger(hour=8, minute=30, day_of_week="mon-fri"),
        id="swing_scan",
        name="Morning Swing Scan"
    )

    # 3. 9:00 AM — Intraday scanner reset
    scheduler.add_job(
        job_intraday_reset,
        CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),
        id="intraday_reset",
        name="Intraday Reset"
    )

    # 4. 9:15 AM – 11:00 AM — Intraday scan every 5 mins
    scheduler.add_job(
        job_intraday_scan,
        CronTrigger(
            hour="9,10,11",
            minute="0,5,10,15,20,25,30,35,40,45,50,55",
            day_of_week="mon-fri"
        ),
        id="intraday_scan",
        name="Intraday Scanner (9:15–11:00)"
    )

    # 5. 9:15 AM – 3:30 PM — Position monitor every 1 min
    scheduler.add_job(
        job_position_monitor,
        CronTrigger(
            hour="9,10,11,12,13,14,15",
            minute="*",
            day_of_week="mon-fri"
        ),
        id="position_monitor",
        name="Position Monitor"
    )

    # 6. 3:20 PM — EOD summary
    scheduler.add_job(
        job_eod_summary,
        CronTrigger(hour=15, minute=20, day_of_week="mon-fri"),
        id="eod_summary",
        name="EOD Summary"
    )

    # 7. Every 10 mins — Render keep-alive (runs 24/7)
    scheduler.add_job(
        job_keep_alive,
        CronTrigger(minute="*/10"),
        id="keep_alive",
        name="Render Keep-Alive"
    )

    # IMPORTANT: Start the scheduler!
    scheduler.start()
    print("🚀 Background Scheduler Started...")
    
    return scheduler