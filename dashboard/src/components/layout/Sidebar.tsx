import React, { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard, Users, Settings, LogOut,
  Moon, Sun, Bot, Menu, X, Shield, ChevronsUpDown,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../../store/appStore'
import { useAuth } from '../../hooks/useAuth'
import { localizeUsername } from '../../lib/localize'
import { AccountSwitcherModal } from '../common/AccountSwitcherModal'
import { useTenant } from '../../context/TenantContext'
import toast from 'react-hot-toast'

const LANGUAGES = ['AR', 'EN', 'TR'] as const

export interface SidebarProps {
  onLogoutClick?: () => void
}

export function Sidebar({ onLogoutClick }: SidebarProps = {}) {
  const { t, i18n } = useTranslation()
  const { brandName, tagline, logoUrl } = useTenant()
  const navigate    = useNavigate()
  const { user, logout, isAdmin, savedAccounts } = useAuth()
  const { theme, language, sidebarOpen, setTheme, setLanguage, toggleSidebar } = useAppStore()
  const [showAccountSwitcher, setShowAccountSwitcher] = useState(false)

  const handleLangChange = (lang: string) => {
    const lc = lang.toLowerCase() as 'ar' | 'en' | 'tr'
    setLanguage(lc)
    i18n.changeLanguage(lc)
    document.documentElement.dir = 'ltr'
    document.documentElement.lang = lc
  }

  const handleLogout = async () => {
    if (onLogoutClick) {
      onLogoutClick()
      return
    }
    await logout()
    navigate('/login')
  }

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const navLinks = [
    { to: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/accounts',  icon: Users,           label: t('nav.accounts')  },
    { to: '/settings',  icon: Settings,        label: t('nav.settings')  },
    ...(isAdmin ? [
      {
        to: '/admin',
        icon: Shield,
        label: t('nav.admin', 'الإدارة'),
        badge: 'ROOT',
        isSpecial: true,
      }
    ] : []),
  ]

  return (
    <>
      {/* Sidebar - Desktop Only (Hidden on Mobile) */}
      <aside
        dir="ltr"
        className="hidden md:flex glass-sidebar fixed top-0 left-0 h-full z-50 flex-col border-r border-gray-200 dark:border-white/8 sidebar-width"
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-gray-200 dark:border-white/8">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-primary-500/25 shrink-0 flex items-center justify-center shadow-xs overflow-hidden">
              <img
                src={logoUrl || '/logo.png?v=2'}
                alt={brandName}
                className="w-full h-full object-cover"
              />
            </div>
            <div className="min-w-0">
              <span className="brand-title font-bold text-sm tracking-wide block leading-tight">{brandName}</span>
              {tagline ? (
                <span className="brand-tagline text-[11px] font-bold block leading-tight mt-0.5 truncate">
                  {tagline}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* User info & Quick Account Switcher trigger */}
        {user && (
          <div className="p-2 border-b border-gray-200 dark:border-white/8">
            <button
              type="button"
              onClick={() => setShowAccountSwitcher(true)}
              className="w-full flex items-center justify-between p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-white/6 transition-colors text-left group cursor-pointer border border-transparent hover:border-gray-200 dark:hover:border-white/10"
              title={t('accountSwitcher.title', 'تبديل الحساب')}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-primary-600 dark:bg-primary-600 text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-xs">
                  {user.username?.[0]?.toUpperCase() ?? user.email?.[0]?.toUpperCase() ?? '?'}
                </div>
                <div className="min-w-0 text-left">
                  <div className="text-xs font-bold text-gray-900 dark:text-white truncate">
                    {localizeUsername(user.username, t) || user.email}
                  </div>
                  <div className="text-[10px] text-gray-500 dark:text-gray-400 flex items-center gap-1">
                    <span>{isAdmin ? t('roles.admin', 'Admin') : t('roles.user', 'User')}</span>
                    {savedAccounts.length > 1 && (
                      <span className="text-[9px] bg-primary-500/15 text-primary-600 dark:text-primary-400 font-mono px-1 py-0.2 rounded font-bold">
                        {savedAccounts.length}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <ChevronsUpDown size={14} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-200 shrink-0 transition-colors" />
            </button>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navLinks.map(({ to, icon: Icon, label, badge, isSpecial }: any) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => clsx(
                'nav-item flex items-center justify-between',
                isActive && 'active',
                isSpecial && !isActive && 'text-emerald-400/90 hover:text-emerald-300'
              )}
              onClick={() => window.innerWidth < 768 && toggleSidebar()}
            >
              <div className="flex items-center gap-2.5">
                <Icon size={18} className={isSpecial ? 'text-emerald-400' : undefined} />
                <span>{label}</span>
              </div>
              {badge && (
                <span className="bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-mono font-extrabold px-1.5 py-0.5 rounded tracking-wider">
                  {badge}
                </span>
              )}
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

      {/* Account Switcher Modal */}
      <AccountSwitcherModal
        isOpen={showAccountSwitcher}
        onClose={() => setShowAccountSwitcher(false)}
      />
    </>
  )
}

// Mobile menu button — separate export for Layout usage
export function MobileMenuBtn() {
  return null
}
