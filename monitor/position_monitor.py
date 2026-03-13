from datetime import datetime

from data.angel_api import angel

from alerts.telegram_bot import telegram_bot

from database.queries import db_queries


class PositionMonitor:

    def __init__(self):

        self.warned_symbols = set()  # Track already warned positions

    def monitor_all(self):

        """

        Main function — monitors all open swing positions

        Runs every 1 minute during market hours

        """

        # Fetch all open positions from database

        open_positions = db_queries.get_open_positions()

        if not open_positions:
            return

        print(f"👁 Monitoring {len(open_positions)} open position(s)...")

        for position in open_positions:

            try:

                self.check_position(position)

            except Exception as e:

                print(f"⚠️ Error monitoring {position['symbol']}: {e}")

                continue

    def check_position(self, position):

        """

        Check a single position against live price

        Sends alerts if target/SL hit or approaching

        """

        symbol = position["symbol"]

        entry = position["entry"]

        stop_loss = position["stop_loss"]

        target = position["target"]

        signal = position["signal"]

        # Get live price

        current_price = angel.get_live_price(symbol)

        if not current_price:
            print(f"⚠️ Could not fetch price for {symbol}")

            return

        # Calculate P&L

        if signal == "BUY":

            profit_per_share = round(current_price - entry, 2)

            pnl_pct = round((profit_per_share / entry) * 100, 2)

        else:

            profit_per_share = round(entry - current_price, 2)

            pnl_pct = round((profit_per_share / entry) * 100, 2)

        print(f"  {symbol}: ₹{current_price} | P&L: ₹{profit_per_share} ({pnl_pct}%)")

        # Update position in database

        db_queries.update_position_price(

            symbol=symbol,

            current_price=current_price,

            unrealised_pnl=profit_per_share,

            pnl_pct=pnl_pct

        )

        # ── TARGET HIT CHECK ──

        if signal == "BUY" and current_price >= target:

            print(f"🎯 TARGET HIT — {symbol}")

            telegram_bot.send_target_hit(

                symbol=symbol,

                entry=entry,

                target=target,

                profit_per_share=profit_per_share

            )

            db_queries.close_position(

                symbol=symbol,

                exit_price=current_price,

                exit_reason="TARGET_HIT"

            )

            self.warned_symbols.discard(symbol)

            return

        elif signal == "SELL" and current_price <= target:

            print(f"🎯 TARGET HIT — {symbol}")

            telegram_bot.send_target_hit(

                symbol=symbol,

                entry=entry,

                target=target,

                profit_per_share=profit_per_share

            )

            db_queries.close_position(

                symbol=symbol,

                exit_price=current_price,

                exit_reason="TARGET_HIT"

            )

            self.warned_symbols.discard(symbol)

            return

        # ── STOP LOSS HIT CHECK ──

        if signal == "BUY" and current_price <= stop_loss:

            print(f"❌ SL HIT — {symbol}")

            telegram_bot.send_sl_hit(

                symbol=symbol,

                entry=entry,

                sl=stop_loss,

                loss_per_share=abs(profit_per_share)

            )

            db_queries.close_position(

                symbol=symbol,

                exit_price=current_price,

                exit_reason="SL_HIT"

            )

            self.warned_symbols.discard(symbol)

            return

        elif signal == "SELL" and current_price >= stop_loss:

            print(f"❌ SL HIT — {symbol}")

            telegram_bot.send_sl_hit(

                symbol=symbol,

                entry=entry,

                sl=stop_loss,

                loss_per_share=abs(profit_per_share)

            )

            db_queries.close_position(

                symbol=symbol,

                exit_price=current_price,

                exit_reason="SL_HIT"

            )

            self.warned_symbols.discard(symbol)

            return

        # ── SL WARNING CHECK ──

        # Warn when price is within 1% of stop loss

        sl_distance_pct = abs(current_price - stop_loss) / current_price * 100

        if sl_distance_pct <= 1.0 and symbol not in self.warned_symbols:

            print(f"⚠️ SL WARNING — {symbol}")

            telegram_bot.send_sl_warning(

                symbol=symbol,

                current_price=current_price,

                sl=stop_loss

            )

            self.warned_symbols.add(symbol)

        # Reset warning if price moves away from SL

        elif sl_distance_pct > 2.0 and symbol in self.warned_symbols:

            self.warned_symbols.discard(symbol)

    def get_open_positions_summary(self):

        """

        Returns formatted summary of all open positions

        Used in EOD summary

        """

        open_positions = db_queries.get_open_positions()

        if not open_positions:
            return []

        summary = []

        for position in open_positions:

            symbol = position["symbol"]

            current_price = angel.get_live_price(symbol)

            if not current_price:
                current_price = position.get("last_price", position["entry"])

            entry = position["entry"]

            signal = position["signal"]

            if signal == "BUY":

                unrealised_pnl = round(current_price - entry, 2)

            else:

                unrealised_pnl = round(entry - current_price, 2)

            pnl_pct = round((unrealised_pnl / entry) * 100, 2)

            # Position status

            if pnl_pct >= 2:

                status = "Looking good 📈 — consider trailing SL"

            elif pnl_pct <= -1.5:

                status = "Near SL ⚠️ — watch closely"

            else:

                status = "In progress ➡️ — hold"

            summary.append({

                "symbol": symbol,

                "entry": entry,

                "current_price": current_price,

                "target": position["target"],

                "stop_loss": position["stop_loss"],

                "unrealised_pnl": unrealised_pnl,

                "pnl_pct": pnl_pct,

                "status": status,

                "signal": signal

            })

        return summary


# Single instance

position_monitor = PositionMonitor()
