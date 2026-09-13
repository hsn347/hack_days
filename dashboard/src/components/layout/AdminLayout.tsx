import React, { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Shield, Lock, LogOut, ExternalLink, Activity, Users, Clock, AlertTriangle } from 'lucide-react'
import { useAdminAuth } from '../../hooks/useAdminAuth'
import toast from 'react-hot-toast'

export interface AdminLayoutProps {
  children: React.ReactNode
  title?: string
}

export function AdminLayout({ children, title }: AdminLayoutProps) {
  const { adminUser, logoutAdmin } = useAdminAuth()
  const navigate = useNavigate()
  const [timeLeft, setTimeLeft] = useState<string>('60:00')

  // مؤقت الجلسة التنازلي التلقائي
  useEffect(() => {
    const raw = sessionStorage.getItem('osmanli_admin_session_token')
    if (!raw) return

    const timer = setInterval(() => {
      try {
        const session = JSON.parse(sessionStorage.getItem('osmanli_admin_session_token') || '{}')
        if (session.expiresAt) {
          const diff = session.expiresAt - Date.now()
          if (diff <= 0) {
            clearInterval(timer)
            toast.error('انتهت صلاحية جلسة المسؤول لأسباب أمنية')
            logoutAdmin()
            navigate('/admin/login')
          } else {
            const mins = Math.floor(diff / 60000)
            const secs = Math.floor((diff % 60000) / 1000)
            setTimeLeft(`${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`)
          }
        }
      } catch {}
    }, 1000)

    return () => clearInterval(timer)
  }, [logoutAdmin, navigate])

  const handleSecureLogout = async () => {
    await logoutAdmin()
    toast.success('تم قفل جلسة المسؤول بنجاح')
    navigate('/admin/login')
  }

  return (
    <div className="min-h-screen bg-[#060a08] text-gray-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* ── Background Cyber Ambient Glow ── */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 start-1/4 w-96 h-96 bg-emerald-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-10 end-1/4 w-96 h-96 bg-amber-600/10 rounded-full blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(16,185,129,0.15),rgba(255,255,255,0))]" />
      </div>

      {/* ── Dedicated Admin Top Bar ── */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-black/60 border-b border-emerald-500/20 shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Logo & Portal Identity */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 via-emerald-600/30 to-amber-500/20 border border-emerald-500/40 shadow-[0_0_20px_rgba(16,185,129,0.3)]">
              <Shield size={20} className="text-emerald-400" />
              <span className="absolute -top-1 -end-1 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-white text-base tracking-wide">
                  بوابة الإدارة المركزية
                </span>
                <span className="bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                  ROOT ADMIN
                </span>
              </div>
              <div className="text-[11px] text-gray-400 flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span>اتصال آمن ومشفّر 256-Bit SSL/TLS</span>
              </div>
            </div>
          </div>

          {/* Center / Security Indicator */}
          <div className="hidden md:flex items-center gap-3 bg-white/5 border border-white/10 px-3 py-1.5 rounded-xl text-xs">
            <Clock size={14} className="text-amber-400" />
            <span className="text-gray-400">صلاحية الجلسة:</span>
            <span className="font-mono font-bold text-amber-300">{timeLeft}</span>
          </div>

          {/* Right / Actions & User Profile */}
          <div className="flex items-center gap-3">
            {/* Link to regular dashboard */}
            <Link
              to="/dashboard"
              className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-white/10 transition"
              title="الانتقال إلى لوحة المستخدمين العادية"
            >
              <ExternalLink size={13} />
              <span>لوحة المستخدمين</span>
            </Link>

            {/* Admin Profile Chip */}
            <div className="hidden lg:flex items-center gap-2 bg-emerald-950/40 border border-emerald-500/30 px-3 py-1 rounded-xl text-xs">
              <span className="text-emerald-300 font-semibold truncate max-w-[150px]">
                {adminUser?.email || 'admin@osmanli.com'}
              </span>
            </div>

            {/* Emergency Lock / Logout Button */}
            <button
              onClick={handleSecureLogout}
              className="flex items-center gap-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 px-3 py-1.5 rounded-lg text-xs font-bold transition shadow-[0_0_15px_rgba(244,63,94,0.2)] active:scale-95"
              title="إغلاق وقفل الجلسة فوراً"
            >
              <Lock size={13} />
              <span>قفل الجلسة</span>
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Content Area ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 relative z-10">
        {children}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-white/10 py-4 text-center text-xs text-gray-500 relative z-10 bg-black/40 backdrop-blur-md">
        <span>OsmanliBot Core Security Gateway • Zero-Trust Policy Enforced</span>
      </footer>
    </div>
  )
}
