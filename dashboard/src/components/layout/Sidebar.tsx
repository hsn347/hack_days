import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard, Users, Settings, LogOut,
  Moon, Sun, Bot, Menu, X,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../../store/appStore'
import { useAuth } from '../../hooks/useAuth'
import toast from 'react-hot-toast'

const LANGUAGES = ['AR', 'EN', 'TR'] as const

export function Sidebar() {
  const { t, i18n } = useTranslation()
  const navigate    = useNavigate()
  const { user, logout, isAdmin } = useAuth()
  const { theme, language, sidebarOpen, setTheme, setLanguage, toggleSidebar } = useAppStore()

  const handleLangChange = (lang: string) => {
    const lc = lang.toLowerCase() as 'ar' | 'en' | 'tr'
    setLanguage(lc)
    i18n.changeLanguage(lc)
    document.documentElement.dir = 'ltr'
    document.documentElement.lang = lc
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login')
    toast.success('تم تسجيل الخروج')
  }

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const navLinks = [
    { to: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/accounts',  icon: Users,           label: t('nav.accounts')  },
    { to: '/settings',  icon: Settings,        label: t('nav.settings')  },
  ]

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 bg-black/60 z-40" onClick={toggleSidebar} />
      )}

      {/* Sidebar - Always on the Left in all languages */}
      <aside
        dir="ltr"
        className={clsx(
          'glass-sidebar fixed top-0 left-0 h-full z-50 flex flex-col border-r border-white/8 transition-transform duration-300',
          'sidebar-width',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-4 py-5 border-b border-white/8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center shadow-glow">
              <Bot size={16} className="text-white" />
            </div>
            <span className="font-bold text-white tracking-wide">OsmanliBot</span>
          </div>
          <button onClick={toggleSidebar} className="md:hidden text-gray-400 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* User info */}
        {user && (
          <div className="px-4 py-3 border-b border-white/6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-primary-700 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                {user.username?.[0]?.toUpperCase() ?? user.email?.[0]?.toUpperCase() ?? '?'}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-white truncate">{user.username || user.email}</div>
                <div className="text-xs text-gray-500">{isAdmin ? 'Admin' : 'User'}</div>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navLinks.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => clsx('nav-item', isActive && 'active')}
              onClick={() => window.innerWidth < 768 && toggleSidebar()}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom: Language + Theme + Logout */}
        <div className="border-t border-white/8 px-3 py-3 space-y-2">
          {/* Language selector */}
          <div className="flex items-center gap-1 px-1">
            <span className="text-xs text-gray-500 flex-1">{t('settings.language')}</span>
            <div className="flex gap-1">
              {LANGUAGES.map(lang => (
                <button
                  key={lang}
                  onClick={() => handleLangChange(lang)}
                  className={clsx(
                    'px-2 py-0.5 rounded text-xs font-medium transition-all',
                    language === lang.toLowerCase()
                      ? 'bg-primary-600 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-white/8'
                  )}
                >
                  {lang}
                </button>
              ))}
            </div>
          </div>

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="nav-item w-full"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            <span className="text-sm">{theme === 'dark' ? t('common.lightMode') : t('common.darkMode')}</span>
          </button>

          {/* Logout */}
          <button onClick={handleLogout} className="nav-item w-full text-red-600 hover:text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:text-red-300 dark:hover:bg-red-600/10 transition-colors">
            <LogOut size={16} />
            <span className="text-sm">{t('nav.logout')}</span>
          </button>
        </div>
      </aside>
    </>
  )
}

// Mobile menu button — separate export for Layout usage
export function MobileMenuBtn() {
  const { toggleSidebar } = useAppStore()
  return (
    <button
      onClick={toggleSidebar}
      className="md:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/8"
    >
      <Menu size={20} />
    </button>
  )
}
