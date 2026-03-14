import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramBot:

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, message):
        """Core function — sends any message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print("✅ Telegram message sent")
                return True
            else:
                print(f"❌ Telegram error: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Telegram send failed: {e}")
            return False

    # ─────────────────────────────────────────
    # Health Check Alert
    # ─────────────────────────────────────────
    def send_health_check(self):
        """Sent every morning at 8:00 AM"""
        message = f"""
✅ <b>TOOL IS ALIVE</b>
📅 {datetime.now().strftime("%d %B %Y")}
⏰ {datetime.now().strftime("%H:%M")}

All systems normal ✅
Swing scan running at 8:30 AM 🔍
Intraday scanner starts at 9:15 AM ⚡

<i>If you did NOT get this message by 8:05 AM, check Railway.</i>
"""
        self.send_message(message)

    # ─────────────────────────────────────────
    # Swing Scan Report
    # ─────────────────────────────────────────
    def send_swing_report(self, opportunities, market_mood, bullish_count, total, ai_commentary):
        """Morning swing scan report — sent at 8:30 AM"""

        date_str = datetime.now().strftime("%d %B %Y")

        if not opportunities:
            message = f"""
🔍 <b>SWING SCAN — {date_str}</b>

❌ <b>No clean setups today across all 50 Nifty stocks.</b>

📊 Market Mood: {market_mood} ({bullish_count}/{total} stocks above EMA)
🤖 {ai_commentary}

<i>Best trade today = NO trade. Wait for tomorrow.</i>
"""
            self.send_message(message)
            return

        # Header
        message = f"🔍 <b>SWING SCAN — {date_str}</b>\n\n"
        message += f"📊 Market Mood: {market_mood} ({bullish_count}/{total} above EMA)\n"
        message += f"🤖 {ai_commentary}\n"
        message += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"✅ <b>{len(opportunities)} SETUP(S) FOUND:</b>\n\n"

        # Each opportunity
        for i, opp in enumerate(opportunities, 1):
            ai = opp.get("ai_analysis", {})
            confidence = ai.get("confidence", "MEDIUM")
            reasoning = ai.get("reasoning", "")
            caution = ai.get("caution", "NONE")
            action = ai.get("action", "")

            # Confidence emoji
            if confidence == "HIGH":
                conf_emoji = "🟢"
            elif confidence == "MEDIUM-HIGH":
                conf_emoji = "🟡"
            else:
                conf_emoji = "🟠"

            # Signal emoji
            signal_emoji = "📈" if opp["signal"] == "BUY" else "📉"

            message += f"{i}. <b>{opp['symbol']}</b> — Score: {opp['score']}/10 {conf_emoji}\n"
            message += f"   {signal_emoji} <b>{opp['signal']}</b> | Confidence: {confidence}\n"
            message += f"   Entry: ₹{opp['entry']}\n"
            message += f"   Stop Loss: ₹{opp['stop_loss']}\n"
            message += f"   Target: ₹{opp['target']}\n"
            message += f"   R/R: 1:{opp['risk_reward']} | Hold: {opp['hold_days']}\n"
            message += f"   RSI: {opp['rsi']} | ADX: {opp['adx']} | Vol: {opp['volume_ratio']}x\n"
            message += f"   💡 {reasoning}\n"

            if caution != "NONE":
                message += f"   ⚠️ {caution}\n"

            message += f"   🎯 {action}\n"
            message += f"\n"

        message += f"━━━━━━━━━━━━━━━━━━━━\n"
        message += f"💰 Max capital per trade: ₹7,500\n"
        message += f"🛑 Never risk more than ₹500 per trade\n"

        self.send_message(message)

    # ─────────────────────────────────────────
    # Intraday Alert
    # ─────────────────────────────────────────
    def send_intraday_alert(self, opp):
        """Sent instantly when intraday signal fires"""
        ai = opp.get("ai_analysis", {})
        confidence = ai.get("confidence", "MEDIUM")
        reasoning = ai.get("reasoning", "")
        caution = ai.get("caution", "NONE")

        signal_emoji = "📈" if opp["signal"] == "BUY" else "📉"

        if confidence == "HIGH":
            conf_emoji = "🟢"
        elif confidence == "MEDIUM-HIGH":
            conf_emoji = "🟡"
        else:
            conf_emoji = "🟠"

        message = f"""
⚡ <b>INTRADAY ALERT — {opp['time']}</b>

<b>{opp['symbol']}</b> {signal_emoji} <b>{opp['signal']}</b> {conf_emoji}
Score: {opp['score']}/10 | Confidence: {confidence}

Entry: ₹{opp['entry']}
Stop Loss: ₹{opp['stop_loss']}
Target 1: ₹{opp['target_1']}
Target 2: ₹{opp['target_2']}
R/R: 1:{opp['risk_reward']}

VWAP: ₹{opp['vwap']} | EMA9: ₹{opp['ema_9']}
Volume: {opp['volume_ratio']}x average | RSI: {opp['rsi']}

💡 {reasoning}
"""
        if caution != "NONE":
            message += f"⚠️ {caution}\n"

        message += f"\n🛑 Max risk: ₹500 | Exit before 3:15 PM"

        self.send_message(message)

    # ─────────────────────────────────────────
    # Position Monitor Alerts
    # ─────────────────────────────────────────
    def send_target_hit(self, symbol, entry, target, profit_per_share):
        """Sent when swing position hits target"""
        message = f"""
✅ <b>TARGET HIT — {symbol}</b>

Entry: ₹{entry} → Target: ₹{target}
Profit: ₹{profit_per_share}/share 🎯

<b>EXIT NOW — Book your profit!</b>
"""
        self.send_message(message)

    def send_sl_hit(self, symbol, entry, sl, loss_per_share):
        """Sent when swing position hits stop loss"""
        message = f"""
❌ <b>STOP LOSS HIT — {symbol}</b>

Entry: ₹{entry} → SL: ₹{sl}
Loss: ₹{loss_per_share}/share

<b>EXIT IMMEDIATELY.</b>
🚫 No averaging down. No holding hope.
Accept the loss and move on.
"""
        self.send_message(message)

    def send_sl_warning(self, symbol, current_price, sl):
        """Sent when price approaches stop loss"""
        message = f"""
⚠️ <b>SL WARNING — {symbol}</b>

Current Price: ₹{current_price}
Stop Loss: ₹{sl}

Price approaching stop loss zone.
Consider early partial exit to reduce risk.
"""
        self.send_message(message)

    # ─────────────────────────────────────────
    # EOD Summary
    # ─────────────────────────────────────────
    def send_eod_summary(self, open_positions, new_setups, market_mood, bullish_count, total):
        """Evening summary sent at 3:20 PM"""
        date_str = datetime.now().strftime("%d %B %Y")

        message = f"📊 <b>EOD SUMMARY — {date_str}</b>\n"
        message += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        # Open positions
        if open_positions:
            message += f"📂 <b>OPEN SWING POSITIONS:</b>\n"
            for pos in open_positions:
                pnl_emoji = "📈" if pos["unrealised_pnl"] >= 0 else "📉"
                message += f"\n• <b>{pos['symbol']}</b>\n"
                message += f"  Entry: ₹{pos['entry']} | Current: ₹{pos['current_price']}\n"
                message += f"  P&L: {pnl_emoji} ₹{pos['unrealised_pnl']} ({pos['pnl_pct']}%)\n"
                message += f"  Target: ₹{pos['target']} | SL: ₹{pos['stop_loss']}\n"
                message += f"  Status: {pos['status']}\n"
        else:
            message += "📂 <b>No open swing positions</b>\n"

        message += f"\n━━━━━━━━━━━━━━━━━━━━\n\n"

        # New setups for tomorrow
        if new_setups:
            message += f"🔭 <b>SETUPS FOR TOMORROW:</b>\n"
            for setup in new_setups[:3]:  # Max 3
                signal_emoji = "📈" if setup["signal"] == "BUY" else "📉"
                message += f"\n• <b>{setup['symbol']}</b> {signal_emoji} Score: {setup['score']}/10\n"
                message += f"  Entry: ₹{setup['entry']} | SL: ₹{setup['stop_loss']} | Target: ₹{setup['target']}\n"
        else:
            message += "🔭 <b>No new setups for tomorrow</b>\n"

        message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📊 Market: {market_mood} ({bullish_count}/{total} above EMA)\n"
        message += f"⏰ See you tomorrow at 8:00 AM ✅"

        self.send_message(message)

    # ─────────────────────────────────────────
    # Tool Restart Alert
    # ─────────────────────────────────────────
    def send_restart_alert(self):
        """Sent when tool restarts on Railway"""
        message = f"""
⚠️ <b>TOOL RESTARTED</b>
⏰ {datetime.now().strftime("%d %B %Y — %H:%M")}

All jobs resumed ✅
Monitoring continues normally.
"""
        self.send_message(message)

    def send_holiday_alert(self, date_str):
        """Sent on market holidays"""
        message = f"""
📅 <b>MARKET HOLIDAY</b>
{date_str}

No scans today.
See you on the next trading day ✅
"""
        self.send_message(message)


# Single instance
telegram_bot = TelegramBot()