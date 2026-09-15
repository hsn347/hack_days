import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Sidebar } from './Sidebar'
import { BottomNav } from './BottomNav'
import { PwaInstallPrompt } from '../common/PwaInstallPrompt'
import { ConfirmLogoutModal } from '../common/ConfirmLogoutModal'
import { Sun, Moon, LogOut } from 'lucide-react'
import { clsx } from 'clsx'
import { useAppStore } from '../../store/appStore'
import { useAuth } from '../../hooks/useAuth'

const LANGUAGES = ['AR', 'EN', 'TR'] as const

interface LayoutProps {
  children: React.ReactNode
  title?: string
}

export function Layout({ children, title }: LayoutProps) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { logout } = useAuth()
  const { theme, language, setTheme, setLanguage } = useAppStore()
  const [showLogoutModal, setShowLogoutModal] = useState(false)
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  const handleLangChange = (lang: string) => {
    const lc = lang.toLowerCase() as 'ar' | 'en' | 'tr'
    setLanguage(lc)
    i18n.changeLanguage(lc)
    document.documentElement.dir = 'ltr'
    document.documentElement.lang = lc
  }

  const handleConfirmLogout = async () => {
    setIsLoggingOut(true)
    try {
      await logout()
      navigate('/login')
    } finally {
      setIsLoggingOut(false)
      setShowLogoutModal(false)
    }
  }

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <div className="min-h-screen" style={{ minHeight: '100vh' }}>
      <Sidebar onLogoutClick={() => setShowLogoutModal(true)} />

      {/* Main content */}
      <main className="main-offset min-h-screen">
        {/* Mobile App Header (mobile only) */}
        <header className="mobile-app-header md:hidden flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-white/8 sticky top-0 z-30 bg-white/95 dark:bg-gray-950/90 backdrop-blur-xl shadow-xs">
          {/* Brand Identity */}
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 dark:border-emerald-500/30 shrink-0 p-0.5 flex items-center justify-center shadow-xs overflow-hidden">
              <img
                src="/logo.png?v=2"
                alt="IBRA BOT"
                className="w-full h-full object-contain"
              />
            </div>
            <div className="min-w-0">
              <span className="brand-title font-bold tracking-wide text-sm leading-tight block truncate">IBRA BOT</span>
              <span className="brand-tagline text-[10px] font-bold block leading-tight truncate">
                {t('tagline')}
              </span>
            </div>
          </div>

          {/* Quick Header Actions: Language + Theme + Logout */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Language Selector */}
            <div className="flex items-center bg-gray-100 dark:bg-white/6 rounded-lg p-0.5 border border-gray-200 dark:border-white/10">
              {LANGUAGES.map((lang) => {
                const isActive = language === lang.toLowerCase()
                return (
                  <button
                    key={lang}
                    onClick={() => handleLangChange(lang)}
                    className={clsx(
                      'px-1.5 py-0.5 rounded-md text-[10px] font-bold transition-all',
                      isActive
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                    )}
                  >
                    {lang}
                  </button>
                )
              })}
            </div>

            {/* Quick theme toggle */}
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-white/6 hover:bg-gray-200 dark:hover:bg-white/10 border border-gray-200 dark:border-white/10 transition-colors"
              title={theme === 'dark' ? t('common.lightMode') : t('common.darkMode')}
            >
              {theme === 'dark' ? <Sun size={15} className="text-amber-400" /> : <Moon size={15} className="text-primary-600" />}
            </button>

            {/* Logout button */}
            <button
              onClick={() => setShowLogoutModal(true)}
              className="p-1.5 rounded-lg text-rose-500 dark:text-rose-400 hover:text-rose-600 dark:hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition-colors cursor-pointer"
              title={t('nav.logout')}
            >
              <LogOut size={15} />
            </button>
          </div>
        </header>

        {/* Page content - pb-28 ensures full visibility above the mobile bottom nav */}
        <div className="p-3 sm:p-4 md:p-6 pb-28 md:pb-24 animate-fade-up">
          {children}
        </div>
      </main>

      {/* Mobile App Bottom Navigation Bar */}
      <BottomNav />

      {/* PWA Install Prompt */}
      <PwaInstallPrompt />

      {/* Confirm Logout Modal */}
      <ConfirmLogoutModal
        isOpen={showLogoutModal}
        onClose={() => setShowLogoutModal(false)}
        onConfirm={handleConfirmLogout}
        isPending={isLoggingOut}
      />
    </div>
  )
}

