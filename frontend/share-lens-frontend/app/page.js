'use client'
import { useState, useEffect } from 'react'
import Sidebar from '../components/Sidebar'
import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function ScoreBar({ score }) {
  const color = score >= 8 ? 'var(--accent-green)' : score >= 7 ? 'var(--accent-yellow)' : 'var(--accent-red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{ flex: 1, height: '6px', background: 'var(--bg-elevated)', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{ width: `${score * 10}%`, height: '100%', background: color, borderRadius: '3px', transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ fontSize: '14px', fontWeight: '700', color, fontFamily: 'DM Mono, monospace', minWidth: '32px' }}>
        {score}
      </span>
    </div>
  )
}

function SignalCard({ signal, index }) {
  const isBuy = signal.signal_type === 'BUY'
  const conf = signal.confidence
  const confColor = conf === 'HIGH' ? 'var(--accent-green)' : conf === 'MEDIUM-HIGH' ? 'var(--accent-yellow)' : 'var(--text-muted)'

  return (
    <div className="card fade-up" style={{
      animationDelay: `${index * 0.06}s`,
      marginBottom: '12px',
      borderLeft: `3px solid ${isBuy ? 'var(--accent-green)' : 'var(--accent-red)'}`
    }}>

      {/* Top row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span style={{ fontSize: '20px', fontWeight: '700' }}>{signal.symbol}</span>
            <span className={isBuy ? 'tag tag-green' : 'tag tag-red'}>{signal.signal_type}</span>
            <span className="tag tag-blue">{signal.trade_type}</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Signal strength
          </div>
          <div style={{ marginTop: '6px', width: '200px' }}>
            <ScoreBar score={signal.score} />
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}> Confidence</div>
          <div style={{ fontSize: '14px', fontWeight: '600', color: confColor }}>
            {conf === 'HIGH' ? '🟢 High' : conf === 'MEDIUM-HIGH' ? '🟡 Medium-High' : '⚪ Medium'}
          </div>
        </div>
      </div>

      {/* Trade levels */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '1px', background: 'var(--border)',
        borderRadius: '8px', overflow: 'hidden',
        marginBottom: '14px'
      }}>
        {[
          { label: 'Buy At', value: `Rs. ${signal.entry}`, sub: 'Entry price', color: 'var(--text-primary)' },
          { label: 'Stop Loss', value: `Rs. ${signal.stop_loss}`, sub: 'Exit if hits this', color: 'var(--accent-red)' },
          { label: 'Target', value: `Rs. ${signal.target}`, sub: 'Book profit here', color: 'var(--accent-green)' },
          { label: 'Risk/Reward', value: `1 : ${signal.risk_reward}`, sub: 'Profit vs risk ratio', color: 'var(--accent-yellow)' },
        ].map(item => (
          <div key={item.label} style={{ background: 'var(--bg-elevated)', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: '500' }}>
              {item.label}
            </div>
            <div style={{ fontSize: '14px', fontWeight: '700', color: item.color, fontFamily: 'DM Mono, monospace' }}>
              {item.value}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {item.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Indicators row */}
      <div style={{
        display: 'flex', gap: '20px', paddingTop: '12px',
        borderTop: '1px solid var(--border)', marginBottom: '12px'
      }}>
        {[
          { label: 'RSI', value: signal.rsi, tip: 'Below 40 = oversold (good buy zone)' },
          { label: 'ADX', value: signal.adx, tip: 'Above 25 = strong trend' },
          { label: 'Volume', value: `${signal.volume_ratio}x`, tip: 'Higher = stronger signal' },
        ].map(ind => (
          <div key={ind.label} title={ind.tip}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>{ind.label}</div>
            <div style={{ fontSize: '13px', fontWeight: '600', fontFamily: 'DM Mono, monospace' }}>{ind.value}</div>
          </div>
        ))}
      </div>

      {/* AI Reasoning */}
      {signal.reasoning && (
        <div style={{
          background: 'var(--bg-elevated)', borderRadius: '8px',
          padding: '12px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6'
        }}>
          <span style={{ fontSize: '11px', fontWeight: '600', color: confColor, marginRight: '6px' }}>
            ANALYSIS:
          </span>
          {signal.reasoning}
        </div>
      )}
    </div>
  )
}

export default function ScannerPage() {
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [filter, setFilter] = useState('ALL')

  const fetchSignals = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${API_BASE}/signals?limit=20`)
      setSignals(res.data.signals || [])
      setLastUpdated(new Date().toLocaleTimeString())
    } catch {
      setSignals([
        { id: 1, symbol: 'HDFCBANK', signal_type: 'BUY', trade_type: 'SWING', score: 8.5, entry: 1685, stop_loss: 1648, target: 1760, risk_reward: 2.1, confidence: 'HIGH', rsi: 45.2, adx: 28.5, volume_ratio: 1.8, reasoning: 'EMA crossover confirmed with RSI in oversold zone. ADX at 28.5 shows strong trend. Price sitting at key support level with above-average volume — high probability setup.' },
        { id: 2, symbol: 'TATAMOTORS', signal_type: 'BUY', trade_type: 'SWING', score: 7.8, entry: 724, stop_loss: 698, target: 775, risk_reward: 1.9, confidence: 'MEDIUM-HIGH', rsi: 52.1, adx: 31.2, volume_ratio: 2.1, reasoning: 'Breakout above key resistance at 720 with 2.1x volume spike. ADX strong at 31. RSI neutral — room to run upward.' },
        { id: 3, symbol: 'RELIANCE', signal_type: 'BUY', trade_type: 'INTRADAY', score: 7.2, entry: 2891, stop_loss: 2865, target: 2940, risk_reward: 1.9, confidence: 'MEDIUM-HIGH', rsi: 58.3, adx: 26.1, volume_ratio: 1.6, reasoning: 'VWAP reclaim at open with EMA9 crossover. Volume 1.6x above average. Clean intraday setup — exit before 3:15 PM.' },
      ])
      setLastUpdated(new Date().toLocaleTimeString() + ' (demo)')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 60000)
    return () => clearInterval(interval)
  }, [])

  const filtered = filter === 'ALL' ? signals : signals.filter(s => s.trade_type === filter)

  return (
    <div style={{ display: 'flex' }}>
      <Sidebar />
      <main style={{ marginLeft: '240px', padding: '36px', minHeight: '100vh', width: '100%'}}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px' }}>
          <div>
            <h1 style={{ fontSize: '26px', fontWeight: '700', letterSpacing: '-0.02em', marginBottom: '4px' }}>
              Signal Scanner
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Nifty 50 stocks scanned every morning at 8:30 AM
              {lastUpdated && <span style={{ marginLeft: '12px' }}>· Last updated {lastUpdated}</span>}
            </div>
          </div>
          <button onClick={fetchSignals} disabled={loading} style={{
            background: loading ? 'var(--bg-elevated)' : 'var(--accent-green)',
            color: loading ? 'var(--text-muted)' : '#000',
            border: 'none', borderRadius: '8px',
            padding: '10px 20px', fontSize: '13px', fontWeight: '600',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease'
          }}>
            {loading ? 'Scanning...' : '⚡  Run Scan Now'}
          </button>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '24px' }}>
          {[
            { label: 'Total Signals Today', value: signals.length, color: 'var(--text-primary)' },
            { label: 'Swing Trades', value: signals.filter(s => s.trade_type === 'SWING').length, color: 'var(--accent-blue)', tip: 'Hold 3-7 days' },
            { label: 'Intraday Trades', value: signals.filter(s => s.trade_type === 'INTRADAY').length, color: 'var(--accent-yellow)', tip: 'Exit same day' },
            { label: 'High Confidence', value: signals.filter(s => s.confidence === 'HIGH').length, color: 'var(--accent-green)', tip: 'Best setups only' },
          ].map(stat => (
            <div key={stat.label} className="card" title={stat.tip || ''}>
              <div style={{ fontSize: '28px', fontWeight: '700', color: stat.color, fontFamily: 'DM Mono, monospace', marginBottom: '4px' }}>
                {stat.value}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500' }}>{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginRight: '4px' }}>Filter:</span>
          {[
            { key: 'ALL', label: 'All Signals' },
            { key: 'SWING', label: 'Swing Only' },
            { key: 'INTRADAY', label: 'Intraday Only' },
          ].map(tab => (
            <button key={tab.key} onClick={() => setFilter(tab.key)} style={{
              padding: '6px 14px', borderRadius: '6px',
              border: `1px solid ${filter === tab.key ? 'var(--accent-green)' : 'var(--border)'}`,
              background: filter === tab.key ? 'rgba(0,201,107,0.1)' : 'transparent',
              color: filter === tab.key ? 'var(--accent-green)' : 'var(--text-secondary)',
              fontSize: '12px', fontWeight: '500', cursor: 'pointer'
            }}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Signals */}
        {filtered.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>🔍</div>
            <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '6px' }}>No signals right now</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Scanner runs at 8:30 AM every weekday. Click "Run Scan Now" to trigger manually.
            </div>
          </div>
        ) : (
          filtered.map((signal, i) => <SignalCard key={signal.id} signal={signal} index={i} />)
        )}
      </main>
    </div>
  )
}