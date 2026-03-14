from apscheduler.schedulers.background import BackgroundScheduler

from apscheduler.triggers.cron import CronTrigger

from datetime import datetime

from config import (

    SWING_SCAN_TIME,

    INTRADAY_START_TIME,

    INTRADAY_END_TIME,

    EOD_SUMMARY_TIME

)

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
    """Check if today is a weekday"""

    return datetime.now().weekday() < 5  # 0-4 = Mon-Fri


def should_run():
    """Combined check — weekday and not holiday"""

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

    from ai.claude_agent import claude_agent

    from alerts.telegram_bot import telegram_bot

    from database.queries import db_queries

    if not should_run():
        today = datetime.now().strftime("%d %B %Y")

        from alerts.telegram_bot import telegram_bot

        telegram_bot.send_holiday_alert(today)

        return

    print("🔍 Running swing scan...")

    # Run scan

    opportunities = swing_scanner.scan_all()

    # Get market mood

    mood, bullish_count, total = swing_scanner.get_market_mood()

    # AI market commentary

    ai_commentary = claude_agent.analyze_market_mood(

        bullish_count, total, mood

    )

    # Add AI analysis to each opportunity

    for opp in opportunities:
        ai_analysis = claude_agent.analyze_swing_signal(opp)

        opp["ai_analysis"] = ai_analysis

        # Save signal to database

        db_queries.save_signal(opp, ai_analysis, "SWING")

    # Send Telegram report

    telegram_bot.send_swing_report(

        opportunities=opportunities,

        market_mood=mood,

        bullish_count=bullish_count,

        total=total,

        ai_commentary=ai_commentary

    )

    print(f"✅ Swing scan complete — {len(opportunities)} opportunities sent")


def job_intraday_scan():
    """Every 5 mins 9:15 AM - 11:00 AM"""

    from scanners.intraday_scanner import intraday_scanner

    from ai.claude_agent import claude_agent

    from alerts.telegram_bot import telegram_bot

    from database.queries import db_queries

    if not should_run():
        return

    print(f"⚡ Intraday scan — {datetime.now().strftime('%H:%M')}")

    # Run scan

    opportunities = intraday_scanner.scan_all()

    # Send alert for each opportunity

    for opp in opportunities:
        ai_analysis = claude_agent.analyze_intraday_signal(opp)

        opp["ai_analysis"] = ai_analysis

        # Save to database

        db_queries.save_signal(opp, ai_analysis, "INTRADAY")

        # Send Telegram alert

        telegram_bot.send_intraday_alert(opp)

    if opportunities:
        print(f"✅ {len(opportunities)} intraday signal(s) sent")


def job_position_monitor():
    """Every 1 min during market hours 9:15 AM - 3:30 PM"""

    from monitor.position_monitor import position_monitor

    if not should_run():
        return

    position_monitor.monitor_all()


def job_eod_summary():
    """3:20 PM — end of day summary"""

    from monitor.position_monitor import position_monitor

    from scanners.swing_scanner import swing_scanner

    from ai.claude_agent import claude_agent

    from alerts.telegram_bot import telegram_bot

    if not should_run():
        return

    print("📊 Running EOD summary...")

    # Get open positions summary

    open_positions = position_monitor.get_open_positions_summary()

    # Run evening swing scan for tomorrow's setups

    new_setups = swing_scanner.scan_all()

    # Get market mood

    mood, bullish_count, total = swing_scanner.get_market_mood()

    # Send EOD summary

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


# ─────────────────────────────────────────

# Scheduler Setup

# ─────────────────────────────────────────

def create_scheduler():
    """Create and configure the scheduler"""

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # Health check — 8:00 AM every weekday

    scheduler.add_job(

        job_health_check,

        CronTrigger(hour=8, minute=0, day_of_week="mon-fri"),

        id="health_check",

        name="Daily Health Check"

    )

    # Intraday reset — 9:00 AM every weekday

    scheduler.add_job(

        job_intraday_reset,

        CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),

        id="intraday_reset",

        name="Intraday Reset"

    )

    # Swing scan — 8:30 AM every weekday

    scheduler.add_job(

        job_swing_scan,

        CronTrigger(hour=8, minute=30, day_of_week="mon-fri"),

        id="swing_scan",

        name="Morning Swing Scan"

    )

    # Intraday scan — every 5 mins 9:15 AM to 11:00 AM

    scheduler.add_job(

        job_intraday_scan,

        CronTrigger(

            hour="9-10",

            minute="15,20,25,30,35,40,45,50,55",

            day_of_week="mon-fri"

        ),

        id="intraday_scan",

        name="Intraday Scanner"

    )

    # Also run at 10:00 and 10:05 to 11:00

    scheduler.add_job(

        job_intraday_scan,

        CronTrigger(

            hour="10",

            minute="0,5,10,15,20,25,30,35,40,45,50,55",

            day_of_week="mon-fri"

        ),

        id="intraday_scan_10",

        name="Intraday Scanner 10AM"

    )

    # Position monitor — every 1 min 9:15 AM to 3:30 PM

    scheduler.add_job(

        job_position_monitor,

        CronTrigger(

            hour="9-15",

            minute="*",

            day_of_week="mon-fri"

        ),

        id="position_monitor",

        name="Position Monitor"

    )

    # EOD summary — 3:20 PM every weekday

    scheduler.add_job(

        job_eod_summary,

        CronTrigger(hour=15, minute=20, day_of_week="mon-fri"),

        id="eod_summary",

        name="EOD Summary"

    )

    return scheduler


