import React from 'react'
import { useTranslation } from 'react-i18next'
import { Sun, Moon } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { LanguageDropdown } from './LanguageDropdown'

export function AuthHeaderBar() {
  const { t } = useTranslation()
  const { theme, setTheme } = useAppStore()

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <div className="absolute top-4 start-4 end-4 flex items-center justify-between z-20 pointer-events-auto">
      <div />
      {/* Language & Theme Controls */}
      <div className="flex items-center gap-1.5 bg-white/80 dark:bg-[#0c120f]/80 backdrop-blur-md p-1 rounded-xl border border-gray-200/80 dark:border-white/10 shadow-xs">
        {/* Language selector dropdown */}
        <LanguageDropdown direction="down" />

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
