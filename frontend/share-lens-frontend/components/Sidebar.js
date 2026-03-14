'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const navItems = [
  { href: '/',            label: 'Scanner',     icon: '⚡', desc: 'Live signals' },
  { href: '/positions',   label: 'Positions',   icon: '📂', desc: 'Open trades' },
  { href: '/performance', label: 'Performance', icon: '📊', desc: 'Track record' },
  { href: '/history',     label: 'History',     icon: '🕐', desc: 'All signals' },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside style={{
      width: '240px',
      minHeight: '100vh',
      background: '#111111',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '28px 16px',
      position: 'fixed',
      top: 0, left: 0,
      zIndex: 100
    }}>
      {/* Logo */}
      <div style={{ padding: '0 8px', marginBottom: '32px' }}>
        <div style={{ fontSize: '22px', fontWeight: '700', letterSpacing: '-0.03em', color: '#fff' }}>
          Share<span style={{ color: 'var(--accent-green)' }}>Lens</span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
          Nifty 50 AI Trading Tool
        </div>
      </div>

      {/* Live badge */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        background: 'rgba(0,201,107,0.08)',
        border: '1px solid rgba(0,201,107,0.15)',
        borderRadius: '8px', padding: '8px 12px',
        marginBottom: '24px'
      }}>
        <div style={{
          width: '7px', height: '7px', borderRadius: '50%',
          background: 'var(--accent-green)',
          animation: 'pulse-dot 2s infinite'
        }} />
        <span style={{ fontSize: '12px', color: 'var(--accent-green)', fontWeight: '600' }}>
          System Live
        </span>
      </div>

      {/* Nav */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {navItems.map(item => {
          const active = pathname === item.href
          return (
            <Link key={item.href} href={item.href} style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '10px 12px', borderRadius: '8px',
              textDecoration: 'none',
              background: active ? 'rgba(0,201,107,0.1)' : 'transparent',
              border: `1px solid ${active ? 'rgba(0,201,107,0.2)' : 'transparent'}`,
              transition: 'all 0.15s ease'
            }}>
              <span style={{ fontSize: '16px' }}>{item.icon}</span>
              <div>
                <div style={{
                  fontSize: '13px', fontWeight: active ? '600' : '400',
                  color: active ? 'var(--accent-green)' : 'var(--text-primary)'
                }}>
                  {item.label}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {item.desc}
                </div>
              </div>
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div style={{ marginTop: 'auto', padding: '0 8px' }}>
        <div style={{
          background: 'var(--bg-elevated)', borderRadius: '8px',
          padding: '12px', border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: '600' }}>
            MARKET HOURS
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            NSE • Mon – Fri
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            9:15 AM – 3:30 PM
          </div>
          <div style={{
            marginTop: '8px', paddingTop: '8px',
            borderTop: '1px solid var(--border)',
            fontSize: '11px', color: 'var(--accent-green)', fontWeight: '600'
          }}>
            Running cost: ~Rs. 500/mo
          </div>
        </div>
      </div>
    </aside>
  )
}