import React, { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Check } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import type { Language } from '../../types'
import clsx from 'clsx'

export interface LanguageOption {
  code: Language
  label: string
  nativeName: string
}

export const SUPPORTED_LANGUAGES: LanguageOption[] = [
  { code: 'ar', label: 'AR', nativeName: 'العربية' },
  { code: 'en', label: 'EN', nativeName: 'English' },
  { code: 'tr', label: 'TR', nativeName: 'Türkçe' },
  { code: 'ru', label: 'RU', nativeName: 'Русский' },
]

export interface LanguageDropdownProps {
  direction?: 'down' | 'up'
  align?: 'start' | 'end'
  className?: string
  buttonClassName?: string
}

export function LanguageDropdown({
  direction = 'down',
  align = 'end',
  className,
  buttonClassName,
}: LanguageDropdownProps) {
  const { i18n } = useTranslation()
  const { language, setLanguage } = useAppStore()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const activeOption =
    SUPPORTED_LANGUAGES.find((l) => l.code === language) || SUPPORTED_LANGUAGES[0]

  const handleSelect = (code: Language) => {
    setLanguage(code)
    i18n.changeLanguage(code)
    document.documentElement.dir = 'ltr'
    document.documentElement.lang = code
    setIsOpen(false)
  }

  // Close dropdown on outside click or escape key
  useEffect(() => {
    if (!isOpen) return

    const handlePointerDown = (e: MouseEvent | TouchEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('touchstart', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('touchstart', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  return (
    <div ref={dropdownRef} className={clsx('relative inline-block text-left', className)}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-label="Select Language"
        className={clsx(
          'flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] font-bold tracking-wide transition-all cursor-pointer select-none',
          'bg-gray-100 hover:bg-gray-200 dark:bg-white/6 dark:hover:bg-white/10',
          'border border-gray-200/80 dark:border-white/10 text-gray-700 dark:text-gray-200',
          isOpen && 'ring-1 ring-primary-500/50 border-primary-500/50',
          buttonClassName
        )}
      >
        <span className="font-mono">{activeOption.label}</span>
        <ChevronDown
          size={13}
          className={clsx(
            'transition-transform duration-200 text-gray-400 dark:text-gray-400',
            isOpen && (direction === 'up' ? '-rotate-180' : 'rotate-180')
          )}
        />
      </button>

      {/* Floating Menu Popover */}
      {isOpen && (
        <div
          style={{
            borderColor: 'rgba(var(--theme-primary-rgb), 0.25)',
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.18)',
          }}
          className={clsx(
            'absolute z-50 min-w-[145px] p-1 rounded-xl border bg-white dark:bg-[#0c120f] backdrop-blur-md transition-all',
            direction === 'up' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
            align === 'end' ? 'right-0' : 'left-0'
          )}
        >
          <div className="space-y-0.5">
            {SUPPORTED_LANGUAGES.map((lang) => {
              const isActive = language === lang.code
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => handleSelect(lang.code)}
                  style={
                    isActive
                      ? {
                          backgroundColor: 'rgba(var(--theme-primary-rgb), 0.12)',
                          color: 'var(--theme-primary)',
                        }
                      : {}
                  }
                  className={clsx(
                    'w-full flex items-center justify-between gap-2.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer select-none text-left',
                    isActive
                      ? 'font-bold'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/6'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={clsx(
                        'px-1 py-0.5 rounded text-[10px] font-mono font-bold leading-none',
                        isActive
                          ? 'bg-primary-500/20 text-primary-500'
                          : 'bg-gray-100 dark:bg-white/8 text-gray-500 dark:text-gray-400'
                      )}
                    >
                      {lang.label}
                    </span>
                    <span className="text-xs">{lang.nativeName}</span>
                  </div>

                  {isActive && (
                    <Check
                      size={14}
                      className="shrink-0"
                      style={{ color: 'var(--theme-primary)' }}
                    />
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
