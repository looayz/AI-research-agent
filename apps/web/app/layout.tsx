import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Research Agent — Autonomous Multi-Agent Investigation Platform',
  description: 'Multi-agent AI research platform that autonomously investigates complex questions, cross-checks claims, and builds cited reports.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased selection:bg-primary/20 selection:text-primary">
        {children}
      </body>
    </html>
  )
}
