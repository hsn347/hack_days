import React from 'react'
import { clsx } from 'clsx'
import { useTranslation } from 'react-i18next'
import type { TaskTab } from '../../types'

// مطابق للموقع المرجعي بالضبط
export const TABS: { id: TaskTab; emoji: string; label: string }[] = [
  { id: 'gather',    emoji: '🌾', label: 'جمع الموارد'       },
  { id: 'train',     emoji: '⚔️', label: 'التدريب العسكري'   },
  { id: 'combat',    emoji: '🗡️', label: 'الهجوم'            },
  { id: 'watermill', emoji: '🌊', label: 'مكافأة الطاحونة'   },
  { id: 'transport', emoji: '🔗', label: 'مساعدة الموارد'    },
  { id: 'prestige',  emoji: '🎁', label: 'مهام الهيبة'       },
  { id: 'daily',     emoji: '📅', label: 'المهام اليومية'     },
  { id: 'building',  emoji: '🔼', label: 'التطوير والمكافآت' },
  { id: 'events',    emoji: '🏆', label: 'الفعاليات'         },
  { id: 'gold',      emoji: '🔍', label: 'البحث عن الذهب'    },
]

interface TaskTabsProps {
  active: TaskTab
  onChange: (t: TaskTab) => void
  errorTab?: TaskTab | null
}

export function TaskTabs({ active, onChange, errorTab }: TaskTabsProps) {
  const { t } = useTranslation()
  const scrollRef = React.useRef<HTMLDivElement>(null)

  const scroll = (dir: 'left' | 'right') => {
    if (!scrollRef.current) return
    scrollRef.current.scrollBy({ left: dir === 'left' ? -160 : 160, behavior: 'smooth' })
  }

  return (
    <div
      className="task-tabs-nav"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '14px',
        padding: '4px',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Arrow left */}
      <button
        type="button"
        onClick={() => scroll('left')}
        className="task-tabs-arrow"
        style={{
          flexShrink: 0, padding: '4px 8px',
          borderRadius: '8px', border: 'none',
          background: 'none', color: '#6b7280',
          cursor: 'pointer', fontSize: '16px',
          display: 'flex', alignItems: 'center',
        }}
      >
        ‹
      </button>

      {/* Tabs list */}
      <div
        ref={scrollRef}
        style={{
          display: 'flex', alignItems: 'center',
          gap: '4px', flex: 1,
          overflowX: 'auto',
          scrollbarWidth: 'none',
        }}
      >
        {TABS.map(tab => {
          const isActive = active === tab.id
          const isError = errorTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onChange(tab.id)}
              className={clsx('task-tab-item', isActive && 'active', isError && 'has-error')}
              style={{
                flexShrink: 0,
                display: 'flex', alignItems: 'center', gap: '5px',
                padding: '5px 9px',
                borderRadius: '8px',
                border: isError
                  ? '1px solid rgba(239,68,68,0.7)'
                  : isActive
                  ? '1px solid rgba(34,197,94,0.35)'
                  : '1px solid transparent',
                background: isError
                  ? 'rgba(239,68,68,0.14)'
                  : isActive
                  ? 'linear-gradient(135deg, rgba(5,150,105,0.25) 0%, rgba(16,185,129,0.15) 100%)'
                  : 'none',
                color: isError ? '#fca5a5' : isActive ? '#6ee7b7' : '#9ca3af',
                fontSize: '12px',
                fontWeight: isActive ? 600 : 400,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s',
                fontFamily: 'inherit',
              }}
            >
              <span style={{ fontSize: '13px', lineHeight: 1 }}>{tab.emoji}</span>
              <span>{t(`tabs.${tab.id}`, tab.label)}</span>
              {isError && (
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: '#ef4444',
                    boxShadow: '0 0 6px #ef4444',
                    display: 'inline-block',
                  }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* Arrow right */}
      <button
        type="button"
        onClick={() => scroll('right')}
        className="task-tabs-arrow"
        style={{
          flexShrink: 0, padding: '4px 8px',
          borderRadius: '8px', border: 'none',
          background: 'none', color: '#6b7280',
          cursor: 'pointer', fontSize: '16px',
          display: 'flex', alignItems: 'center',
        }}
      >
        ›
      </button>
    </div>
  )
}
