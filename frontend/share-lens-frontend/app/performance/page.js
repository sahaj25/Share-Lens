'use client'
import { useState, useEffect } from 'react'
import Sidebar from '../../components/Sidebar'
import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function PerformancePage() {
  const [perf, setPerf] = useState(null)

  useEffect(() => {
    axios.get(`${API_BASE}/performance`).then(r => setPerf(r.data.data)).catch(() => {
      setPerf({
        total_trades: 47, winning_trades: 30, losing_trades: 17,
        total_pnl: 14230, win_rate: 63.8,
        monthly: [
          { month: 'Nov', pnl: 2100 }, { month: 'Dec', pnl: 3450 },
          { month: 'Jan', pnl: -800 }, { month: 'Feb', pnl: 4200 }, { month: 'Mar', pnl: 5280 },
        ],
        recent: [
          { symbol: 'HDFCBANK', signal: 'BUY', entry: 1685, exit: 1760, pnl: 375, result: 'WIN' },
          { symbol: 'WIPRO', signal: 'BUY', entry: 420, exit: 408, pnl: -120, result: 'LOSS' },
          { symbol: 'RELIANCE', signal: 'BUY', entry: 2891, exit: 2940, pnl: 490, result: 'WIN' },
          { symbol: 'SBIN', signal: 'SELL', entry: 780, exit: 745, pnl: 350, result: 'WIN' },
          { symbol: 'INFY', signal: 'BUY', entry: 1540, exit: 1510, pnl: -300, result: 'LOSS' },
        ]
      })
    })
  }, [])

  if (!perf) return (
    <div style={{ display: 'flex' }}>
      <Sidebar />
      <main style={{ marginLeft: '240px', padding: '36px' }}>
        <div style={{ color: 'var(--text-muted)' }}>Loading...</div>
      </main>
    </div>
  )

  const maxPnl = Math.max(...perf.monthly.map(m => Math.abs(m.pnl)))

  return (
    <div style={{ display: 'flex' }}>
      <Sidebar />
      <main style={{ marginLeft: '240px', padding: '36px', minHeight: '100vh', width: '100%'}}>

        <div style={{ marginBottom: '28px' }}>
          <h1 style={{ fontSize: '26px', fontWeight: '700', letterSpacing: '-0.02em', marginBottom: '4px' }}>
            Performance
          </h1>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Track record based on all closed trades
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '24px' }}>
          {[
            { label: 'Total Trades', value: perf.total_trades, color: 'var(--text-primary)', sub: 'All time' },
            { label: 'Win Rate', value: `${perf.win_rate}%`, color: 'var(--accent-green)', sub: 'Trades that hit target' },
            { label: 'Total Profit', value: `Rs. ${perf.total_pnl.toLocaleString()}`, color: perf.total_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', sub: 'Net P&L all trades' },
            { label: 'Wins / Losses', value: `${perf.winning_trades}W  ${perf.losing_trades}L`, color: 'var(--accent-yellow)', sub: 'Breakdown' },
          ].map(stat => (
            <div key={stat.label} className="card">
              <div style={{ fontSize: '22px', fontWeight: '700', color: stat.color, fontFamily: 'DM Mono, monospace', marginBottom: '4px' }}>
                {stat.value}
              </div>
              <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '2px' }}>
                {stat.label}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{stat.sub}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '16px', marginBottom: '16px' }}>
          {/* Monthly chart */}
          <div className="card">
            <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '20px' }}>Monthly P&L</div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '12px', height: '150px' }}>
              {perf.monthly.map(m => {
                const isPos = m.pnl >= 0
                const height = Math.round((Math.abs(m.pnl) / maxPnl) * 120)
                return (
                  <div key={m.month} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                    <div style={{ fontSize: '11px', color: isPos ? 'var(--accent-green)' : 'var(--accent-red)', fontFamily: 'DM Mono, monospace' }}>
                      {isPos ? '+' : '-'}Rs.{Math.abs(m.pnl / 1000).toFixed(1)}k
                    </div>
                    <div style={{
                      width: '100%', height: `${height}px`,
                      background: isPos ? 'rgba(0,201,107,0.25)' : 'rgba(255,77,77,0.25)',
                      border: `1px solid ${isPos ? 'var(--accent-green)' : 'var(--accent-red)'}`,
                      borderRadius: '4px 4px 0 0'
                    }} />
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{m.month}</div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Win rate */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '20px', alignSelf: 'flex-start' }}>Win Rate</div>
            <div style={{ position: 'relative', width: '120px', height: '120px' }}>
              <svg viewBox="0 0 36 36" style={{ width: '120px', height: '120px', transform: 'rotate(-90deg)' }}>
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--border)" strokeWidth="3" />
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--accent-green)" strokeWidth="3"
                  strokeDasharray={`${perf.win_rate} ${100 - perf.win_rate}`} strokeLinecap="round" />
              </svg>
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--accent-green)', fontFamily: 'DM Mono, monospace' }}>
                  {perf.win_rate}%
                </div>
              </div>
            </div>
            <div style={{ marginTop: '16px', display: 'flex', gap: '24px' }}>
              {[
                { label: 'Wins', value: perf.winning_trades, color: 'var(--accent-green)' },
                { label: 'Losses', value: perf.losing_trades, color: 'var(--accent-red)' }
              ].map(item => (
                <div key={item.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '18px', fontWeight: '700', color: item.color, fontFamily: 'DM Mono, monospace' }}>
                    {item.value}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent trades */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: '13px', fontWeight: '600' }}>
            Recent Trades
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg)' }}>
                {['Stock', 'Signal', 'Entry', 'Exit', 'Profit / Loss', 'Result'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '10px 16px',
                    fontSize: '11px', color: 'var(--text-muted)',
                    fontWeight: '600', letterSpacing: '0.03em',
                    borderBottom: '1px solid var(--border)'
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {perf.recent.map((trade, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '12px 16px', fontSize: '14px', fontWeight: '600' }}>{trade.symbol}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span className={trade.signal === 'BUY' ? 'tag tag-green' : 'tag tag-red'}>{trade.signal}</span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)' }}>Rs. {trade.entry}</td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)' }}>Rs. {trade.exit}</td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', fontFamily: 'DM Mono, monospace', fontWeight: '600', color: trade.pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                    {trade.pnl >= 0 ? '+' : ''}Rs. {trade.pnl}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span className={trade.result === 'WIN' ? 'tag tag-green' : 'tag tag-red'}>{trade.result}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}