import React from 'react'
import { useTranslation } from 'react-i18next'
import { Sun, Moon } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import clsx from 'clsx'

const LANGUAGES = ['AR', 'EN', 'TR'] as const

export function AuthHeaderBar() {
  const { i18n, t } = useTranslation()
  const { theme, language, setTheme, setLanguage } = useAppStore()

  const handleLangChange = (lang: string) => {
    const lc = lang.toLowerCase() as 'ar' | 'en' | 'tr'
    setLanguage(lc)
    i18n.changeLanguage(lc)
    document.documentElement.dir = 'ltr'
    document.documentElement.lang = lc
  }

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <div className="absolute top-4 start-4 end-4 flex items-center justify-between z-20 pointer-events-auto">
      <div />
      {/* Language & Theme Controls */}
      <div className="flex items-center gap-1.5 bg-white/80 dark:bg-[#0c120f]/80 backdrop-blur-md p-1 rounded-xl border border-gray-200/80 dark:border-white/10 shadow-xs">
        {/* Language selector */}
        <div className="flex items-center bg-gray-100 dark:bg-white/6 rounded-lg p-0.5 border border-gray-200/60 dark:border-white/5">
          {LANGUAGES.map((lang) => {
            const isActive = language === lang.toLowerCase()
            return (
              <button
                key={lang}
                type="button"
                onClick={() => handleLangChange(lang)}
                style={isActive ? { backgroundColor: 'var(--theme-primary)', color: '#ffffff' } : {}}
                className={clsx(
                  'px-2 py-0.5 rounded-md text-[11px] font-bold transition-all cursor-pointer select-none',
                  isActive
                    ? 'shadow-xs'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                )}
              >
                {lang}
              </button>
            )
          })}
        </div>

        {/* Theme toggle button */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-white/6 hover:bg-gray-200 dark:hover:bg-white/10 border border-gray-200/60 dark:border-white/5 transition-colors cursor-pointer"
          title={theme === 'dark' ? t('common.lightMode', 'الوضع النهاري') : t('common.darkMode', 'الوضع الليلي')}
        >
          {theme === 'dark' ? (
            <Sun size={15} className="text-amber-400" />
          ) : (
            <Moon size={15} className="text-emerald-600" />
          )}
        </button>
      </div>
    </div>
  )
}
