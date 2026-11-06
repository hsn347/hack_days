import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Resources } from '../../types'

// Resource icons — صور الموارد الحقيقية من ملفات اللعبة مع fallback emoji
export const RESOURCE_META = [
  { key: 'stamina', icon: '/images/resources/dayaniklilik_2.png', emoji: '⚡', color: 'text-yellow-400', label: 'resources.stamina' },
  { key: 'food',    icon: '/images/resources/tahil.png',          emoji: '🌾', color: 'text-green-400',  label: 'resources.food'    },
  { key: 'wood',    icon: '/images/resources/odun.png',           emoji: '🪵', color: 'text-amber-400',  label: 'resources.wood'    },
  { key: 'iron',    icon: '/images/resources/demir.png',          emoji: '⚙️', color: 'text-gray-300',   label: 'resources.iron'    },
  { key: 'diamond', icon: '/images/resources/kuvars.png',         emoji: '💎', color: 'text-blue-400',   label: 'resources.diamond' },
  { key: 'gold',    icon: '/images/resources/altin.png',          emoji: '🪙', color: 'text-yellow-500', label: 'resources.gold'    },
] as const

export function formatNum(n: number): string {
  if (!n || isNaN(n) || n <= 0) return '0'
  if (n >= 1_000_000_000) {
    const val = n / 1_000_000_000
    return `${val.toFixed(1).replace(/\.0$/, '')}B`
  }
  if (n >= 1_000_000) {
    const val = n / 1_000_000
    return `${val.toFixed(1).replace(/\.0$/, '')}M`
  }
  if (n >= 1_000) {
    const val = n / 1_000
    return `${val.toFixed(1).replace(/\.0$/, '')}K`
  }
  return String(Math.floor(n))
}

interface ResourceBarProps {
  resources: Resources
  compact?: boolean
}

export function ResourceBar({ resources, compact }: ResourceBarProps) {
  const { t } = useTranslation()
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({})

  return (
    <div className={`grid grid-cols-3 sm:grid-cols-6 ${compact ? 'gap-1' : 'gap-1.5 sm:gap-2'} select-none`}>
      {RESOURCE_META.map(({ key, icon, emoji, color, label }) => {
        const val = resources[key as keyof Resources]
        if (typeof val !== 'number') return null
        const hasError = !!imgErrors[key]

        // استخراج الموارد غير المحفوظة إن وُجدت لهذا المورد
        const unprotectKey = `unprotected_${key}` as keyof Resources
        const unprotectVal = typeof resources[unprotectKey] === 'number' ? (resources[unprotectKey] as number) : undefined
        const hasUnprotected = ['food', 'wood', 'iron', 'diamond'].includes(key) && unprotectVal !== undefined

        const titleText = hasUnprotected
          ? `${t(label)}: ${val.toLocaleString()} (${t('resources.unprotected')}: ${unprotectVal.toLocaleString()})`
          : `${t(label)}: ${val.toLocaleString()}`

        return (
          <div
            key={key}
            className={`resource-bar-chip flex items-center rounded-lg bg-gray-100/90 dark:bg-white/5 hover:bg-gray-200/90 dark:hover:bg-white/10 border border-gray-200/80 dark:border-white/8 transition-all min-w-0 ${
              compact ? 'gap-1 px-1.5 py-1 min-h-[34px]' : 'gap-1.5 px-2 py-1 min-h-[38px]'
            }`}
            title={titleText}
          >
            {/* Icon */}
            <div className="shrink-0 flex items-center justify-center">
              {icon && !hasError ? (
                <img
                  src={icon}
                  alt={key}
                  className={`${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} object-contain filter drop-shadow-xs select-none`}
                  onError={() => setImgErrors(prev => ({ ...prev, [key]: true }))}
                />
              ) : (
                <span className={`${color} shrink-0 text-xs sm:text-sm`}>{emoji}</span>
              )}
            </div>

            {/* Numbers: Stacked vertically */}
            <div className="flex flex-col justify-center min-w-0 leading-tight flex-1">
              {/* الرصيد الإجمالي المباشر */}
              <span className="resource-bar-val text-gray-900 dark:text-gray-100 font-bold tabular-nums text-[11px] sm:text-xs truncate">
                {formatNum(val)}
              </span>

              {/* الموارد غير المحفوظة بالأحمر في كلا الوضعين */}
              {hasUnprotected ? (
                <span
                  className="resource-bar-unprotected text-[#dc2626] dark:text-[#f87171] font-bold tabular-nums text-[9px] sm:text-[10px] leading-none mt-0.5 truncate"
                  title={`${t('resources.unprotected')}: ${unprotectVal.toLocaleString()}`}
                >
                  {formatNum(unprotectVal)}
                </span>
              ) : (
                <span className="text-gray-400 dark:text-gray-500 font-medium text-[9px] sm:text-[10px] leading-none mt-0.5 truncate">
                  {t(label)}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
