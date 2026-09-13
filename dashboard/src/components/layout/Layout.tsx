import React from 'react'
import { Sidebar, MobileMenuBtn } from './Sidebar'

interface LayoutProps {
  children: React.ReactNode
  title?: string
}

export function Layout({ children, title }: LayoutProps) {
  return (
    <div className="min-h-screen" style={{ minHeight: '100vh' }}>
      <Sidebar />

      {/* Main content */}
      <main className="main-offset min-h-screen">
        {/* Top bar (mobile only) */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-white/6 glass-sidebar sticky top-0 z-30">
          <MobileMenuBtn />
          {title && <h1 className="font-semibold text-white">{title}</h1>}
        </div>

        {/* Page content */}
        <div className="p-4 md:p-6 pb-20 md:pb-24 animate-fade-up">
          {children}
        </div>
      </main>
    </div>
  )
}
