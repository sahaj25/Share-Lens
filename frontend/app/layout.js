import './globals.css'

export const metadata = {
  title: 'ShareLens — Trading Intelligence',
  description: 'AI-powered Nifty 50 trading signals',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}