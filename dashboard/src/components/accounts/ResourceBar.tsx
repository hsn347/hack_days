import React from 'react'
import { useTranslation } from 'react-i18next'
import type { Resources } from '../../types'

// Resource icons — إما صور اللعبة أو fallback emoji
const RESOURCE_META = [
  { key: 'stamina',  emoji: '⚡', color: 'text-yellow-400', label: 'resources.stamina' },
  { key: 'food',     emoji: '🌾', color: 'text-green-400',  label: 'resources.food'    },
  { key: 'wood',     emoji: '🪵', color: 'text-amber-400',  label: 'resources.wood'    },
  { key: 'iron',     emoji: '⚙️', color: 'text-gray-300',   label: 'resources.iron'    },
  { key: 'diamond',  emoji: '💎', color: 'text-blue-400',   label: 'resources.diamond' },
  { key: 'gold',     emoji: '🪙', color: 'text-yellow-500', label: 'resources.gold'    },
] as const

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

interface ResourceBarProps {
  resources: Resources
  compact?: boolean
}

export function ResourceBar({ resources, compact }: ResourceBarProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-wrap gap-2 items-center">
      {RESOURCE_META.map(({ key, emoji, color, label }) => {
        const val = resources[key as keyof Resources]
        if (typeof val !== 'number') return null
        return (
          <div
            key={key}
            className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-white/6 border border-white/8 text-xs"
            title={t(label)}
          >
            <span className={color}>{emoji}</span>
            <span className="text-gray-300 font-medium">{formatNum(val)}</span>
          </div>
        )
      })}
    </div>
  )
}
