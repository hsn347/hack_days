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

function formatNum(n: number): string {
  if (n >= 1_000_000_000) {
    const val = Math.floor(n / 100_000_000) / 10
    return `${Number.isInteger(val) ? val.toFixed(0) : val.toFixed(1)}B`
  }
  if (n >= 1_000_000) {
    const val = Math.floor(n / 100_000) / 10
    return `${Number.isInteger(val) ? val.toFixed(0) : val.toFixed(1)}M`
  }
  if (n >= 1_000) {
    const val = Math.floor(n / 100) / 10
    return `${Number.isInteger(val) ? val.toFixed(0) : val.toFixed(1)}K`
  }
  return String(n)
}

interface ResourceBarProps {
  resources: Resources
  compact?: boolean
}

export function ResourceBar({ resources, compact }: ResourceBarProps) {
  const { t } = useTranslation()
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({})

  return (
    <div className={`grid grid-cols-3 sm:flex sm:flex-wrap items-center ${compact ? 'gap-1.5' : 'gap-2'}`}>
      {RESOURCE_META.map(({ key, icon, emoji, color, label }) => {
        const val = resources[key as keyof Resources]
        if (typeof val !== 'number') return null
        const hasError = !!imgErrors[key]

        return (
          <div
            key={key}
            className={`resource-bar-chip flex items-center rounded-lg bg-white/5 hover:bg-white/10 border border-white/8 transition-all ${
              compact ? 'gap-1 px-1.5 py-0.5 text-[11px]' : 'gap-1.5 px-2 py-1 text-xs'
            }`}
            title={`${t(label)}: ${val.toLocaleString()}`}
          >
            {icon && !hasError ? (
              <img
                src={icon}
                alt={key}
                className={`${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} object-contain shrink-0 filter drop-shadow-sm select-none`}
                onError={() => setImgErrors(prev => ({ ...prev, [key]: true }))}
              />
            ) : (
              <span className={`${color} shrink-0`}>{emoji}</span>
            )}
            <span className="resource-bar-val text-gray-200 font-semibold tabular-nums">
              {formatNum(val)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
