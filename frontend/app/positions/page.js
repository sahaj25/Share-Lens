'use client'
import { useState, useEffect } from 'react'
import Sidebar from '../../components/Sidebar'
import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function PositionCard({ position, index }) {
  const isBuy = position.signal === 'BUY'
  const pnl = position.unrealised_pnl || 0
  const pnlPct = position.pnl_pct || 0
  const isProfit = pnl >= 0
  const totalMove = Math.abs(position.target - position.entry)
  const currentMove = Math.abs((position.current_price || position.entry) - position.entry)
  const progress = Math.min(Math.round((currentMove / totalMove) * 100), 100)

  return (
    <div className="card fade-up" style={{
      animationDelay: `${index * 0.06}s`,
      marginBottom: '12px',
      borderLeft: `3px solid ${isProfit ? 'var(--accent-green)' : 'var(--accent-red)'}`
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <span style={{ fontSize: '20px', fontWeight: '700' }}>{position.symbol}</span>
            <span className={isBuy ? 'tag tag-green' : 'tag tag-red'}>{position.signal}</span>
            <span className="tag tag-blue">{position.trade_type}</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {position.quantity} shares · Capital used: Rs. {position.capital_used?.toLocaleString()}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontSize: '22px', fontWeight: '700',
            color: isProfit ? 'var(--accent-green)' : 'var(--accent-red)',
            fontFamily: 'DM Mono, monospace'
          }}>
            {isProfit ? '+' : ''}Rs. {Math.abs(pnl)}
          </div>
          <div style={{ fontSize: '12px', color: isProfit ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            {isProfit ? '▲' : '▼'} {Math.abs(pnlPct)}% unrealised
          </div>
        </div>
      </div>

      {/* Levels */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '1px', background: 'var(--border)',
        borderRadius: '8px', overflow: 'hidden', marginBottom: '14px'
      }}>
        {[
          { label: 'Entry Price', value: `Rs. ${position.entry}`, color: 'var(--text-primary)' },
          { label: 'Current Price', value: `Rs. ${position.current_price || position.entry}`, color: isProfit ? 'var(--accent-green)' : 'var(--accent-red)' },
          { label: 'Target', value: `Rs. ${position.target}`, color: 'var(--accent-green)' },
          { label: 'Stop Loss', value: `Rs. ${position.stop_loss}`, color: 'var(--accent-red)' },
        ].map(item => (
          <div key={item.label} style={{ background: 'var(--bg-elevated)', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: '500' }}>{item.label}</div>
            <div style={{ fontSize: '13px', fontWeight: '700', color: item.color, fontFamily: 'DM Mono, monospace' }}>{item.value}</div>
          </div>
        ))}
      </div>

      {/* Progress */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Progress to target</span>
          <span style={{ fontSize: '12px', fontWeight: '600', color: isProfit ? 'var(--accent-green)' : 'var(--text-muted)' }}>
            {progress}%
          </span>
        </div>
        <div style={{ height: '6px', background: 'var(--bg-elevated)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${progress}%`,
            background: isProfit ? 'var(--accent-green)' : 'var(--accent-red)',
            borderRadius: '3px', transition: 'width 0.5s ease'
          }} />
        </div>
      </div>
    </div>
  )
}

export default function PositionsPage() {
  const [positions, setPositions] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchPositions = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${API_BASE}/positions/open`)
      setPositions(res.data.positions || [])
    } catch {
      setPositions([
        { id: 1, symbol: 'HDFCBANK', signal: 'BUY', trade_type: 'SWING', entry: 1685, current_price: 1721, target: 1760, stop_loss: 1648, quantity: 4, capital_used: 6740, unrealised_pnl: 144, pnl_pct: 2.1 },
        { id: 2, symbol: 'TATAMOTORS', signal: 'BUY', trade_type: 'SWING', entry: 724, current_price: 712, target: 775, stop_loss: 698, quantity: 10, capital_used: 7240, unrealised_pnl: -120, pnl_pct: -1.6 },
      ])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPositions()
    const interval = setInterval(fetchPositions, 30000)
    return () => clearInterval(interval)
  }, [])

  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealised_pnl || 0), 0)
  const isProfit = totalPnl >= 0

  return (
    <div style={{ display: 'flex' }}>
      <Sidebar />
      <main style={{ marginLeft: '240px', padding: '36px', minHeight: '100vh', width: '100%'}}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px' }}>
          <div>
            <h1 style={{ fontSize: '26px', fontWeight: '700', letterSpacing: '-0.02em', marginBottom: '4px' }}>
              Open Positions
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Prices update every 30 seconds during market hours
            </div>
          </div>
          <button onClick={fetchPositions} style={{
            background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
            border: '1px solid var(--border)', borderRadius: '8px',
            padding: '10px 20px', fontSize: '13px', fontWeight: '600', cursor: 'pointer'
          }}>
            🔄 Refresh
          </button>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '24px' }}>
          {[
            { label: 'Open Trades', value: positions.length, color: 'var(--text-primary)' },
            { label: 'Total Unrealised P&L', value: `${isProfit ? '+' : ''}Rs. ${Math.abs(totalPnl).toFixed(0)}`, color: isProfit ? 'var(--accent-green)' : 'var(--accent-red)' },
            { label: 'In Profit', value: positions.filter(p => p.unrealised_pnl >= 0).length, color: 'var(--accent-green)' },
            { label: 'In Loss', value: positions.filter(p => p.unrealised_pnl < 0).length, color: 'var(--accent-red)' },
          ].map(stat => (
            <div key={stat.label} className="card">
              <div style={{ fontSize: '24px', fontWeight: '700', color: stat.color, fontFamily: 'DM Mono, monospace', marginBottom: '4px' }}>
                {stat.value}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500' }}>{stat.label}</div>
            </div>
          ))}
        </div>

        {positions.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>📂</div>
            <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '6px' }}>No open positions</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Go to the Scanner page to find trade setups.
            </div>
          </div>
        ) : (
          positions.map((p, i) => <PositionCard key={p.id} position={p} index={i} />)
        )}
      </main>
    </div>
  )
}