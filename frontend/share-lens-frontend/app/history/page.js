"use client";
import { useState, useEffect } from "react";
import Sidebar from "../../components/Sidebar";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function HistoryPage() {
  const [signals, setSignals] = useState([]);
  const [filter, setFilter] = useState("ALL");

  useEffect(() => {
    axios
      .get(`${API_BASE}/signals?limit=100`)
      .then((r) => setSignals(r.data.signals || []))
      .catch(() => {
        setSignals([
          {
            id: 1,
            symbol: "HDFCBANK",
            signal_type: "BUY",
            trade_type: "SWING",
            score: 8.5,
            entry: 1685,
            stop_loss: 1648,
            target: 1760,
            risk_reward: 2.1,
            confidence: "HIGH",
            rsi: 45.2,
            adx: 28.5,
            created_at: "2026-03-14T08:30:00",
          },
          {
            id: 2,
            symbol: "TATAMOTORS",
            signal_type: "BUY",
            trade_type: "SWING",
            score: 7.8,
            entry: 724,
            stop_loss: 698,
            target: 775,
            risk_reward: 1.9,
            confidence: "MEDIUM-HIGH",
            rsi: 52.1,
            adx: 31.2,
            created_at: "2026-03-14T08:30:00",
          },
          {
            id: 3,
            symbol: "RELIANCE",
            signal_type: "BUY",
            trade_type: "INTRADAY",
            score: 7.2,
            entry: 2891,
            stop_loss: 2865,
            target: 2940,
            risk_reward: 1.9,
            confidence: "MEDIUM-HIGH",
            rsi: 58.3,
            adx: 26.1,
            created_at: "2026-03-14T09:42:00",
          },
          {
            id: 4,
            symbol: "WIPRO",
            signal_type: "SELL",
            trade_type: "SWING",
            score: 7.5,
            entry: 420,
            stop_loss: 435,
            target: 395,
            risk_reward: 2.0,
            confidence: "MEDIUM",
            rsi: 68.2,
            adx: 27.4,
            created_at: "2026-03-13T08:30:00",
          },
          {
            id: 5,
            symbol: "SBIN",
            signal_type: "BUY",
            trade_type: "SWING",
            score: 8.0,
            entry: 780,
            stop_loss: 755,
            target: 830,
            risk_reward: 2.0,
            confidence: "HIGH",
            rsi: 42.1,
            adx: 29.8,
            created_at: "2026-03-13T08:30:00",
          },
          {
            id: 6,
            symbol: "INFY",
            signal_type: "BUY",
            trade_type: "INTRADAY",
            score: 7.0,
            entry: 1540,
            stop_loss: 1515,
            target: 1590,
            risk_reward: 2.0,
            confidence: "MEDIUM",
            rsi: 55.6,
            adx: 25.2,
            created_at: "2026-03-13T09:55:00",
          },
          {
            id: 7,
            symbol: "AXISBANK",
            signal_type: "BUY",
            trade_type: "SWING",
            score: 7.6,
            entry: 1120,
            stop_loss: 1088,
            target: 1184,
            risk_reward: 2.0,
            confidence: "MEDIUM-HIGH",
            rsi: 47.3,
            adx: 30.1,
            created_at: "2026-03-12T08:30:00",
          },
          {
            id: 8,
            symbol: "BAJFINANCE",
            signal_type: "SELL",
            trade_type: "SWING",
            score: 7.9,
            entry: 6800,
            stop_loss: 6935,
            target: 6530,
            risk_reward: 2.0,
            confidence: "HIGH",
            rsi: 71.2,
            adx: 33.5,
            created_at: "2026-03-12T08:30:00",
          },
        ]);
      });
  }, []);

  const filtered =
    filter === "ALL"
      ? signals
      : filter === "HIGH"
        ? signals.filter((s) => s.confidence === "HIGH")
        : signals.filter((s) => s.trade_type === filter);

  const formatDate = (d) => {
    const dt = new Date(d);
    return (
      dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short" }) +
      "  " +
      dt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
    );
  };

  const confStyle = (conf) =>
    conf === "HIGH"
      ? "tag tag-green"
      : conf === "MEDIUM-HIGH"
        ? "tag tag-yellow"
        : "tag tag-gray";

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main
        style={{
          marginLeft: "240px",
          padding: "36px",
          minHeight: "100vh",
          width: "100%",
        }}
      >
        <div style={{ marginBottom: "28px" }}>
          <h1
            style={{
              fontSize: "26px",
              fontWeight: "700",
              letterSpacing: "-0.02em",
              marginBottom: "4px",
            }}
          >
            Signal History
          </h1>
          <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            Every signal the tool has generated — {signals.length} total
          </div>
        </div>

        {/* Filters */}
        <div
          style={{
            display: "flex",
            gap: "8px",
            marginBottom: "20px",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginRight: "4px",
            }}
          >
            Filter:
          </span>
          {[
            { key: "ALL", label: "All Signals" },
            { key: "SWING", label: "Swing Only" },
            { key: "INTRADAY", label: "Intraday Only" },
            { key: "HIGH", label: "⭐ High Confidence" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              style={{
                padding: "6px 14px",
                borderRadius: "6px",
                border: `1px solid ${filter === tab.key ? "var(--accent-green)" : "var(--border)"}`,
                background:
                  filter === tab.key ? "rgba(0,201,107,0.1)" : "transparent",
                color:
                  filter === tab.key
                    ? "var(--accent-green)"
                    : "var(--text-secondary)",
                fontSize: "12px",
                fontWeight: "500",
                cursor: "pointer",
              }}
            >
              {tab.label}
            </button>
          ))}
          <span
            style={{
              marginLeft: "auto",
              fontSize: "12px",
              color: "var(--text-muted)",
            }}
          >
            {filtered.length} signals
          </span>
        </div>

        {/* Table */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--bg)" }}>
                {[
                  { label: "Date & Time", tip: "" },
                  { label: "Stock", tip: "" },
                  {
                    label: "Type",
                    tip: "Swing = hold days, Intraday = same day",
                  },
                  { label: "Signal", tip: "Buy or Sell direction" },
                  { label: "Score", tip: "Out of 10 — higher is better" },
                  { label: "Entry Price", tip: "Suggested buy/sell price" },
                  {
                    label: "Stop Loss",
                    tip: "Exit immediately if price hits this",
                  },
                  { label: "Target", tip: "Book profit at this price" },
                  {
                    label: "R/R Ratio",
                    tip: "Risk vs Reward — 1:2 means risk 1 to gain 2",
                  },
                  { label: "Confidence", tip: "AI confidence in this signal" },
                ].map((h) => (
                  <th
                    key={h.label}
                    title={h.tip}
                    style={{
                      textAlign: "left",
                      padding: "12px 14px",
                      fontSize: "11px",
                      color: "var(--text-muted)",
                      fontWeight: "600",
                      letterSpacing: "0.03em",
                      borderBottom: "1px solid var(--border)",
                      whiteSpace: "nowrap",
                      cursor: h.tip ? "help" : "default",
                    }}
                  >
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => (
                <tr
                  key={s.id}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    background:
                      i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                  }}
                >
                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "12px",
                      color: "var(--text-muted)",
                      fontFamily: "DM Mono, monospace",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatDate(s.created_at)}
                  </td>
                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "14px",
                      fontWeight: "700",
                    }}
                  >
                    {s.symbol}
                  </td>
                  <td style={{ padding: "12px 14px" }}>
                    <span className="tag tag-blue">{s.trade_type}</span>
                  </td>
                  <td style={{ padding: "12px 14px" }}>
                    <span
                      className={
                        s.signal_type === "BUY"
                          ? "tag tag-green"
                          : "tag tag-red"
                      }
                    >
                      {s.signal_type}
                    </span>
                  </td>
                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "13px",
                      fontWeight: "700",
                      color:
                        s.score >= 8
                          ? "var(--accent-green)"
                          : "var(--accent-yellow)",
                      fontFamily: "DM Mono, monospace",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.score}/10
                  </td>

                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "13px",
                      fontFamily: "DM Mono, monospace",
                      color: "var(--text-primary)",
                      fontWeight: "500",
                    }}
                  >
                    Rs. {s.entry}
                  </td>
                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "13px",
                      fontFamily: "DM Mono, monospace",
                      color: "var(--accent-red)",
                      fontWeight: "500",
                    }}
                  >
                    Rs. {s.stop_loss}
                  </td>
                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "13px",
                      fontFamily: "DM Mono, monospace",
                      color: "var(--accent-green)",
                      fontWeight: "500",
                    }}
                  >
                    Rs. {s.target}
                  </td>
                  <td
                    style={{
                      padding: "12px 14px",
                      fontSize: "13px",
                      fontFamily: "DM Mono, monospace",
                      color: "var(--accent-yellow)",
                      fontWeight: "500",
                    }}
                  >
                    1 : {s.risk_reward}
                  </td>
                  <td style={{ padding: "12px 14px" }}>
                    <span className={confStyle(s.confidence)}>
                      {s.confidence}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filtered.length === 0 && (
            <div
              style={{
                textAlign: "center",
                padding: "60px",
                color: "var(--text-secondary)",
              }}
            >
              <div style={{ fontSize: "36px", marginBottom: "12px" }}>🕐</div>
              <div style={{ fontSize: "14px" }}>
                No signals found for this filter.
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
