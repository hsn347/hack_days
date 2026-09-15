import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Shield, Lock, ExternalLink, Sun, Moon } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { useAppStore } from '../../store/appStore'
import toast from 'react-hot-toast'

export interface AdminLayoutProps {
  children: React.ReactNode
  title?: string
}

export function AdminLayout({ children, title }: AdminLayoutProps) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const { theme, setTheme } = useAppStore()

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const handleSecureLogout = async () => {
    await logout()
    toast.success('تم تسجيل الخروج بنجاح')
    navigate('/login')
  }

  return (
    <div className="admin-layout-wrapper min-h-screen bg-slate-50 dark:bg-[#060a08] text-slate-900 dark:text-gray-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200 transition-colors">
      {/* ── Background Ambient Glow (Dark mode only) ── */}
      <div className="fixed inset-0 pointer-events-none z-0 hidden dark:block">
        <div className="absolute top-0 start-1/4 w-96 h-96 bg-emerald-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-10 end-1/4 w-96 h-96 bg-amber-600/10 rounded-full blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(16,185,129,0.15),rgba(255,255,255,0))]" />
      </div>

      {/* ── Simplified Admin Header ── */}
      <header className="admin-header sticky top-0 z-30 backdrop-blur-xl bg-white/95 dark:bg-black/75 border-b border-slate-200/80 dark:border-emerald-500/20 shadow-xs transition-colors">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-2.5 sm:py-0 sm:h-16 flex items-center justify-between gap-3">
          {/* Brand Identity */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-emerald-500/10 dark:bg-emerald-500/20 border border-emerald-500/25 flex items-center justify-center shrink-0 shadow-xs">
              <Shield size={18} className="text-emerald-600 dark:text-emerald-400" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-black text-sm sm:text-base text-slate-900 dark:text-white tracking-tight">
                IBRA BOT
              </span>
              <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/20 px-1.5 py-0.5 rounded-md">
                Admin
              </span>
            </div>
          </div>

          {/* Header Actions: Theme Toggle + Dashboard Link + Emergency Lock */}
          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            {/* Theme Toggle (الوضع الليلي والنهاري) */}
            <button
              onClick={toggleTheme}
              className="p-1.5 sm:p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 border border-slate-200/80 dark:border-white/10 transition-colors cursor-pointer shadow-xs"
              title={theme === 'dark' ? 'الوضع النهاري' : 'الوضع الليلي'}
            >
              {theme === 'dark' ? <Sun size={16} className="text-amber-400" /> : <Moon size={16} className="text-emerald-600" />}
            </button>

            {/* Link to regular dashboard */}
            <Link
              to="/dashboard"
              className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 px-3 py-1.5 rounded-xl border border-slate-200/80 dark:border-white/10 transition active:scale-95 shadow-xs"
              title="الانتقال إلى لوحة المستخدمين العادية"
            >
              <ExternalLink size={13} />
              <span>المستخدمين</span>
            </Link>

            {/* Lock / Logout Button */}
            <button
              onClick={handleSecureLogout}
              className="flex items-center gap-1 bg-rose-50 hover:bg-rose-100 dark:bg-rose-500/10 dark:hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 px-3 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 cursor-pointer shadow-xs"
              title="إغلاق وقفل الجلسة فوراً"
            >
              <Lock size={13} />
              <span>قفل</span>
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Content Area ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 relative">
        {children}
      </main>
    </div>
  )
}

