import React, { useEffect } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { Users, Activity, LayoutDashboard, LogOut, Sun, Moon } from 'lucide-react'
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
  const location = useLocation()
  const { theme, setTheme } = useAppStore()

  const isUsersActive = location.pathname === '/admin'
  const isLiveProcessesActive = location.pathname.startsWith('/admin/live-processes')

  useEffect(() => {
    if (title) {
      document.title = `${title} - IBRA BOT Admin`
    }
  }, [title])

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

      {/* ── Admin Header ── */}
      <header className="admin-header sticky top-0 z-30 backdrop-blur-xl bg-white/95 dark:bg-black/75 border-b border-slate-200/80 dark:border-emerald-500/20 shadow-xs transition-colors">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
          {/* ── Mobile Header (< sm): Two dedicated rows so nothing is cut off ── */}
          <div className="flex flex-col gap-2 py-2 sm:hidden">
            {/* Top Bar: Logo + Quick Actions (لوحة البوت، المظهر، خروج) */}
            <div className="flex items-center justify-between gap-2">
              <Link
                to="/admin"
                className="flex items-center gap-1.5 shrink-0 transition-opacity hover:opacity-90"
                title="لوحة الإدارة"
              >
                <div className="w-8 h-8 rounded-xl bg-white border border-gray-200 dark:border-emerald-500/30 shrink-0 p-0.5 flex items-center justify-center shadow-xs overflow-hidden">
                  <img
                    src="/logo.png?v=2"
                    alt="IBRA BOT"
                    className="w-full h-full object-contain"
                  />
                </div>
                <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/20 px-1.5 py-0.5 rounded-md">
                  Admin
                </span>
              </Link>

              {/* Action Buttons: Never cut off */}
              <div className="flex items-center gap-1.5 shrink-0">
                <Link
                  to="/dashboard"
                  className="flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-white/5 px-2.5 py-1.5 rounded-xl border border-slate-200/80 dark:border-white/10 active:scale-95 shadow-xs"
                  title="الرجوع إلى لوحة البوت الرئيسية"
                >
                  <LayoutDashboard size={13} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>لوحة البوت</span>
                </Link>

                <button
                  onClick={toggleTheme}
                  className="p-1.5 rounded-xl text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 active:scale-95 cursor-pointer shadow-xs"
                  title={theme === 'dark' ? 'الوضع النهاري' : 'الوضع الليلي'}
                >
                  {theme === 'dark' ? <Sun size={15} className="text-amber-400" /> : <Moon size={15} className="text-emerald-600" />}
                </button>

                <button
                  onClick={handleSecureLogout}
                  className="flex items-center gap-1 bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 px-2.5 py-1.5 rounded-xl text-xs font-bold active:scale-95 cursor-pointer shadow-xs"
                  title="تسجيل الخروج"
                >
                  <LogOut size={13} className="shrink-0" />
                  <span>خروج</span>
                </button>
              </div>
            </div>

            {/* Row 2: Full-width Segmented Tabs (50/50) */}
            <nav className="grid grid-cols-2 gap-1 bg-slate-100/90 dark:bg-white/5 p-1 rounded-xl border border-slate-200/70 dark:border-white/10 w-full">
              <Link
                to="/admin"
                className={`flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg transition-all ${
                  isUsersActive
                    ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                    : 'text-slate-600 dark:text-slate-300 font-medium border border-transparent'
                }`}
                title="إدارة المستخدمين والاشتراكات"
              >
                <Users size={14} className={isUsersActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                <span>المستخدمين</span>
              </Link>

              <Link
                to="/admin/live-processes"
                className={`flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg transition-all ${
                  isLiveProcessesActive
                    ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                    : 'text-slate-600 dark:text-slate-300 font-medium border border-transparent'
                }`}
                title="عرض العمليات الحية الشغالة في الذاكرة"
              >
                <Activity size={14} className={isLiveProcessesActive ? 'text-emerald-500 animate-pulse' : 'text-slate-500 dark:text-slate-400'} />
                <span>العمليات الحية</span>
              </Link>
            </nav>
          </div>

          {/* ── Desktop Header (sm and above): Single Unified Row ── */}
          <div className="hidden sm:flex sm:h-16 items-center justify-between gap-4">
            {/* Brand Identity & Logo */}
            <Link
              to="/admin"
              className="flex items-center gap-2.5 shrink-0 transition-opacity hover:opacity-90"
              title="الرئيسية - إدارة المستخدمين"
            >
              <div className="w-8 h-8 rounded-xl bg-white border border-gray-200 dark:border-emerald-500/30 shrink-0 p-0.5 flex items-center justify-center shadow-xs overflow-hidden">
                <img
                  src="/logo.png?v=2"
                  alt="IBRA BOT"
                  className="w-full h-full object-contain"
                />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-black text-sm sm:text-base text-slate-900 dark:text-white tracking-tight">
                  IBRA BOT
                </span>
                <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/20 px-1.5 py-0.5 rounded-md">
                  Admin
                </span>
              </div>
            </Link>

            {/* Admin Navigation Tabs */}
            <nav className="flex items-center gap-1 bg-slate-100/90 dark:bg-white/5 p-1 rounded-xl border border-slate-200/70 dark:border-white/10 shrink-0">
              <Link
                to="/admin"
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  isUsersActive
                    ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/5 font-medium border border-transparent'
                }`}
                title="إدارة المستخدمين والاشتراكات"
              >
                <Users size={14} className={isUsersActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                <span>المستخدمين</span>
              </Link>

              <Link
                to="/admin/live-processes"
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  isLiveProcessesActive
                    ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/5 font-medium border border-transparent'
                }`}
                title="عرض العمليات الحية الشغالة في الذاكرة"
              >
                <Activity size={14} className={isLiveProcessesActive ? 'text-emerald-500 animate-pulse' : 'text-slate-500 dark:text-slate-400'} />
                <span>العمليات الحية</span>
              </Link>
            </nav>

            {/* Quick Actions: Return to Dashboard + Theme Toggle + Logout */}
            <div className="flex items-center gap-2 shrink-0">
              <Link
                to="/dashboard"
                className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 px-3 py-1.5 rounded-xl border border-slate-200/80 dark:border-white/10 transition active:scale-95 shadow-xs"
                title="الرجوع إلى لوحة البوت الرئيسية"
              >
                <LayoutDashboard size={14} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span>لوحة البوت</span>
              </Link>

              <button
                onClick={toggleTheme}
                className="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 border border-slate-200/80 dark:border-white/10 transition-colors cursor-pointer shadow-xs"
                title={theme === 'dark' ? 'الوضع النهاري' : 'الوضع الليلي'}
              >
                {theme === 'dark' ? <Sun size={15} className="text-amber-400" /> : <Moon size={15} className="text-emerald-600" />}
              </button>

              <button
                onClick={handleSecureLogout}
                className="flex items-center gap-1.5 bg-rose-50 hover:bg-rose-100 dark:bg-rose-500/10 dark:hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 px-3 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 cursor-pointer shadow-xs"
                title="تسجيل الخروج"
              >
                <LogOut size={14} className="shrink-0" />
                <span>خروج</span>
              </button>
            </div>
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

