import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { Users, Activity, LogOut, Sun, Moon, Store, ShieldCheck, Menu, X, Landmark } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../hooks/useAuth'
import { useAppStore } from '../../store/appStore'
import { useTenant } from '../../context/TenantContext'
import toast from 'react-hot-toast'

export interface AdminLayoutProps {
  children: React.ReactNode
  title?: string
}

export function AdminLayout({ children, title }: AdminLayoutProps) {
  const { t } = useTranslation()
  const { logout, isSuperAdmin, isMerchantAdmin } = useAuth()
  const { brandName, logoUrl } = useTenant()
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, setTheme } = useAppStore()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  const isUsersActive = location.pathname === '/admin'
  const isLiveProcessesActive = location.pathname.startsWith('/admin/live-processes')
  const isMerchantsActive = location.pathname.startsWith('/admin/merchants')
  const isProxiesActive = location.pathname.startsWith('/admin/proxies')
  const isUsersCastlesActive = location.pathname.startsWith('/admin/users-castles')

  useEffect(() => {
    if (title) {
      document.title = `${title} - ${brandName} Admin`
    } else {
      document.title = `${brandName} Admin`
    }
  }, [title, brandName])

  // إغلاق القائمة الجانبية تلقائياً عند تغيير المسار
  useEffect(() => {
    setMobileDrawerOpen(false)
  }, [location.pathname])

  // إغلاق القائمة الجانبية عند الضغط على Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileDrawerOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const handleSecureLogout = async () => {
    await logout()
    toast.success(t('admin.layout.logoutSuccess'))
    navigate('/login')
  }

  return (
    <div className="admin-layout-wrapper min-h-screen bg-slate-50 dark:bg-[#060a08] text-slate-900 dark:text-gray-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200 transition-colors">
      {/* ── Background Ambient Glow (Dark mode only) ── */}
      <div className="fixed inset-0 pointer-events-none z-0 hidden dark:block">
        <div className="absolute top-0 start-1/4 w-96 h-96 bg-emerald-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-10 end-1/4 w-96 h-96 bg-amber-600/10 rounded-full blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(var(--theme-primary-rgb,16,185,129),0.15),rgba(255,255,255,0))]" />
      </div>

      {/* ── Admin Header ── */}
      <header className="admin-header sticky top-0 z-30 backdrop-blur-xl bg-white/95 dark:bg-black/75 border-b border-slate-200/80 dark:border-emerald-500/20 shadow-xs transition-colors">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
          {/* ── Mobile Header (< sm): Clean Single Row with Hamburger Menu ── */}
          <div className="flex items-center justify-between gap-2 py-2.5 sm:hidden">
            {/* Start: Hamburger Button + Logo + Title */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setMobileDrawerOpen(true)}
                className="p-1.5 rounded-xl text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 active:scale-95 cursor-pointer shadow-xs hover:bg-slate-200 dark:hover:bg-white/10 transition-colors"
                aria-label="فتح قائمة التنقل"
                title="قائمة التنقل"
              >
                <Menu size={18} className="text-emerald-600 dark:text-emerald-400" />
              </button>

              <Link
                to="/admin"
                className="flex items-center gap-1.5 shrink-0 transition-opacity hover:opacity-90"
                title={t('admin.layout.panelTitle')}
              >
                <div className="w-8 h-8 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-primary-500/25 shrink-0 flex items-center justify-center shadow-xs overflow-hidden">
                  <img
                    src={logoUrl || '/logo.png?v=2'}
                    alt={brandName}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-black text-xs text-slate-900 dark:text-white">
                    {brandName}
                  </span>
                  <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/20 px-1 py-0.2 rounded-md">
                    Admin
                  </span>
                </div>
              </Link>
            </div>

            {/* End: Action Buttons */}
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={toggleTheme}
                className="p-1.5 rounded-xl text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 active:scale-95 cursor-pointer shadow-xs"
                title={theme === 'dark' ? t('common.lightMode') : t('common.darkMode')}
              >
                {theme === 'dark' ? <Sun size={15} className="text-amber-400" /> : <Moon size={15} className="text-emerald-600" />}
              </button>

              <button
                onClick={handleSecureLogout}
                className="flex items-center gap-1 bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 px-2.5 py-1.5 rounded-xl text-xs font-bold active:scale-95 cursor-pointer shadow-xs"
                title={t('admin.layout.logout')}
              >
                <LogOut size={13} className="shrink-0" />
                <span>{t('admin.layout.logoutShort')}</span>
              </button>
            </div>
          </div>

          {/* ── Mobile Side Drawer (< sm) via React Portal ── */}
          {mobileDrawerOpen && typeof document !== 'undefined' && createPortal(
            <div className="fixed inset-0 z-[9999] sm:hidden">
              {/* Backdrop */}
              <div
                className="fixed inset-0 bg-black/70 backdrop-blur-xs transition-opacity"
                onClick={() => setMobileDrawerOpen(false)}
              />

              {/* Drawer Container */}
              <aside
                className="fixed top-0 bottom-0 left-0 w-72 max-w-[85vw] h-full bg-white dark:bg-[#0c120e] z-[10000] shadow-2xl flex flex-col border-r border-slate-200 dark:border-white/10"
                style={{ height: '100vh', maxHeight: '100dvh', left: 0 }}
              >
                {/* Drawer Header */}
                <div className="flex items-center justify-between px-4 py-3.5 border-b border-slate-200/80 dark:border-white/10">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-primary-500/25 shrink-0 flex items-center justify-center shadow-xs overflow-hidden">
                      <img
                        src={logoUrl || '/logo.png?v=2'}
                        alt={brandName}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-black text-sm text-slate-900 dark:text-white leading-tight">
                        {brandName}
                      </span>
                      <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/20 px-1 py-0.2 rounded-md">
                        Admin
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setMobileDrawerOpen(false)}
                    className="p-1.5 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 transition-colors cursor-pointer"
                    title="إغلاق"
                  >
                    <X size={18} />
                  </button>
                </div>

                {/* Navigation Links */}
                <nav className="flex-1 overflow-y-auto p-3 space-y-1.5">
                  <Link
                    to="/admin"
                    onClick={() => setMobileDrawerOpen(false)}
                    className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                      isUsersActive
                        ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-200/80 dark:border-emerald-500/30 shadow-xs'
                        : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
                    }`}
                  >
                    <Users size={18} className={isUsersActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                    <span>المستخدمين</span>
                  </Link>

                  {isSuperAdmin && (
                    <>
                      <Link
                        to="/admin/live-processes"
                        onClick={() => setMobileDrawerOpen(false)}
                        className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                          isLiveProcessesActive
                            ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-200/80 dark:border-emerald-500/30 shadow-xs'
                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
                        }`}
                      >
                        <Activity size={18} className={isLiveProcessesActive ? 'text-emerald-500 animate-pulse' : 'text-slate-500 dark:text-slate-400'} />
                        <span>العمليات الحية</span>
                      </Link>

                      <Link
                        to="/admin/merchants"
                        onClick={() => setMobileDrawerOpen(false)}
                        className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                          isMerchantsActive
                            ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-200/80 dark:border-emerald-500/30 shadow-xs'
                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
                        }`}
                      >
                        <Store size={18} className={isMerchantsActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                        <span>التجار</span>
                      </Link>

                      <Link
                        to="/admin/proxies"
                        onClick={() => setMobileDrawerOpen(false)}
                        className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                          isProxiesActive
                            ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-200/80 dark:border-emerald-500/30 shadow-xs'
                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
                        }`}
                      >
                        <ShieldCheck size={18} className={isProxiesActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                        <span>البروكسيات</span>
                      </Link>

                      <Link
                        to="/admin/users-castles"
                        onClick={() => setMobileDrawerOpen(false)}
                        className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                          isUsersCastlesActive
                            ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-200/80 dark:border-emerald-500/30 shadow-xs'
                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
                        }`}
                      >
                        <Landmark size={18} className={isUsersCastlesActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                        <span>قلاع المستخدمين</span>
                      </Link>
                    </>
                  )}
                </nav>

                {/* Drawer Footer */}
                <div className="p-3 border-t border-slate-200/80 dark:border-white/10 flex items-center justify-between bg-slate-50/50 dark:bg-white/2">
                  <button
                    onClick={toggleTheme}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-white/5 border border-slate-200/80 dark:border-white/10 cursor-pointer shadow-xs active:scale-95"
                  >
                    {theme === 'dark' ? <Sun size={14} className="text-amber-400" /> : <Moon size={14} className="text-emerald-600" />}
                    <span>المظهر</span>
                  </button>

                  <button
                    onClick={handleSecureLogout}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 cursor-pointer shadow-xs active:scale-95"
                  >
                    <LogOut size={13} />
                    <span>خروج</span>
                  </button>
                </div>
              </aside>
            </div>,
            document.body
          )}

          {/* ── Desktop Header (sm and above): Single Unified Row ── */}
          <div className="hidden sm:flex sm:h-16 items-center justify-between gap-4">
            {/* Brand Identity & Logo */}
            <Link
              to="/admin"
              className="flex items-center gap-2.5 shrink-0 transition-opacity hover:opacity-90"
              title="لوحة التحكم"
            >
              <div className="w-8 h-8 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-primary-500/25 shrink-0 flex items-center justify-center shadow-xs overflow-hidden">
                <img
                  src={logoUrl || '/logo.png?v=2'}
                  alt={brandName}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-black text-sm sm:text-base text-slate-900 dark:text-white tracking-tight">
                  {brandName}
                </span>
                <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/20 px-1.5 py-0.5 rounded-md">
                  {isMerchantAdmin ? 'Merchant Admin' : 'Admin'}
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
                title="المستخدمين"
              >
                <Users size={14} className={isUsersActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                <span>المستخدمين</span>
              </Link>

              {/* العمليات الحية والتجار والبروكسيات: للمشرف الأعلى حصرياً */}
              {isSuperAdmin && (
                <>
                  <Link
                    to="/admin/live-processes"
                    className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                      isLiveProcessesActive
                        ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/5 font-medium border border-transparent'
                    }`}
                    title="العمليات الحية"
                  >
                    <Activity size={14} className={isLiveProcessesActive ? 'text-emerald-500 animate-pulse' : 'text-slate-500 dark:text-slate-400'} />
                    <span>العمليات الحية</span>
                  </Link>

                  <Link
                    to="/admin/merchants"
                    className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                      isMerchantsActive
                        ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/5 font-medium border border-transparent'
                    }`}
                    title="التجار"
                  >
                    <Store size={14} className={isMerchantsActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                    <span>التجار</span>
                  </Link>

                  <Link
                    to="/admin/proxies"
                    className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                      isProxiesActive
                        ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/5 font-medium border border-transparent'
                    }`}
                    title="البروكسيات"
                  >
                    <ShieldCheck size={14} className={isProxiesActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                    <span>البروكسيات</span>
                  </Link>

                  <Link
                    to="/admin/users-castles"
                    className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                      isUsersCastlesActive
                        ? 'bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold shadow-xs border border-slate-200/80 dark:border-emerald-500/30'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/5 font-medium border border-transparent'
                    }`}
                    title="قلاع المستخدمين"
                  >
                    <Landmark size={14} className={isUsersCastlesActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'} />
                    <span>قلاع المستخدمين</span>
                  </Link>
                </>
              )}
            </nav>

            {/* Quick Actions: Theme Toggle + Logout */}
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={toggleTheme}
                className="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 border border-slate-200/80 dark:border-white/10 transition-colors cursor-pointer shadow-xs"
                title={theme === 'dark' ? t('common.lightMode') : t('common.darkMode')}
              >
                {theme === 'dark' ? <Sun size={15} className="text-amber-400" /> : <Moon size={15} className="text-emerald-600" />}
              </button>

              <button
                onClick={handleSecureLogout}
                className="flex items-center gap-1.5 bg-rose-50 hover:bg-rose-100 dark:bg-rose-500/10 dark:hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 px-3 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 cursor-pointer shadow-xs"
                title={t('admin.layout.logout')}
              >
                <LogOut size={14} className="shrink-0" />
                <span>{t('admin.layout.logoutShort')}</span>
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

