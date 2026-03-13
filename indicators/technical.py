import pandas as pd

import numpy as np

import ta


class TechnicalIndicators:

    def add_all_indicators(self, df):

        """Add all indicators to dataframe at once"""

        df = self.add_ema(df)

        df = self.add_rsi(df)

        df = self.add_adx(df)

        df = self.add_vwap(df)

        df = self.add_volume_analysis(df)

        df = self.add_support_resistance(df)

        return df

    # ─────────────────────────────────────────

    # EMA — Exponential Moving Average

    # ─────────────────────────────────────────

    def add_ema(self, df):

        """

        EMA 9 → intraday momentum

        EMA 20/50 → swing trend direction

        EMA 50/200 → positional trend

        """

        df["ema_9"] = ta.trend.ema_indicator(df["close"], window=9)

        df["ema_20"] = ta.trend.ema_indicator(df["close"], window=20)

        df["ema_50"] = ta.trend.ema_indicator(df["close"], window=50)

        df["ema_200"] = ta.trend.ema_indicator(df["close"], window=200)

        return df

    # ─────────────────────────────────────────

    # RSI — Relative Strength Index

    # ─────────────────────────────────────────

    def add_rsi(self, df):

        """

        RSI 14 → momentum + overbought/oversold

        Above 70 = overbought

        Below 40 = oversold bounce opportunity

        40-60 = neutral good entry zone

        """

        df["rsi"] = ta.momentum.rsi(df["close"], window=14)

        return df

    # ─────────────────────────────────────────

    # ADX — Average Directional Index

    # ─────────────────────────────────────────

    def add_adx(self, df):

        """

        ADX 14 → trend strength

        Above 25 = strong trend → trust the signal

        Below 25 = weak trend → ignore signal

        """

        df["adx"] = ta.trend.adx(

            df["high"], df["low"], df["close"], window=14

        )

        df["adx_pos"] = ta.trend.adx_pos(

            df["high"], df["low"], df["close"], window=14

        )

        df["adx_neg"] = ta.trend.adx_neg(

            df["high"], df["low"], df["close"], window=14

        )

        return df

    # ─────────────────────────────────────────

    # VWAP — Volume Weighted Average Price

    # ─────────────────────────────────────────

    def add_vwap(self, df):

        """

        VWAP → most important intraday indicator

        Price above VWAP = bullish

        Price below VWAP = bearish

        """

        df["vwap"] = ta.volume.volume_weighted_average_price(

            df["high"], df["low"], df["close"], df["volume"]

        )

        return df

    # ─────────────────────────────────────────

    # Volume Analysis

    # ─────────────────────────────────────────

    def add_volume_analysis(self, df):

        """

        Volume confirmation — critical filter

        Volume above 20-day avg = confirmed signal

        Volume spike 1.5x+ = strong confirmation

        """

        df["volume_ma_20"] = df["volume"].rolling(window=20).mean()

        df["volume_ratio"] = df["volume"] / df["volume_ma_20"]

        df["volume_spike"] = df["volume_ratio"] >= 1.5

        return df

    # ─────────────────────────────────────────

    # Support & Resistance

    # ─────────────────────────────────────────

    def add_support_resistance(self, df):

        """

        Auto detect key S/R levels

        Uses recent highs/lows over 20 periods

        Price near S/R = high conviction signal

        """

        # Rolling 20 period high/low

        df["resistance"] = df["high"].rolling(window=20).max()

        df["support"] = df["low"].rolling(window=20).min()

        # How close is current price to S/R (as % distance)

        df["dist_to_resistance"] = (

                (df["resistance"] - df["close"]) / df["close"] * 100

        )

        df["dist_to_support"] = (

                (df["close"] - df["support"]) / df["close"] * 100

        )

        # Price near support = within 1.5%

        df["near_support"] = df["dist_to_support"] <= 1.5

        # Price near resistance = within 1.5%

        df["near_resistance"] = df["dist_to_resistance"] <= 1.5

        # Breakout = price breaking above 20 period high with volume

        df["breakout"] = (

                (df["close"] > df["resistance"].shift(1)) &

                (df["volume_spike"] == True)

        )

        return df

    # ─────────────────────────────────────────

    # Signal Checks — used by scanners

    # ─────────────────────────────────────────

    def check_swing_trend(self, df):

        """EMA 20 above EMA 50 = bullish swing trend"""

        latest = df.iloc[-1]

        if latest["ema_20"] > latest["ema_50"]:

            return "BULLISH"

        elif latest["ema_20"] < latest["ema_50"]:

            return "BEARISH"

        return "NEUTRAL"

    def check_trend_strength(self, df):

        """ADX above 25 = strong trend"""

        latest = df.iloc[-1]

        return latest["adx"] >= 25

    def check_rsi_zone(self, df):

        """

        Returns entry quality based on RSI

        GOOD = 40-60 (neutral zone)

        OVERSOLD = below 40 (bounce opportunity)

        OVERBOUGHT = above 70 (avoid)

        """

        latest = df.iloc[-1]

        rsi = latest["rsi"]

        if rsi < 40:

            return "OVERSOLD"

        elif rsi <= 60:

            return "GOOD"

        elif rsi <= 70:

            return "NEUTRAL"

        return "OVERBOUGHT"

    def check_volume_confirmation(self, df):

        """Volume above 20-day average"""

        latest = df.iloc[-1]

        return latest["volume_ratio"] >= 1.0

    def check_intraday_signal(self, df):

        """

        Intraday signal check:

        Price above VWAP + above EMA9 + volume spike = BUY

        Price below VWAP + below EMA9 + volume spike = SELL

        """

        latest = df.iloc[-1]

        price = latest["close"]

        vwap = latest["vwap"]

        ema9 = latest["ema_9"]

        volume_spike = latest["volume_spike"]

        if price > vwap and price > ema9 and volume_spike:

            return "BUY"

        elif price < vwap and price < ema9 and volume_spike:

            return "SELL"

        return "NONE"

    def calculate_sl_target(self, df, signal, risk_reward=2.0):

        """

        Auto calculate stop loss and target

        Based on recent support/resistance levels

        """

        latest = df.iloc[-1]

        price = latest["close"]

        if signal == "BUY":

            stop_loss = round(latest["support"] * 0.995, 2)

            risk = price - stop_loss

            target = round(price + (risk * risk_reward), 2)

        elif signal == "SELL":

            stop_loss = round(latest["resistance"] * 1.005, 2)

            risk = stop_loss - price

            target = round(price - (risk * risk_reward), 2)

        else:

            return None

        actual_rr = round(

            abs(target - price) / abs(price - stop_loss), 2

        )

        return {

            "entry": round(price, 2),

            "stop_loss": stop_loss,

            "target": target,

            "risk_reward": actual_rr,

            "risk_amount": round(abs(price - stop_loss), 2)

        }


# Single instance

indicators = TechnicalIndicators()


