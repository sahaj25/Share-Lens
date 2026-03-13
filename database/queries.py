from datetime import datetime
from database.models import (
    Signal, Position, DailyPerformance,
    SessionLocal
)


class DBQueries:

    def get_db(self):
        return SessionLocal()

    # ─────────────────────────────────────────
    # Signal queries
    # ─────────────────────────────────────────
    def save_signal(self, signal_data, ai_analysis, trade_type):
        """Save every generated signal to database"""
        db = self.get_db()
        try:
            signal = Signal(
                symbol=signal_data["symbol"],
                signal_type=signal_data["signal"],
                trade_type=trade_type,
                score=signal_data["score"],
                entry=signal_data["entry"],
                stop_loss=signal_data["stop_loss"],
                target=signal_data.get("target", signal_data.get("target_2")),
                risk_reward=signal_data["risk_reward"],
                confidence=ai_analysis.get("confidence", "MEDIUM"),
                reasoning=ai_analysis.get("reasoning", ""),
                caution=ai_analysis.get("caution", "NONE"),
                rsi=signal_data.get("rsi", 0),
                adx=signal_data.get("adx", 0),
                volume_ratio=signal_data.get("volume_ratio", 0)
            )
            db.add(signal)
            db.commit()
            print(f"✅ Signal saved: {signal_data['symbol']}")
        except Exception as e:
            print(f"❌ Error saving signal: {e}")
            db.rollback()
        finally:
            db.close()

    def get_all_signals(self, trade_type=None, limit=50):
        """Fetch recent signals"""
        db = self.get_db()
        try:
            query = db.query(Signal)
            if trade_type:
                query = query.filter(Signal.trade_type == trade_type)
            return query.order_by(
                Signal.created_at.desc()
            ).limit(limit).all()
        finally:
            db.close()

    # ─────────────────────────────────────────
    # Position queries
    # ─────────────────────────────────────────
    def open_position(self, signal_data, quantity, capital_used, trade_type):
        """Log when you enter a trade"""
        db = self.get_db()
        try:
            position = Position(
                symbol=signal_data["symbol"],
                signal=signal_data["signal"],
                trade_type=trade_type,
                entry=signal_data["entry"],
                stop_loss=signal_data["stop_loss"],
                target=signal_data.get("target", signal_data.get("target_2")),
                quantity=quantity,
                capital_used=capital_used,
                current_price=signal_data["entry"],
                is_open=True
            )
            db.add(position)
            db.commit()
            print(f"✅ Position opened: {signal_data['symbol']}")
        except Exception as e:
            print(f"❌ Error opening position: {e}")
            db.rollback()
        finally:
            db.close()

    def get_open_positions(self):
        """Get all currently open positions"""
        db = self.get_db()
        try:
            positions = db.query(Position).filter(
                Position.is_open == True
            ).all()
            return [
                {
                    "id": p.id,
                    "symbol": p.symbol,
                    "signal": p.signal,
                    "trade_type": p.trade_type,
                    "entry": p.entry,
                    "stop_loss": p.stop_loss,
                    "target": p.target,
                    "quantity": p.quantity,
                    "capital_used": p.capital_used,
                    "current_price": p.current_price,
                    "unrealised_pnl": p.unrealised_pnl,
                    "pnl_pct": p.pnl_pct
                }
                for p in positions
            ]
        finally:
            db.close()

    def update_position_price(self, symbol, current_price, unrealised_pnl, pnl_pct):
        """Update live price and P&L of open position"""
        db = self.get_db()
        try:
            position = db.query(Position).filter(
                Position.symbol == symbol,
                Position.is_open == True
            ).first()
            if position:
                position.current_price = current_price
                position.unrealised_pnl = unrealised_pnl
                position.pnl_pct = pnl_pct
                db.commit()
        except Exception as e:
            print(f"❌ Error updating position: {e}")
            db.rollback()
        finally:
            db.close()

    def close_position(self, symbol, exit_price, exit_reason):
        """Close a position when target/SL hit"""
        db = self.get_db()
        try:
            position = db.query(Position).filter(
                Position.symbol == symbol,
                Position.is_open == True
            ).first()
            if position:
                position.is_open = False
                position.exit_price = exit_price
                position.exit_reason = exit_reason
                position.closed_at = datetime.now()
                db.commit()
                print(f"✅ Position closed: {symbol} — {exit_reason}")
                self.update_daily_performance(position)
        except Exception as e:
            print(f"❌ Error closing position: {e}")
            db.rollback()
        finally:
            db.close()

    # ─────────────────────────────────────────
    # Performance queries
    # ─────────────────────────────────────────
    def update_daily_performance(self, position):
        """Update daily P&L when a trade closes"""
        db = self.get_db()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            perf = db.query(DailyPerformance).filter(
                DailyPerformance.date == today
            ).first()

            pnl = (position.exit_price - position.entry) * position.quantity
            if position.signal == "SELL":
                pnl = -pnl

            if not perf:
                perf = DailyPerformance(
                    date=today,
                    total_trades=1,
                    winning_trades=1 if pnl > 0 else 0,
                    losing_trades=1 if pnl <= 0 else 0,
                    total_pnl=pnl
                )
                db.add(perf)
            else:
                perf.total_trades += 1
                if pnl > 0:
                    perf.winning_trades += 1
                else:
                    perf.losing_trades += 1
                perf.total_pnl += pnl
                perf.win_rate = round(
                    perf.winning_trades / perf.total_trades * 100, 2
                )

            db.commit()
            print(f"✅ Daily performance updated: ₹{pnl}")

        except Exception as e:
            print(f"❌ Error updating performance: {e}")
            db.rollback()
        finally:
            db.close()

    def get_performance_summary(self):
        """Get overall performance stats"""
        db = self.get_db()
        try:
            all_closed = db.query(Position).filter(
                Position.is_open == False
            ).all()

            if not all_closed:
                return None

            total_trades = len(all_closed)
            winning = sum(1 for p in all_closed if p.exit_reason == "TARGET_HIT")
            losing = sum(1 for p in all_closed if p.exit_reason == "SL_HIT")
            total_pnl = sum(
                (p.exit_price - p.entry) * p.quantity
                if p.signal == "BUY"
                else (p.entry - p.exit_price) * p.quantity
                for p in all_closed
            )
            win_rate = round(winning / total_trades * 100, 2)

            return {
                "total_trades": total_trades,
                "winning_trades": winning,
                "losing_trades": losing,
                "total_pnl": round(total_pnl, 2),
                "win_rate": win_rate
            }
        finally:
            db.close()


# Single instance
db_queries = DBQueries()