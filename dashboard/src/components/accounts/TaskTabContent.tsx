import React, { useState, useEffect, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Plus, Minus, Trash2, Check, RotateCcw, Loader2, SlidersHorizontal, Edit3 } from 'lucide-react'
import { clsx } from 'clsx'
import { Toggle } from '../ui/Toggle'
import { TaskTabs } from './TaskTabs'
import { useUpdateCastleConfig } from '../../hooks/useCastles'
import type { Castle, TaskTab, CastleConfig, GoldLocation } from '../../types'
import { useTranslation } from 'react-i18next'
import toast from 'react-hot-toast'

/** يحسب عدد الإعدادات الفردية المختلفة بين الإعداد الأصلي والمسودة */
export function countConfigChanges(original: unknown, draft: unknown): number {
  if (original === draft) return 0
  if (original == null || draft == null) return 1
  if (typeof original !== 'object' || typeof draft !== 'object') {
    return original !== draft ? 1 : 0
  }
  if (Array.isArray(original) || Array.isArray(draft)) {
    return JSON.stringify(original) !== JSON.stringify(draft) ? 1 : 0
  }
  let count = 0
  const origObj = original as Record<string, unknown>
  const draftObj = draft as Record<string, unknown>
  const allKeys = new Set([...Object.keys(origObj), ...Object.keys(draftObj)])
  for (const key of allKeys) {
    const oVal = origObj[key]
    const dVal = draftObj[key]
    if (typeof oVal === 'object' && typeof dVal === 'object' && oVal !== null && dVal !== null && !Array.isArray(oVal) && !Array.isArray(dVal)) {
      count += countConfigChanges(oVal, dVal)
    } else {
      if (JSON.stringify(oVal) !== JSON.stringify(dVal)) {
        count += 1
      }
    }
  }
  return count
}

// ─── Shared Helper Components ───────────────────────────────────────────────

/** محدد وزر رقمي مدمج وأنيق يدعم الكتابة المباشرة والأزرار */
function Stepper({
  value,
  min = 1,
  max = 99,
  step = 1,
  onChange,
  formatLabel,
}: {
  value: number
  min?: number
  max?: number
  step?: number
  onChange: (v: number) => void
  formatLabel?: (v: number) => string | React.ReactNode
}) {
  const [isFocused, setIsFocused] = useState(false)
  const [textValue, setTextValue] = useState(String(value))
  const [hasError, setHasError] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isFocused) {
      setTextValue(String(value))
      setHasError(false)
    }
  }, [value, isFocused])

  const handleStep = (delta: number) => {
    const next = Math.min(max, Math.max(min, (Number(value) || 0) + delta * step))
    onChange(next)
    setTextValue(String(next))
    setHasError(false)
  }

  const commitValue = (valStr: string) => {
    const trimmed = valStr.trim()
    if (trimmed === '') {
      setTextValue(String(value))
      setHasError(false)
      return
    }
    const parsed = parseInt(trimmed, 10)
    if (isNaN(parsed)) {
      setTextValue(String(value))
      setHasError(false)
      return
    }
    const clamped = Math.min(max, Math.max(min, parsed))
    onChange(clamped)
    setTextValue(String(clamped))
    setHasError(false)
  }

  return (
    <div
      className={clsx(
        'inline-flex items-center bg-black/60 shadow-sm border border-white/10 rounded-md h-6 overflow-hidden transition-all duration-150 select-none task-stepper shrink-0',
        isFocused
          ? hasError
            ? 'border-rose-500 ring-1 ring-rose-500/40'
            : 'border-emerald-400 ring-1 ring-emerald-500/40'
          : 'hover:border-emerald-500/40'
      )}
      style={{ direction: 'ltr' }}
    >
      {/* Minus button */}
      <button
        type="button"
        disabled={value <= min}
        onClick={() => handleStep(-1)}
        className="flex justify-center items-center bg-white/[0.03] hover:bg-emerald-500/20 active:bg-emerald-500/30 disabled:hover:bg-transparent disabled:opacity-20 border-white/5 border-r w-5 h-6 text-gray-300 hover:text-emerald-300 transition-colors cursor-pointer disabled:cursor-not-allowed task-stepper-btn shrink-0"
        title={`- (${min})`}
      >
        <Minus size={10} strokeWidth={2.5} />
      </button>

      {/* Center Numeric Pod */}
      <div
        onClick={() => inputRef.current?.focus()}
        className={clsx(
          'relative flex justify-center items-center px-0.5 h-6 transition-colors cursor-text task-stepper-pod shrink-0',
          formatLabel ? 'w-auto min-w-[50px] px-1.5' : 'w-7 min-w-[28px] max-w-[28px]',
          isFocused ? 'bg-black/90' : 'bg-black/30 hover:bg-black/50'
        )}
        title={`(${min} - ${max})`}
      >
        <input
          ref={inputRef}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          value={isFocused ? textValue : (formatLabel ? '' : value)}
          placeholder={formatLabel ? String(formatLabel(value)) : String(value)}
          onFocus={(e) => {
            setIsFocused(true)
            setTextValue(String(value))
            setHasError(false)
            setTimeout(() => e.target.select(), 10)
          }}
          onChange={(e) => {
            const clean = e.target.value.replace(/[^0-9]/g, '')
            setTextValue(clean)
            if (clean === '') {
              setHasError(false)
              return
            }
            const num = parseInt(clean, 10)
            if (!isNaN(num)) {
              if (num > max || num < min) {
                setHasError(true)
              } else {
                setHasError(false)
                onChange(num)
              }
            }
          }}
          onBlur={() => {
            setIsFocused(false)
            commitValue(textValue)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.currentTarget.blur()
            } else if (e.key === 'Escape') {
              setTextValue(String(value))
              setIsFocused(false)
              setHasError(false)
              e.currentTarget.blur()
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              handleStep(e.shiftKey ? 5 : 1)
            } else if (e.key === 'ArrowDown') {
              e.preventDefault()
              handleStep(e.shiftKey ? -5 : -1)
            }
          }}
          style={{ width: '100%', minWidth: 0 }}
          className="bg-transparent selection:bg-emerald-500/40 px-0 outline-none font-mono font-bold text-emerald-400 text-xs text-center cursor-text task-stepper-input"
        />

        {/* Formatted label overlay when blurred */}
        {!isFocused && formatLabel && (
          <span className="absolute inset-0 flex justify-center items-center px-1 font-bold text-[11px] text-emerald-400 whitespace-nowrap pointer-events-none task-stepper-label">
            {formatLabel(value)}
          </span>
        )}
      </div>

      {/* Plus button */}
      <button
        type="button"
        disabled={value >= max}
        onClick={() => handleStep(1)}
        className="flex justify-center items-center bg-white/[0.03] hover:bg-emerald-500/20 active:bg-emerald-500/30 disabled:hover:bg-transparent disabled:opacity-20 border-white/5 border-l w-5 h-6 text-gray-300 hover:text-emerald-300 transition-colors cursor-pointer disabled:cursor-not-allowed task-stepper-btn shrink-0"
        title={`+ (${max})`}
      >
        <Plus size={10} strokeWidth={2.5} />
      </button>
    </div>
  )
}

/** بطاقة مورد قابلة للتحديد */
function ResCard({ img, label, selected, onClick }: { img: string; label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx('task-res-card', selected ? 'selected' : 'unselected')}
      style={{
        flex: '1 1 0',
        minWidth: '68px',
        padding: '8px 6px',
        borderRadius: '10px',
        border: selected ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
        background: selected ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
        cursor: 'pointer',
        transition: 'all 0.15s',
        color: selected ? '#6ee7b7' : '#9ca3af',
        fontSize: '11px', fontWeight: selected ? 600 : 400,
        fontFamily: 'inherit',
      }}
    >
      <img src={img} alt={label} style={{ width: '28px', height: '28px', objectFit: 'contain' }}
        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
      />
      {label}
    </button>
  )
}

// ─── Task Accordion Context (قائمة منسدلة أحادية: واحدة فقط تفتح في نفس الوقت) ──
interface TaskAccordionContextValue {
  expandedTaskId: string | null
  toggleTask: (id: string) => void
}

const TaskAccordionContext = React.createContext<TaskAccordionContextValue>({
  expandedTaskId: null,
  toggleTask: () => {},
})

/** صف مهمة مع toggle وقائمة منسدلة للخيارات الفرعية بسهم مميز */
function TaskRow({
  id, img, emoji, label, enabled, onToggle, children, comingSoon,
}: {
  id?: string; img?: string; emoji?: string; label: string;
  enabled: boolean; onToggle: (v: boolean) => void;
  children?: React.ReactNode; comingSoon?: boolean;
}) {
  const { expandedTaskId, toggleTask } = React.useContext(TaskAccordionContext)
  const taskId = id || label
  const hasOptions = Boolean(children)
  const isOpen = hasOptions && expandedTaskId === taskId
  const rowRef = useRef<HTMLDivElement>(null)

  // انتقال سلس وسريع: توسيط المكون في الشاشة، أو إظهار أعلاه إذا كان أطول من الشاشة
  useEffect(() => {
    if (isOpen && rowRef.current) {
      const timer = setTimeout(() => {
        if (!rowRef.current) return
        const rect = rowRef.current.getBoundingClientRect()
        const isMobile = window.innerWidth < 768
        const headerOffset = isMobile ? 65 : 24
        const bottomOffset = isMobile ? 65 : 0
        const usableHeight = window.innerHeight - headerOffset - bottomOffset
        const elementHeight = rect.height

        let targetY: number
        if (elementHeight >= usableHeight) {
          // إذا كان المكون أطول من الشاشة: يظهر أعلى المكون مباشرة أسفل الهيدر
          targetY = window.scrollY + rect.top - headerOffset - 8
        } else {
          // إذا كان المكون يتسع في الشاشة: يتم توسيطه عمودياً في المنتصف تماماً
          const verticalPadding = (usableHeight - elementHeight) / 2
          targetY = window.scrollY + rect.top - headerOffset - verticalPadding
        }

        window.scrollTo({
          top: Math.max(0, Math.round(targetY)),
          behavior: 'smooth',
        })
      }, 75)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  return (
    <div
      ref={rowRef}
      className={clsx(
        'transition-all duration-200 task-row-card',
        enabled && !comingSoon ? 'enabled' : 'disabled',
        comingSoon && 'coming-soon',
        isOpen && 'task-row-expanded shadow-md'
      )}
      style={{
        background: enabled && !comingSoon
          ? (isOpen ? 'rgba(16,185,129,0.08)' : 'rgba(16,185,129,0.05)')
          : (isOpen ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.03)'),
        border: enabled && !comingSoon
          ? (isOpen ? '1.5px solid rgba(34,197,94,0.35)' : '1px solid rgba(34,197,94,0.18)')
          : (isOpen ? '1.5px solid rgba(255,255,255,0.14)' : '1px solid rgba(255,255,255,0.08)'),
        borderRadius: '12px',
        overflow: 'hidden',
      }}
    >
      <div
        onClick={() => {
          if (comingSoon) return
          if (hasOptions) {
            toggleTask(taskId)
          } else {
            onToggle(!enabled)
          }
        }}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 12px', gap: '10px',
          cursor: comingSoon ? 'default' : 'pointer',
          userSelect: 'none',
        }}
        className="hover:bg-white/[0.04] active:bg-white/[0.06] transition-colors task-row-header"
      >
        {/* الطرف الأيمن: أيقونة المهمة واسمها */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
          {img ? (
            <img src={img} alt={label} style={{ width: '26px', height: '26px', objectFit: 'contain', flexShrink: 0 }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : emoji ? (
            <span style={{ fontSize: '18px', flexShrink: 0 }}>{emoji}</span>
          ) : null}
          <div style={{ minWidth: 0 }}>
            <div className="task-row-label" style={{ color: comingSoon ? '#6b7280' : '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>
              {label}
            </div>
          </div>
        </div>

        {/* الطرف الأيسر: السهم المميز (فقط للمهام ذات الخيارات) + زر التفعيل Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          {hasOptions && (
            <button
              type="button"
              aria-label="Toggle options"
              onClick={(e) => {
                e.stopPropagation()
                toggleTask(taskId)
              }}
              className={clsx(
                'flex justify-center items-center rounded-lg transition-all duration-200 cursor-pointer task-accordion-arrow',
                isOpen
                  ? 'is-open bg-amber-500/25 text-amber-300 border border-amber-500/50 shadow-xs ring-1 ring-amber-500/30'
                  : 'bg-white/[0.07] text-gray-300 hover:text-white hover:bg-white/12 border border-white/10'
              )}
              style={{
                width: '28px',
                height: '28px',
              }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                style={{
                  width: '16px',
                  height: '16px',
                  transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              >
                <path
                  fillRule="evenodd"
                  d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          )}

          <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', alignItems: 'center' }}>
            <Toggle value={enabled} onChange={onToggle} disabled={comingSoon} size="sm" />
          </div>
        </div>
      </div>

      {/* محتوى الخيارات: يظهر فقط عند فتح القائمة */}
      {hasOptions && !comingSoon && isOpen && (
        <div
          className="animate-in duration-200 task-row-children fade-in-50"
          style={{
            padding: '0 12px 12px',
            borderTop: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div style={{ paddingTop: '10px' }}>{children}</div>
        </div>
      )}
    </div>
  )
}

/** عنوان قسم */
function SectionLabel({ text }: { text: string }) {
  return <div className="task-section-label" style={{ color: '#9ca3af', fontSize: '12px', fontWeight: 500, marginBottom: '8px' }}>{text}</div>
}

// ─── Resource definitions ────────────────────────────────────────────────────

const MARCH_RESOURCES = [
  { v: 2, img: '/images/gather/mtahil.png', resKey: 'resources.food' },
  { v: 3, img: '/images/gather/modun.png',  resKey: 'resources.wood' },
  { v: 4, img: '/images/gather/mdemir.png', resKey: 'resources.iron' },
  { v: 5, img: '/images/gather/mkuvars.png',resKey: 'resources.diamond' },
  { v: 1, img: '/images/gather/altin.png',  resKey: 'resources.gold' },
]

const TRANSPORT_RESOURCES = [
  { id: 1002, img: '/images/resources/mtahil.png', resKey: 'resources.food' },
  { id: 1003, img: '/images/resources/modun.png',  resKey: 'resources.wood' },
  { id: 1004, img: '/images/resources/mdemir.png', resKey: 'resources.iron' },
  { id: 1005, img: '/images/resources/mkuvars.png',resKey: 'resources.diamond' },
]

const WATERMILL_RESOURCES = [
  { key: 'food',    img: '/images/watermill/uretimtahil.png',  resKey: 'resources.food'    },
  { key: 'wood',    img: '/images/watermill/uretimodun.png',   resKey: 'resources.wood'    },
  { key: 'iron',    img: '/images/watermill/uretimdemir.png',  resKey: 'resources.iron'    },
  { key: 'diamond', img: '/images/watermill/uretimkuvars.png', resKey: 'resources.diamond' },
]

const FOUNTAIN_RESOURCES = [
  { key: 'food',    resKey: 'resources.food',    img: '/images/fountain/food.png' },
  { key: 'wood',    resKey: 'resources.wood',    img: '/images/fountain/wood.png' },
  { key: 'iron',    resKey: 'resources.iron',    img: '/images/fountain/iron.png' },
  { key: 'coal',    resKey: 'tasks.matCoal',     img: '/images/fountain/coal.png' },
  { key: 'diamond', resKey: 'resources.diamond', img: '/images/fountain/diamond.png' },
] as const

// أنواع القوات والتدريب العسكري
const BARRACKS_TYPES = [
  { key: 'infantry', labelKey: 'tasks.infantry' },
  { key: 'cavalry',  labelKey: 'tasks.cavalry'  },
  { key: 'archers',  labelKey: 'tasks.archers'  },
  { key: 'chariots', labelKey: 'tasks.chariots' },
]

const PETS = [
  { name: 'غزال', labelKey: 'tasks.petDeer' },
  { name: 'أسد',  labelKey: 'tasks.petLion' },
  { name: 'صقر',  labelKey: 'tasks.petFalcon' },
  { name: 'ذئب',  labelKey: 'tasks.petWolf' },
  { name: 'نمر',  labelKey: 'tasks.petTiger' },
  { name: 'دب',   labelKey: 'tasks.petBear' },
  { name: 'فيل',  labelKey: 'tasks.petElephant' },
  { name: 'تنين', labelKey: 'tasks.petDragon' },
]

interface StrategyItem {
  id: number
  name_en: string
  name_ar: string
  img: string
  category: 'battle' | 'development' | 'help'
}

const STRATEGY_ITEMS: StrategyItem[] = [
  // ⚔️ Battle
  { id: 91010000, name_en: 'Empty Fort',        name_ar: 'القلعة الفارغة', img: 'bos_hisar.png',        category: 'battle' },
  { id: 91010015, name_en: 'Mount Mastery',     name_ar: 'قمة الإتقان',   img: 'ustalik_dagi.png',     category: 'battle' },
  { id: 91010012, name_en: 'Odd Archery',       name_ar: 'الرماية الفردية', img: 'tekli_okculuk.png',    category: 'battle' },
  { id: 91010014, name_en: 'Eye of the Needle', name_ar: 'عين الإبرة',     img: 'ignenin_gozu.png',     category: 'battle' },
  { id: 91010013, name_en: 'Skilled Spearplay', name_ar: 'رمح المهارة',   img: 'vasifli_mizrakci.png', category: 'battle' },
  { id: 91010016, name_en: 'Lightning Speed',   name_ar: 'سرعة البرق',     img: 'yildirim_hizi.png',    category: 'battle' },

  // 🏗️ Development
  { id: 91010001, name_en: 'Complete Search',   name_ar: 'البحث الكامل',   img: 'aramayi_tamamla.png',  category: 'development' },
  { id: 91010002, name_en: 'Full Room',         name_ar: 'الغرفة الكاملة', img: 'tam_oda.png',          category: 'development' },
  { id: 91010011, name_en: 'Literary Pursuits', name_ar: 'المساعي الأدبية',img: 'edebi_arayislar.png',  category: 'development' },
  { id: 91010003, name_en: 'Washing Waves',     name_ar: 'أمواج الغسيل',   img: 'yikama_dalgalari.png', category: 'development' },

  // 🛡️ Help
  { id: 91010004, name_en: 'Born For War',      name_ar: 'وُلد للحرب',     img: 'savas_icin_dogmak.png', category: 'help' },
  { id: 91010009, name_en: 'Cavalry Practice',  name_ar: 'تدريب الفرسان',  img: 'suvari_tatbikati.png',  category: 'help' },
  { id: 91010006, name_en: 'Infantry Practice', name_ar: 'تدريب المشاة',   img: 'piyade_tatbikati.png',  category: 'help' },
  { id: 91010007, name_en: 'Archer Practice',   name_ar: 'تدريب الرماة',   img: 'okcu_tatbikati.png',    category: 'help' },
  { id: 91010005, name_en: 'Bottomless',        name_ar: 'بلا قاع',        img: 'dipsiz.png',            category: 'help' },
  { id: 91010010, name_en: 'Smoke Bomb',        name_ar: 'القنبلة الدخانية',img: 'sis_bombasi.png',      category: 'help' },
  { id: 91010008, name_en: 'Chariot Practice',  name_ar: 'تدريب العربات',  img: 'araba_tatbikati.png',   category: 'help' },
]

const STRATEGY_TABS = [
  { id: 'battle',      label_en: 'Battle',      label_ar: 'قتال',  icon: '⚔️' },
  { id: 'development', label_en: 'Development', label_ar: 'تطوير', icon: '🏗️' },
  { id: 'help',        label_en: 'Help',        label_ar: 'دعم',   icon: '🛡️' },
] as const

function isStrategySelected(currentVal: any, item: StrategyItem): boolean {
  if (!currentVal && item.id === 91010000) return true
  if (currentVal === item.id || currentVal === String(item.id)) return true
  if (currentVal === item.name_ar || currentVal === item.name_en) return true
  if (item.id === 91010000 && (currentVal === 'القلعة الفارغة' || currentVal === 'Empty Fort' || currentVal === 'empty castle')) return true
  if (item.id === 91010015 && (currentVal === 'قمة الاتقان' || currentVal === 'قمة الإتقان' || currentVal === 'Mount Mastery')) return true
  if (item.id === 91010012 && (currentVal === 'الرماية الفردية' || currentVal === 'Odd Archery')) return true
  if (item.id === 91010014 && (currentVal === 'الضرر الجانبي' || currentVal === 'عين الإبرة' || currentVal === 'Eye of the Needle')) return true
  if (item.id === 91010013 && (currentVal === 'الرمح الثاقب' || currentVal === 'رمح المهارة' || currentVal === 'Skilled Spearplay')) return true
  if (item.id === 91010016 && (currentVal === 'سرعة البرق' || currentVal === 'Lightning Speed')) return true
  if (item.id === 91010001 && (currentVal === 'البحث الكامل' || currentVal === 'Complete Search' || currentVal === 'Complete Research')) return true
  if (item.id === 91010002 && (currentVal === 'التعزيز الكامل' || currentVal === 'الغرفة الكاملة' || currentVal === 'Full Room')) return true
  if (item.id === 91010011 && (currentVal === 'المساعي الاكاديمية' || currentVal === 'المساعي الأكاديمية' || currentVal === 'المساعي الأدبية' || currentVal === 'Literary Pursuits')) return true
  if (item.id === 91010003 && (currentVal === 'السيل الدافق' || currentVal === 'أمواج الغسيل' || currentVal === 'Washing Waves')) return true
  if (item.id === 91010004 && (currentVal === 'جنود الحرب' || currentVal === 'وُلد للحرب' || currentVal === 'Born For War')) return true
  if (item.id === 91010009 && (currentVal === 'التدريب المكثف للفرسان' || currentVal === 'تدريب الفرسان' || currentVal === 'Cavalry Practice')) return true
  if (item.id === 91010006 && (currentVal === 'التدريب الجدي للمشاة' || currentVal === 'تدريب المشاة' || currentVal === 'Infantry Practice')) return true
  if (item.id === 91010007 && (currentVal === 'تدريب مكثف للرماة والنشاب' || currentVal === 'تدريب الرماة' || currentVal === 'Archer Practice')) return true
  if (item.id === 91010005 && (currentVal === 'القعر العميق' || currentVal === 'بلا قاع' || currentVal === 'Bottomless')) return true
  if (item.id === 91010010 && (currentVal === 'القنبلة الدخانية' || currentVal === 'Smoke Bomb')) return true
  if (item.id === 91010008 && (currentVal === 'التدريب المكثف للعربات' || currentVal === 'تدريب العربات' || currentVal === 'Chariot Practice')) return true
  return false
}

const STAMINA_GOLD_OPTIONS = [
  { count: 1,  gold: 60,   label: '1 مرة، إجمالي 60 ذهب' },
  { count: 2,  gold: 150,  label: '2 مرة، إجمالي 150 ذهب' },
  { count: 3,  gold: 270,  label: '3 مرة، إجمالي 270 ذهب' },
  { count: 4,  gold: 420,  label: '4 مرة، إجمالي 420 ذهب' },
  { count: 5,  gold: 600,  label: '5 مرة، إجمالي 600 ذهب' },
  { count: 6,  gold: 810,  label: '6 مرة، إجمالي 810 ذهب' },
  { count: 7,  gold: 1050, label: '7 مرة، إجمالي 1050 ذهب' },
  { count: 8,  gold: 1320, label: '8 مرة، إجمالي 1320 ذهب' },
  { count: 9,  gold: 1620, label: '9 مرة، إجمالي 1620 ذهب' },
  { count: 10, gold: 1950, label: '10 مرة، إجمالي 1950 ذهب' },
]

const WORKSHOP_MATERIALS = [
  { key: 'fang',  label: 'ناب',  labelKey: 'tasks.matFang',  img: 'dis.png'   },
  { key: 'fur',   label: 'فرو',  labelKey: 'tasks.matFur',   img: 'kurk.png'  },
  { key: 'metal', label: 'معدن', labelKey: 'tasks.matMetal', img: 'metal.png' },
  { key: 'coal',  label: 'فحم',  labelKey: 'tasks.matCoal',  img: 'komur.png' },
] as const

// ─── Style constants ─────────────────────────────────────────────────────────

const stepBtn: React.CSSProperties = {
  width: '28px', height: '28px', borderRadius: '8px',
  border: '1px solid rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.08)',
  color: '#6ee7b7', cursor: 'pointer', fontSize: '16px',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontFamily: 'inherit',
}

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.12)', borderRadius: '10px',
  padding: '9px 12px', fontSize: '13px', color: '#f0fdf4',
  outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
}

// ─── Main Component ──────────────────────────────────────────────────────────

interface Props {
  tab?: TaskTab
  initialTab?: TaskTab
  castle: Castle
  userId: string
  onTabChange?: (tab: TaskTab) => void
  isBatchMode?: boolean
  batchTargetCount?: number
  onBatchSave?: (changedSections: Partial<CastleConfig>) => Promise<void>
}

export function TaskTabContent({
  tab: externalTab,
  initialTab = 'gather',
  castle,
  userId,
  onTabChange,
  isBatchMode = false,
  batchTargetCount = 1,
  onBatchSave,
}: Props) {
  const { t, i18n } = useTranslation()
  const [internalTab, setInternalTab] = useState<TaskTab>(externalTab || initialTab)
  const [coordsError, setCoordsError] = useState(false)
  const [tacticsCategory, setTacticsCategory] = useState<'battle' | 'development' | 'help'>('battle')
  const [isSavingBatch, setIsSavingBatch] = useState(false)

  // حالة القائمة المنسدلة: مهمة واحدة فقط يمكن فتح خياراتها في الوقت نفسه
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)

  const toggleTaskAccordion = (id: string) => {
    setExpandedTaskId(prev => prev === id ? null : id)
  }

  // Local draft of castle.config — allows multiple edits without immediately saving to Firebase
  const [draftConfig, setDraftConfig] = useState<CastleConfig>(() =>
    JSON.parse(JSON.stringify(castle.config))
  )
  const [savedConfig, setSavedConfig] = useState<CastleConfig>(() =>
    JSON.parse(JSON.stringify(castle.config))
  )

  const lastSavedConfigRef = useRef<CastleConfig>(castle.config)
  const currentCastleIdRef = useRef<string>(castle.id)

  // Sync internalTab when externalTab changes
  useEffect(() => {
    if (externalTab && externalTab !== internalTab) {
      setInternalTab(externalTab)
    }
  }, [externalTab])

  const currentTab = externalTab ?? internalTab

  // إغلاق كافة القوائم المنسدلة عند تغيير التبويب (تكون كلها مقفلة افتراضياً)
  useEffect(() => {
    setExpandedTaskId(null)
  }, [currentTab])

  // Sync with Firestore when castle changes (switch castle or server refresh)
  useEffect(() => {
    if (currentCastleIdRef.current !== castle.id) {
      currentCastleIdRef.current = castle.id
      lastSavedConfigRef.current = castle.config
      const fresh = JSON.parse(JSON.stringify(castle.config))
      setSavedConfig(fresh)
      setDraftConfig(fresh)
      setCoordsError(false)
      return
    }
    if (JSON.stringify(lastSavedConfigRef.current) !== JSON.stringify(castle.config)) {
      lastSavedConfigRef.current = castle.config
      const fresh = JSON.parse(JSON.stringify(castle.config))
      setSavedConfig(fresh)
      setDraftConfig(fresh)
    }
  }, [castle.id, castle.config])

  const updateConfig = useUpdateCastleConfig(userId, castle.id)

  const changesCount = useMemo(() => {
    return countConfigChanges(savedConfig, draftConfig)
  }, [savedConfig, draftConfig])

  function update<K extends keyof CastleConfig>(key: K, patch: Partial<CastleConfig[K]>) {
    setDraftConfig(prev => {
      const current = (prev[key] || {}) as Record<string, unknown>
      return {
        ...prev,
        [key]: {
          ...current,
          ...(patch as Record<string, unknown>),
        } as CastleConfig[K],
      }
    })
  }

  const toggle = (key: keyof CastleConfig) => (v: boolean) =>
    update(key, { enabled: v } as Partial<CastleConfig[typeof key]>)

  const handleTabChange = (newTab: TaskTab) => {
    if (newTab === currentTab) return

    // التحقق من إحداثيات مساعدة الموارد إذا كانت مفعّلة
    const tr = draftConfig.march_manager?.transport
    if (tr?.enabled) {
      const hasX = tr.target_x != null && tr.target_x > 0
      const hasY = tr.target_y != null && tr.target_y > 0
      if (!hasX || !hasY) {
        toast.error('❌ يرجى إدخال إحداثيات الموقع (X و Y) لمساعدة الموارد قبل الانتقال لمهمة أخرى!', {
          id: 'transport-missing-coords',
          duration: 4500,
        })
        setCoordsError(true)
        if (currentTab !== 'transport') {
          setInternalTab('transport')
          onTabChange?.('transport')
        }
        return
      }
    }

    setCoordsError(false)
    setInternalTab(newTab)
    onTabChange?.(newTab)
  }

  const isPending = updateConfig.isPending || isSavingBatch

  const handleSave = async () => {
    if (changesCount === 0 || isPending) return

    // التحقق من إحداثيات مساعدة الموارد عند الحفظ
    const tr = draftConfig.march_manager?.transport
    if (tr?.enabled) {
      const hasX = tr.target_x != null && tr.target_x > 0
      const hasY = tr.target_y != null && tr.target_y > 0
      if (!hasX || !hasY) {
        toast.error('❌ لا يمكن الحفظ: يرجى إدخال إحداثيات الموقع (X و Y) لمساعدة الموارد أولاً!', {
          id: 'transport-missing-coords',
          duration: 4500,
        })
        setCoordsError(true)
        setInternalTab('transport')
        onTabChange?.('transport')
        return
      }
    }

    const changedSections: Partial<CastleConfig> = {}
    for (const key of Object.keys(draftConfig) as (keyof CastleConfig)[]) {
      if (JSON.stringify(draftConfig[key]) !== JSON.stringify(savedConfig[key])) {
        ;(changedSections as Record<string, unknown>)[key] = draftConfig[key]
      }
    }

    const origGg = (savedConfig as unknown as { gold_gather?: unknown }).gold_gather
    const draftGg = (draftConfig as unknown as { gold_gather?: unknown }).gold_gather
    if (JSON.stringify(draftGg) !== JSON.stringify(origGg)) {
      ;(changedSections as Record<string, unknown>).gold_gather = draftGg
    }

    if (isBatchMode && onBatchSave) {
      try {
        setIsSavingBatch(true)
        await onBatchSave(changedSections)
        const updated = JSON.parse(JSON.stringify(draftConfig))
        lastSavedConfigRef.current = updated
        setSavedConfig(updated)
        toast.success(t('common.success'))
      } catch (err) {
        toast.error(t('common.error') + ': ' + (err instanceof Error ? err.message : ''))
      } finally {
        setIsSavingBatch(false)
      }
      return
    }

    updateConfig.mutate(changedSections, {
      onSuccess: () => {
        const updated = JSON.parse(JSON.stringify(draftConfig))
        lastSavedConfigRef.current = updated
        setSavedConfig(updated)
        toast.success(t('common.success'))
      },
      onError: (err) => {
        toast.error(t('common.error') + ': ' + (err instanceof Error ? err.message : ''))
      },
    })
  }

  const handleCancel = () => {
    if (changesCount === 0) return
    setDraftConfig(JSON.parse(JSON.stringify(savedConfig)))
    toast.success(t('common.success'))
  }

  const cfg = draftConfig

  function renderTabContent() {
    const tab = currentTab
    // ─────────────────────────────────────────────────────────────────────────
    // 1. جمع الموارد (Gather)
    // ─────────────────────────────────────────────────────────────────────────
    if (tab === 'gather') {
    const g = cfg.march_manager.gather
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header toggle */}
        <div
          onClick={() => update('march_manager', { gather: { ...g, enabled: !g.enabled } })}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: g.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: g.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '14px', padding: '12px 14px',
            cursor: 'pointer', userSelect: 'none',
          }}
          className={clsx('transition-colors task-header-card', g.enabled ? 'enabled' : 'disabled')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/gather/mtahil.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div className="task-header-title" style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>{t('tasks.gatherResources')}</div>
            </div>
          </div>
          <Toggle value={g.enabled} onChange={v => update('march_manager', { gather: { ...g, enabled: v } })} />
        </div>

        {/* Sub-options only shown when enabled */}
        {g.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Level stepper */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <SectionLabel text={t('tasks.minResourceLevel')} />
              <Stepper value={g.level} min={1} max={7} onChange={v => update('march_manager', { gather: { ...g, level: v } })} />
            </div>

            {/* Resource type cards */}
            <div>
              <SectionLabel text={t('tasks.resourceType')} />
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {MARCH_RESOURCES.map(r => (
                  <ResCard
                    key={r.v}
                    img={r.img}
                    label={t(r.resKey)}
                    selected={g.res_type === r.v}
                    onClick={() => update('march_manager', { gather: { ...g, res_type: r.v } })}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 2. التدريب العسكري (Train)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'train') {
    const tr = cfg.train
    // Build list of active barracks (level > 0)
    type BarracksKey = 'infantry' | 'cavalry' | 'archers' | 'chariots'
    const activeList = (Object.keys(tr.levels) as BarracksKey[]).filter(k => tr.levels[k] > 0)
    const unusedTypes = BARRACKS_TYPES.filter(b => !activeList.includes(b.key as BarracksKey))

    const setLevel = (key: BarracksKey, lv: number) => {
      update('train', { levels: { ...tr.levels, [key]: lv } } as Partial<typeof tr>)
    }

    const removeBarracks = (key: BarracksKey) => {
      update('train', { levels: { ...tr.levels, [key]: 0 } } as Partial<typeof tr>)
    }

    const addBarracks = () => {
      if (unusedTypes.length === 0) return
      const next = unusedTypes[0]
      update('train', { levels: { ...tr.levels, [next.key]: 1 } } as Partial<typeof tr>)
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header */}
        <div
          onClick={() => toggle('train')(!tr.enabled)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: tr.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: tr.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '14px', padding: '12px 14px',
            cursor: 'pointer', userSelect: 'none',
          }}
          className={clsx('transition-colors task-header-card', tr.enabled ? 'enabled' : 'disabled')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>⚔️</span>
            <div>
              <div className="task-header-title" style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>{t('tasks.militaryTraining')}</div>
            </div>
          </div>
          <Toggle value={tr.enabled} onChange={toggle('train')} />
        </div>

        {/* Sub-options only shown when enabled */}
        {tr.enabled && (
          <>
            {/* Barracks cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {activeList.map((key, idx) => {
                return (
                  <div key={key} className="task-barracks-card" style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.10)',
                    borderRadius: '14px', padding: '14px',
                  }}>
                    {/* Card header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                        <span style={{ color: '#9ca3af', fontSize: '13px', fontWeight: 600 }}>{t('tasks.troops')} #{idx + 1}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeBarracks(key)}
                        style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', padding: '2px', display: 'flex' }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>

                    {/* Type selector — show all 4, disable ones used in other cards */}
                    <SectionLabel text={t('tasks.troopType')} />
                    <div className="gap-2 grid grid-cols-2 sm:grid-cols-4 mb-3">
                      {BARRACKS_TYPES.map(b => {
                        const isSelected = b.key === key
                        const isUsedElsewhere = !isSelected && activeList.includes(b.key as BarracksKey)
                        return (
                          <button
                            key={b.key}
                            type="button"
                            disabled={isUsedElsewhere}
                            className={clsx('task-troop-btn', isSelected ? 'selected' : 'unselected', isUsedElsewhere && 'used-elsewhere')}
                            onClick={() => {
                              if (isUsedElsewhere) return
                              const newLevels = { ...tr.levels, [key]: 0, [b.key]: tr.levels[key] || 1 }
                              update('train', { levels: newLevels } as Partial<typeof tr>)
                            }}
                            style={{
                              width: '100%',
                              padding: '8px 4px', borderRadius: '8px',
                              border: isSelected ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                              background: isSelected ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                              color: isSelected ? '#6ee7b7' : isUsedElsewhere ? '#374151' : '#9ca3af',
                              fontSize: '12px', fontWeight: isSelected ? 600 : 500,
                              cursor: isUsedElsewhere ? 'not-allowed' : 'pointer',
                              fontFamily: 'inherit', transition: 'all 0.15s',
                              opacity: isUsedElsewhere ? 0.38 : 1,
                              textAlign: 'center',
                            }}
                          >
                            {t(b.labelKey)}
                          </button>
                        )
                      })}
                    </div>

                    {/* Level stepper */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <SectionLabel text={t('common.level')} />
                      <Stepper value={tr.levels[key]} min={1} max={12} onChange={v => setLevel(key, v)} />
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Add barracks button */}
            {unusedTypes.length > 0 && (
              <button
                type="button"
                onClick={addBarracks}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                  width: '100%', padding: '8px 12px',
                  borderRadius: '10px', border: '1px dashed rgba(34,197,94,0.3)',
                  background: 'rgba(16,185,129,0.05)',
                  color: '#6ee7b7', fontSize: '12px', fontWeight: 500,
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'all 0.15s',
                }}
              >
                <Plus size={13} />
                {t('tasks.addTroopType')}
              </button>
            )}
          </>
        )}
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 3. الهجوم (Combat / march_manager)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'combat') {
    const mm = cfg.march_manager
    // Only one of elf/invaders/rebels can be active
    const combatChoice: 'elf' | 'invaders' | 'rebels' | null =
      mm.elf.enabled ? 'elf' :
      mm.invaders.enabled ? 'invaders' :
      mm.rebels.enabled ? 'rebels' : null

    const setCombatChoice = (choice: 'elf' | 'invaders' | 'rebels' | null) => {
      update('march_manager', {
        elf:      { ...mm.elf,      enabled: choice === 'elf'      },
        invaders: { ...mm.invaders, enabled: choice === 'invaders' },
        rebels:   { ...mm.rebels,   enabled: choice === 'rebels'   },
      })
    }

    // Shared formation (used for the active combat choice)
    const sharedFormation = mm.elf.enabled ? mm.elf.formation_id :
                            mm.invaders.enabled ? mm.invaders.formation_id :
                            mm.ruins.formation_id

    const setSharedFormation = (v: number) => {
      update('march_manager', {
        elf:      { ...mm.elf,      formation_id: v },
        invaders: { ...mm.invaders, formation_id: v },
        rebels:   { ...mm.rebels,   formation_id: v },
        ruins:    { ...mm.ruins,    formation_id: v },
        stronghold: { ...mm.stronghold, formation_id: v },
      })
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}
        className="task-header-card disabled"
        >
          <span style={{ fontSize: '24px' }}>🗡️</span>
          <div>
            <div className="task-header-title" style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>{t('tasks.attack')}</div>
          </div>
        </div>

        {/* Formation selector */}
        <div>
          <SectionLabel text={t('tasks.selectedMarch')} />
          <div style={{ display: 'flex', gap: '8px' }}>
            {[1, 2, 3, 4].map(f => (
              <button
                key={f}
                type="button"
                className={clsx('task-formation-btn', sharedFormation === f ? 'selected' : 'unselected')}
                onClick={() => setSharedFormation(f)}
                style={{
                  flex: '1 1 0', aspectRatio: '1',
                  maxWidth: '72px', borderRadius: '10px',
                  border: sharedFormation === f ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                  background: sharedFormation === f ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.05)',
                  color: sharedFormation === f ? '#6ee7b7' : '#9ca3af',
                  fontSize: '16px', fontWeight: 700,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'inherit', transition: 'all 0.15s',
                  position: 'relative', overflow: 'hidden',
                }}
              >
                <img
                  src={`/images/combat/slot${f}.png`}
                  alt={`${t('tasks.formation')} ${f}`}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', inset: 0 }}
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
                <span style={{ position: 'relative', zIndex: 1 }}>{f}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Combat type — radio (only one) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {([
            { key: 'elf',      img: '/images/combat/elitifrit.png',   labelKey: 'tasks.eliteEfreet', descKey: 'tasks.usesSelectedMarch' },
            { key: 'invaders', img: '/images/combat/yagmaci.png',     labelKey: 'tasks.invaders',    descKey: 'tasks.usesSelectedMarch' },
            { key: 'rebels',   img: '/images/combat/yagmaci.png',     labelKey: 'tasks.eliteRebels', descKey: 'tasks.usesSelectedMarch' },
          ] as const).map(opt => {
            const isActive = combatChoice === opt.key
            const configData = opt.key === 'elf' ? mm.elf : opt.key === 'invaders' ? mm.invaders : mm.rebels
            return (
              <div
                key={opt.key}
                onClick={() => setCombatChoice(isActive ? null : opt.key)}
                className={clsx('task-sub-card', isActive ? 'enabled' : 'disabled')}
                style={{
                  background: isActive ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)',
                  border: isActive ? '1px solid rgba(34,197,94,0.25)' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '12px', padding: '12px 14px',
                  cursor: 'pointer',
                  userSelect: 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pointerEvents: 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <img src={opt.img} alt="" style={{ width: '28px', height: '28px', objectFit: 'contain' }}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    <div>
                      <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>{t(opt.labelKey)}</div>
                      <div style={{ color: '#6b7280', fontSize: '11px' }}>{t(opt.descKey)}</div>
                    </div>
                  </div>
                  <Toggle value={isActive} onChange={v => setCombatChoice(v ? opt.key : null)} size="sm" />
                </div>
                {/* Level for invaders/rebels */}
                {isActive && opt.key !== 'elf' && (
                  <div
                    onClick={e => e.stopPropagation()}
                    style={{ marginTop: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                  >
                    <span style={{ color: '#9ca3af', fontSize: '12px' }}>{t('tasks.maxLevel')}</span>
                    <Stepper
                      value={Math.min((configData as typeof mm.invaders).level || 1, opt.key === 'rebels' ? 5 : 35)}
                      min={1}
                      max={opt.key === 'rebels' ? 5 : 35}
                      onChange={v => update('march_manager', { enabled: true, [opt.key]: { ...configData, level: v } })}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Ruins */}
        <div
          onClick={() => update('march_manager', { enabled: true, ruins: { ...mm.ruins, enabled: !mm.ruins.enabled } })}
          style={{
            background: mm.ruins.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: mm.ruins.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px', padding: '12px 14px',
            cursor: 'pointer',
            userSelect: 'none',
            transition: 'all 0.15s ease',
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: mm.ruins.enabled ? '12px' : 0,
            pointerEvents: 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <img src="/images/combat/kesif.png" alt="" style={{ width: '28px' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              <div>
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>{t('tasks.ruins')}</div>
                <div style={{ color: '#6b7280', fontSize: '11px' }}>{t('tasks.singleMarchOnly')}</div>
              </div>
            </div>
            <Toggle value={mm.ruins.enabled} onChange={v => update('march_manager', { enabled: true, ruins: { ...mm.ruins, enabled: v } })} size="sm" />
          </div>
          {mm.ruins.enabled && (
            <div onClick={e => e.stopPropagation()} style={{ marginTop: '4px' }}>
              <SectionLabel text={t('tasks.marchDuration')} />
              <div style={{ display: 'flex', gap: '6px' }}>
                {[
                  { s: 900,   labelKey: 'tasks.easy',   subKey: 'tasks.min15' },
                  { s: 3600,  labelKey: 'tasks.normal', subKey: 'tasks.hour1' },
                  { s: 7200,  labelKey: 'tasks.medium', subKey: 'tasks.hours4' },
                  { s: 43200, labelKey: 'tasks.hard',   subKey: 'tasks.hours8' },
                ].map(opt => (
                  <button
                    key={opt.s}
                    type="button"
                    className={clsx('task-duration-btn', mm.ruins.explore_time === opt.s ? 'selected' : 'unselected')}
                    onClick={() => update('march_manager', { enabled: true, ruins: { ...mm.ruins, explore_time: opt.s } })}
                    style={{
                      flex: '1 1 0', padding: '8px 4px', borderRadius: '10px',
                      border: mm.ruins.explore_time === opt.s ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                      background: mm.ruins.explore_time === opt.s ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                      color: mm.ruins.explore_time === opt.s ? '#6ee7b7' : '#9ca3af',
                      fontSize: '11px', fontWeight: mm.ruins.explore_time === opt.s ? 600 : 400,
                      cursor: 'pointer', fontFamily: 'inherit', textAlign: 'center', lineHeight: 1.4,
                      transition: 'all 0.15s',
                    }}
                  >
                    <div>{t(opt.labelKey)}</div>
                    {opt.subKey && <div style={{ fontSize: '10px', opacity: 0.75 }}>{t(opt.subKey)}</div>}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Stronghold */}
        <div
          onClick={() => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, enabled: !mm.stronghold.enabled } })}
          style={{
            background: mm.stronghold.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: mm.stronghold.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px', padding: '12px 14px',
            cursor: 'pointer',
            userSelect: 'none',
            transition: 'all 0.15s ease',
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: mm.stronghold.enabled ? '12px' : 0,
            pointerEvents: 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <img src="/images/prestige/siginak (1).png" alt="" style={{ width: '28px' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              <div>
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>{t('tasks.stronghold')}</div>
              </div>
            </div>
            <Toggle value={mm.stronghold.enabled} onChange={v => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, enabled: v } })} size="sm" />
          </div>
          {mm.stronghold.enabled && (
            <div onClick={e => e.stopPropagation()}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#9ca3af', fontSize: '12px' }}>{t('tasks.maxLevel')}</span>
                <Stepper value={mm.stronghold.level} min={1} max={35}
                  onChange={v => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, level: v } })} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#9ca3af', fontSize: '12px' }}>{t('tasks.simultaneousAttacks')}</span>
                <Stepper
                  value={Math.min(mm.stronghold.count || 1, 5)}
                  min={1}
                  max={5}
                  onChange={v => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, count: v } })}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 4. مكافأة الطاحونة (Watermill)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'watermill') {
    const wm = cfg.watermill
    const rawList: string[] = wm.types === 'all'
      ? ['food', 'wood', 'iron', 'diamond']
      : (wm.types || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
    const selectedTypes = rawList.map(t => t === 'silver' ? 'diamond' : t)

    const toggleResource = (key: string) => {
      const next = selectedTypes.includes(key)
        ? selectedTypes.filter(x => x !== key)
        : [...selectedTypes, key]
      update('watermill', { types: next.join(',') })
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header */}
        <div
          onClick={() => toggle('watermill')(!wm.enabled)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: wm.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: wm.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '14px', padding: '12px 14px',
            cursor: 'pointer', userSelect: 'none',
          }}
          className={clsx('transition-colors task-header-card', wm.enabled ? 'enabled' : 'disabled')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/watermill/uretimbonusust.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div className="task-header-title" style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>{t('tasks.watermillBonus')}</div>
            </div>
          </div>
          <Toggle value={wm.enabled} onChange={toggle('watermill')} />
        </div>

        {wm.enabled && (
          <>
            <div>
              <SectionLabel text={t('tasks.bonusTypes')} />
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {WATERMILL_RESOURCES.map(r => (
                  <ResCard
                    key={r.key}
                    img={r.img}
                    label={t(r.resKey)}
                    selected={selectedTypes.includes(r.key)}
                    onClick={() => toggleResource(r.key)}
                  />
                ))}
              </div>
            </div>

            {/* Allow shop buy toggle */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '12px', padding: '12px 14px',
            }}>
              <img src="/images/watermill/uretimbonusust.png" style={{ width: '28px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              <div style={{ flex: 1 }}>
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>{t('tasks.buyFromAllianceShop')}</div>
                <div style={{ color: '#6b7280', fontSize: '11px' }}>{t('tasks.buyFromAllianceShopDesc')}</div>
              </div>
              <Toggle value={wm.allow_shop_buy} onChange={v => update('watermill', { allow_shop_buy: v })} size="sm" />
            </div>
          </>
        )}
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 5. مساعدة الموارد (Transport)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'transport') {
    const tr = cfg.march_manager.transport

    const toggleResId = (id: number) => {
      const ids = tr.resource_ids.includes(id)
        ? tr.resource_ids.filter(x => x !== id)
        : [...tr.resource_ids, id]
      update('march_manager', { transport: { ...tr, resource_ids: ids } })
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header */}
        <div
          onClick={() => {
            const next = !tr.enabled
            update('march_manager', { transport: { ...tr, enabled: next } })
            if (!next) setCoordsError(false)
          }}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: tr.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: tr.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '14px', padding: '12px 14px',
            cursor: 'pointer', userSelect: 'none',
          }}
          className={clsx('transition-colors task-header-card', tr.enabled ? 'enabled' : 'disabled')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🔗</span>
            <div>
              <div className="task-header-title" style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>{t('tasks.transportResources')}</div>
            </div>
          </div>
          <Toggle
            value={tr.enabled}
            onChange={v => {
              update('march_manager', { transport: { ...tr, enabled: v } })
              if (!v) setCoordsError(false)
            }}
          />
        </div>

        {tr.enabled && (
          <>
            <div>
              <SectionLabel text={t('tasks.resourceTypes')} />
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {TRANSPORT_RESOURCES.map(r => (
                  <ResCard
                    key={r.id}
                    img={r.img}
                    label={t(r.resKey)}
                    selected={tr.resource_ids.includes(r.id)}
                    onClick={() => toggleResId(r.id)}
                  />
                ))}
              </div>
            </div>

            <div>
              <SectionLabel text={t('tasks.location')} />
              <div style={{ display: 'flex', gap: '10px' }}>
                <div style={{ flex: 1 }}>
                  <div className="task-coord-label" style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>X</div>
                  <input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    value={tr.target_x ?? ''}
                    onChange={e => {
                      const val = e.target.value.replace(/[^0-9]/g, '')
                      const newX = val === '' ? null : Number(val)
                      update('march_manager', { transport: { ...tr, target_x: newX } })
                      if (newX && newX > 0 && tr.target_y && tr.target_y > 0) {
                        setCoordsError(false)
                      }
                    }}
                    style={{
                      ...inputStyle,
                      border: coordsError && (!tr.target_x || tr.target_x <= 0)
                        ? '1.5px solid #ef4444'
                        : inputStyle.border,
                      boxShadow: coordsError && (!tr.target_x || tr.target_x <= 0)
                        ? '0 0 10px rgba(239, 68, 68, 0.35)'
                        : undefined,
                    }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <div className="task-coord-label" style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>Y</div>
                  <input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    value={tr.target_y ?? ''}
                    onChange={e => {
                      const val = e.target.value.replace(/[^0-9]/g, '')
                      const newY = val === '' ? null : Number(val)
                      update('march_manager', { transport: { ...tr, target_y: newY } })
                      if (tr.target_x && tr.target_x > 0 && newY && newY > 0) {
                        setCoordsError(false)
                      }
                    }}
                    style={{
                      ...inputStyle,
                      border: coordsError && (!tr.target_y || tr.target_y <= 0)
                        ? '1.5px solid #ef4444'
                        : inputStyle.border,
                      boxShadow: coordsError && (!tr.target_y || tr.target_y <= 0)
                        ? '0 0 10px rgba(239, 68, 68, 0.35)'
                        : undefined,
                    }}
                  />
                </div>
              </div>

              {coordsError && (!tr.target_x || tr.target_x <= 0 || !tr.target_y || tr.target_y <= 0) && (
                <div style={{
                  marginTop: '10px',
                  padding: '9px 12px',
                  borderRadius: '10px',
                  background: 'rgba(239, 68, 68, 0.12)',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  color: '#fca5a5',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                  <span style={{ fontSize: '14px' }}>⚠️</span>
                  <span>{t('tasks.invalidCoordsWarning')}</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 6. مهام الهيبة (Prestige)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'prestige') {
    const pr = cfg.prestige
    const subtaskDefs = [
      { key: 'smuggler',   img: '/images/prestige/kacakci.png',        labelKey: 'tasks.smuggler' },
      { key: 'gather',     img: '/images/prestige/uretimtahil (1).png', labelKey: 'tasks.gatherResources' },
      { key: 'watermill',  img: '/images/development/tamponhasat.png',  labelKey: 'tasks.watermillBonus' },
      { key: 'train',      img: '/images/prestige/asker_egit.png',      labelKey: 'tasks.train' },
      { key: 'invaders',   img: '/images/prestige/yagmaci (1).png',     labelKey: 'tasks.invaders' },
      { key: 'stronghold', img: '/images/prestige/siginak (1).png',     labelKey: 'tasks.stronghold' },
    ] as const

    const activeCount = subtaskDefs.filter(st => pr.subtasks[st.key]).length

    const setAllSubtasks = (val: boolean) => {
      const updated: Record<string, boolean> = { fortress: val }
      for (const st of subtaskDefs) {
        updated[st.key] = val
      }
      update('prestige', { subtasks: { ...pr.subtasks, ...updated } } as Partial<typeof pr>)
    }

    const handleToggleSubtask = (stKey: string, nextVal: boolean) => {
      const updated = { ...pr.subtasks, [stKey]: nextVal }
      // تفعيل وتعطيل حصن الحرب تلقائياً مع تدريب الجنود
      if (stKey === 'train') {
        updated.fortress = nextVal
      }
      update('prestige', { subtasks: updated as typeof pr.subtasks } as Partial<typeof pr>)
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* ─── Master Controller Banner (نظام مهام الهيبة الرئيسي) ─── */}
        <div
          onClick={() => toggle('prestige')(!pr.enabled)}
          style={{
            background: pr.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: pr.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px',
            padding: '12px 14px',
            transition: 'all 0.15s ease',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          className={clsx('transition-colors task-row-card', pr.enabled ? 'enabled' : 'disabled')}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'nowrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: '8px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <img
                  src="/images/daily/goldenchest.png"
                  alt="Prestige"
                  style={{ width: '22px', height: '22px', objectFit: 'contain' }}
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="task-row-label" style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px', whiteSpace: 'nowrap' }}>
                  {t('tasks.prestigeTasks')}
                
              </div>
              </div>
            </div>

            <div style={{ flexShrink: 0 }}>
              <Toggle value={pr.enabled} onChange={toggle('prestige')} size="sm" />
            </div>
          </div>
        </div>

        {/* ─── Subtasks Section (المهام الفرعية) ─── */}
        {pr.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* Sub-header with quick actions */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '0 4px', marginTop: '2px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#d1fae5', fontSize: '13px', fontWeight: 600 }}>{t('tasks.prestigeTasks')}</span>
                <span style={{ color: '#6b7280', fontSize: '11px' }}>{t('tasks.activeSubtasks', { count: activeCount })}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                <button
                  type="button"
                  onClick={() => setAllSubtasks(true)}
                  style={{
                    background: 'rgba(16,185,129,0.10)', border: '1px solid rgba(16,185,129,0.25)',
                    color: '#6ee7b7', padding: '3px 10px', borderRadius: '8px',
                    cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500,
                  }}
                >
                  {t('common.selectAll')}
                </button>
                <button
                  type="button"
                  onClick={() => setAllSubtasks(false)}
                  style={{
                    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                    color: '#9ca3af', padding: '3px 10px', borderRadius: '8px',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  {t('common.cancelAll')}
                </button>
              </div>
            </div>

            {/* List of subtasks */}
            {subtaskDefs.map(st => {
              const isSubEnabled = Boolean(pr.subtasks[st.key])
              const isInvaders = st.key === 'invaders'

              return (
                <div
                  key={st.key}
                  onClick={() => handleToggleSubtask(st.key, !isSubEnabled)}
                  className={clsx('task-subtask-row', isSubEnabled ? 'enabled' : 'disabled')}
                  style={{
                    background: isSubEnabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.025)',
                    border: isSubEnabled ? '1px solid rgba(34,197,94,0.22)' : '1px solid rgba(255,255,255,0.07)',
                    borderRadius: '14px',
                    padding: '12px 14px',
                    cursor: 'pointer',
                    userSelect: 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', pointerEvents: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                      <img
                        src={st.img}
                        alt=""
                        style={{ width: '32px', height: '32px', objectFit: 'contain', flexShrink: 0 }}
                        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                      />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ color: isSubEnabled ? '#f0fdf4' : '#9ca3af', fontWeight: 600, fontSize: '13px' }}>
                          {t(st.labelKey)}
                        </div>
                      </div>
                    </div>

                    <Toggle
                      value={isSubEnabled}
                      onChange={v => handleToggleSubtask(st.key, v)}
                      size="sm"
                    />
                  </div>

                  {/* إذا كان الغزاة مفعّلاً: يظهر تحديد المستوى مباشرة داخل بطاقة الغزاة */}
                  {isInvaders && isSubEnabled && (
                    <div
                      onClick={e => e.stopPropagation()}
                      style={{
                        marginTop: '12px',
                        paddingTop: '10px',
                        borderTop: '1px solid rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '10px',
                        flexWrap: 'wrap',
                        cursor: 'default',
                      }}
                    >
                      <div>
                        <div style={{ color: '#a7f3d0', fontSize: '12px', fontWeight: 600 }}>{t('tasks.invadersMaxLv')}</div>
                      </div>
                      <Stepper
                        value={pr.invaders_max_lv}
                        min={1}
                        max={35}
                        onChange={v => update('prestige', { invaders_max_lv: v } as Partial<typeof pr>)}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ─────────────────────────────────────────────────────────────────────────
  // 7. المهام اليومية (Daily)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'daily') {
    const sh = cfg.shield
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* قافلة الغنيمة */}
        <TaskRow
          img="/images/daily/ganimetkaravani.png" label={t('tasks.lootCaravan')}
          enabled={cfg.caravan.enabled} onToggle={toggle('caravan')}
        />

        {/* الشارات الملكية (Hero Draw) */}
        <TaskRow
          img="/images/daily/kahramanlarsalonu.png" label={t('tasks.heroDraw')}
          enabled={cfg.hero_draw.enabled} onToggle={toggle('hero_draw')}
        />

        {/* مهام التحالف */}
        <TaskRow
          img="/images/daily/lonca.png" label={t('tasks.allianceTasks')}
          enabled={cfg.alliance.enabled} onToggle={toggle('alliance')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* التبرع للتحالف (auto_help) */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 12px', borderRadius: '10px',
              background: (cfg.alliance.auto_help ?? true) ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
              border: (cfg.alliance.auto_help ?? true) ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.07)',
            }}>
              <div>
                <div style={{ color: '#f0fdf4', fontSize: '13px', fontWeight: 600 }}>{t('tasks.allianceDonation')}</div>
              </div>
              <Toggle
                value={cfg.alliance.auto_help ?? true}
                onChange={v => update('alliance', { auto_help: v })}
                size="sm"
              />
            </div>

            {/* خيار التبرع بالذهب (gold_donations) */}
            {(cfg.alliance.auto_help ?? true) && (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '11px 13px', borderRadius: '10px',
                background: (cfg.alliance.gold_donations ?? 0) > 0 ? 'rgba(234,179,8,0.08)' : 'rgba(255,255,255,0.03)',
                border: (cfg.alliance.gold_donations ?? 0) > 0 ? '1px solid rgba(234,179,8,0.25)' : '1px solid rgba(255,255,255,0.07)',
                gap: '12px', flexWrap: 'wrap',
              }}>
                <div>
                  <div style={{ color: '#fef08a', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{t('tasks.goldDonation')}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Stepper
                    value={cfg.alliance.gold_donations ?? 0}
                    min={0}
                    max={10}
                    onChange={v => update('alliance', { gold_donations: v })}
                    
                  />
                </div>
              </div>
            )}
          </div>
        </TaskRow>

        {/* دورية الحيوانات */}
        <TaskRow
          emoji="🦅" label={t('tasks.petPatrol')}
          enabled={cfg.pet_patrol.enabled} onToggle={toggle('pet_patrol')}
        >
          <div>
            <SectionLabel text={t('tasks.pet')} />
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {PETS.map(p => (
                <button key={p.name} type="button"
                  className={clsx('task-pet-btn', cfg.pet_patrol.pet === p.name ? 'selected' : 'unselected')}
                  onClick={() => update('pet_patrol', { pet: p.name })}
                  style={{
                    padding: '4px 8px', borderRadius: '6px', fontFamily: 'inherit',
                    border: cfg.pet_patrol.pet === p.name ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                    background: cfg.pet_patrol.pet === p.name ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                    color: cfg.pet_patrol.pet === p.name ? '#6ee7b7' : '#9ca3af',
                    fontSize: '11px', cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >{p.labelKey ? t(p.labelKey) : p.name}</button>
              ))}
            </div>
          </div>
        </TaskRow>

        {/* القدرة على التحمل (Stamina) */}
        {(() => {
          const currentCount = (cfg.stamina.gold_buys && cfg.stamina.gold_buys >= 1) ? cfg.stamina.gold_buys : 1

          return (
            <TaskRow
              img="/images/daily/dayaniklilik_2.png"
              label={t('tasks.staminaManagement')}
              enabled={cfg.stamina.enabled}
              onToggle={toggle('stamina')}
            >
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                paddingTop: '2px',
              }}>
                <img
                  src="/images/daily/dayaniklilik_1.png"
                  alt=""
                  style={{ width: '34px', height: '34px', objectFit: 'contain', flexShrink: 0, filter: 'drop-shadow(0 0 6px rgba(34,197,94,0.4))' }}
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
                <select
                  value={currentCount}
                  className="task-stamina-select"
                  onChange={e => update('stamina', { gold_buys: Number(e.target.value) })}
                  style={{
                    flex: 1,
                    background: '#0d130e',
                    border: '1.5px solid #f59e0b',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    fontSize: '13.5px',
                    fontWeight: 600,
                    color: '#ffffff',
                    outline: 'none',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    boxShadow: '0 0 10px rgba(245, 158, 11, 0.15)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {STAMINA_GOLD_OPTIONS.map(opt => (
                    <option
                      key={opt.count}
                      value={opt.count}
                      style={{
                        background: '#121a14',
                        color: '#ffffff',
                        fontSize: '13.5px',
                        padding: '10px',
                      }}
                    >
                      {t('tasks.staminaOption', { count: opt.count, gold: opt.gold })}
                    </option>
                  ))}
                </select>
              </div>
            </TaskRow>
          )
        })()}


        {/* بنك الادخار */}
        <TaskRow
          img="/images/daily/goldenchest.png" label={t('tasks.savingsBank')}
          enabled={cfg.savings_bank.enabled} onToggle={toggle('savings_bank')}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { d: 7,  labelKey: 'tasks.days7',  img: 'silverchest.png' },
              { d: 15, labelKey: 'tasks.days15', img: 'silverchest.png' },
              { d: 30, labelKey: 'tasks.days30', img: 'silverchest.png' },
            ].map(opt => {
              const currentDays = (cfg.savings_bank.days === 1 || !cfg.savings_bank.days) ? 7 : cfg.savings_bank.days
              const isSelected = currentDays === opt.d
              return (
                <button
                  key={opt.d}
                  type="button"
                  className={clsx('task-savings-btn', isSelected ? 'selected' : 'unselected')}
                  onClick={() => update('savings_bank', { days: opt.d })}
                  style={{
                    flex: 1,
                    padding: '7px 4px',
                    borderRadius: '9px',
                    border: isSelected ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                    background: isSelected ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                    color: isSelected ? '#6ee7b7' : '#9ca3af',
                    fontSize: '11px',
                    fontWeight: isSelected ? 600 : 400,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '4px',
                    transition: 'all 0.15s',
                  }}
                >
                  <img
                    src={`/images/daily/${opt.img}`}
                    alt=""
                    style={{
                      width: '26px',
                      height: '26px',
                      objectFit: 'contain',
                      filter: isSelected ? 'drop-shadow(0 0 6px rgba(34,197,94,0.4))' : 'grayscale(15%) opacity(0.85)',
                      transition: 'all 0.15s',
                    }}
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                  <span>{t(opt.labelKey)}</span>
                </button>
              )
            })}
          </div>
        </TaskRow>

        {/* دراسة الاستراتيجيات (Study Strategies / Tactics Hall) */}
        {(() => {
          return (
            <TaskRow
              img="/images/daily/egitim_stratejisi.png"
              label={t('tasks.studyStrategies')}
              enabled={cfg.tactics_hall.enabled}
              onToggle={toggle('tactics_hall')}
            >
              <div style={{ paddingTop: '4px' }}>
                {/* ── تصنيفات الاستراتيجيات: Battle | Development | Help ── */}
                <div className="gap-1.5 grid grid-cols-3 bg-gray-100 dark:bg-white/5 mb-3.5 p-1 border border-gray-200 dark:border-white/10 rounded-xl">
                  {STRATEGY_TABS.map(tab => {
                    const isActive = tacticsCategory === tab.id
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        className={clsx(
                          'flex justify-center items-center gap-1.5 px-2 py-2 rounded-lg text-center transition-all cursor-pointer task-strategy-pill',
                          isActive ? 'active' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                        )}
                        onClick={() => setTacticsCategory(tab.id)}
                      >
                        <span className="text-sm">{tab.icon}</span>
                        <span className="font-bold text-xs">{t(`tasks.${tab.id}`)}</span>
                      </button>
                    )
                  })}
                </div>

                {/* ── شبكة الأبحاث: بطاقات بسيطة وأنيقة مع تمييز واضح جداً للبحث المختار ── */}
                <div className="gap-2 sm:gap-2.5 grid grid-cols-2">
                  {STRATEGY_ITEMS.filter(item => item.category === tacticsCategory).map(item => {
                    const isSelected = isStrategySelected(cfg.tactics_hall.tactic, item)
                    const itemName = i18n.language === 'ar' ? item.name_ar : item.name_en
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={clsx(
                          'relative flex flex-col justify-center items-center p-3 rounded-xl text-center transition-all cursor-pointer task-strategy-card',
                          isSelected ? 'selected' : 'unselected'
                        )}
                        onClick={() => update('tactics_hall', { tactic: item.name_en })}
                        style={{
                          minHeight: '78px',
                        }}
                      >
                        <img
                          src={`/images/strategies/${item.img}`}
                          alt={item.name_en}
                          className={clsx(
                            'mb-1.5 w-8 sm:w-9 h-8 sm:h-9 object-contain transition-transform',
                            isSelected ? 'scale-105' : 'opacity-85'
                          )}
                          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                        />
                        <div className="px-1 w-full">
                          <div className={clsx(
                            'text-xs text-center truncate leading-tight transition-colors',
                            isSelected
                              ? 'font-bold text-emerald-800 dark:text-emerald-300'
                              : 'font-medium text-gray-700 dark:text-gray-300'
                          )}>
                            {itemName}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            </TaskRow>
          )
        })()}

        {/* نافورة الأمنيات الملكية وبئر الحظ (Trevi Fountain) */}
        {(() => {
          const ft = cfg.fountain || {
            enabled: false,
            resources: ['food', 'wood', 'iron', 'diamond'],
            allow_gold: false,
            gold_times: 0,
          }
          const selectedRes: string[] = Array.isArray(ft.resources) ? ft.resources : []
          const activeResCount = FOUNTAIN_RESOURCES.filter(r => selectedRes.includes(r.key)).length

          const toggleRes = (key: string) => {
            const next = selectedRes.includes(key)
              ? selectedRes.filter(k => k !== key)
              : [...selectedRes, key]
            update('fountain', { resources: next })
          }

          const selectAll = () => {
            update('fountain', { resources: FOUNTAIN_RESOURCES.map(r => r.key) })
          }

          const deselectAll = () => {
            update('fountain', { resources: [] })
          }

          return (
            <TaskRow
              img="/images/fountain/fountain.png"
              label={t('tasks.fountainOfWishes')}
              enabled={ft.enabled}
              onToggle={toggle('fountain')}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', paddingTop: '4px' }}>
                {/* ── قسم اختيار الموارد الخمسة للتمني ── */}
                <div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '8px',
                    flexWrap: 'wrap',
                    gap: '8px',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ color: '#d1fae5', fontSize: '13px', fontWeight: 600 }}>{t('tasks.selectedResources')}</span>
                      <span style={{
                        padding: '1px 8px',
                        borderRadius: '9999px',
                        background: activeResCount > 0 ? 'rgba(34,197,94,0.18)' : 'rgba(239,68,68,0.15)',
                        border: activeResCount > 0 ? '1px solid rgba(34,197,94,0.35)' : '1px solid rgba(239,68,68,0.30)',
                        color: activeResCount > 0 ? '#86efac' : '#fca5a5',
                        fontSize: '11px',
                        fontWeight: 600,
                      }}>
                        {t('tasks.countOfTotalResources', { active: activeResCount, total: FOUNTAIN_RESOURCES.length })}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={selectAll}
                        style={{
                          background: 'rgba(16,185,129,0.10)',
                          border: '1px solid rgba(16,185,129,0.25)',
                          color: '#6ee7b7',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          cursor: 'pointer',
                          fontFamily: 'inherit',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {t('common.selectAll')}
                      </button>
                      <button
                        type="button"
                        onClick={deselectAll}
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.10)',
                          color: '#9ca3af',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          cursor: 'pointer',
                          fontFamily: 'inherit',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {t('common.cancelAll')}
                      </button>
                    </div>
                  </div>

                  {/* شبكة بطاقات الموارد الخمسة */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                    {FOUNTAIN_RESOURCES.map(r => {
                      const isSelected = selectedRes.includes(r.key)
                      return (
                        <button
                          key={r.key}
                          type="button"
                          className={clsx('task-fountain-card', isSelected ? 'selected' : 'unselected')}
                          onClick={() => toggleRes(r.key)}
                          style={{
                            padding: '12px 6px',
                            borderRadius: '12px',
                            border: isSelected ? '1.5px solid #f59e0b' : '1px solid rgba(255,255,255,0.08)',
                            background: isSelected ? 'rgba(245,158,11,0.12)' : 'rgba(255,255,255,0.03)',
                            boxShadow: isSelected ? '0 0 12px rgba(245,158,11,0.2)' : 'none',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                            cursor: 'pointer',
                            fontFamily: 'inherit',
                            transition: 'all 0.15s ease',
                            position: 'relative',
                          }}
                          onMouseEnter={e => {
                            if (!isSelected) {
                              e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
                              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.18)'
                            }
                          }}
                          onMouseLeave={e => {
                            if (!isSelected) {
                              e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
                              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
                            }
                          }}
                        >
                          <div style={{
                            width: '38px',
                            height: '38px',
                            borderRadius: '8px',
                            background: isSelected ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.30)',
                            border: isSelected ? '1px solid rgba(245,158,11,0.35)' : '1px solid rgba(255,255,255,0.08)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'all 0.15s ease',
                          }}>
                            <img
                              src={r.img}
                              alt={t(r.resKey)}
                              style={{
                                width: '28px',
                                height: '28px',
                                objectFit: 'contain',
                                filter: isSelected ? 'drop-shadow(0 0 6px rgba(245,158,11,0.5))' : 'grayscale(25%) opacity(0.8)',
                                transition: 'filter 0.15s ease',
                              }}
                              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                            />
                          </div>
                          <span style={{
                            fontSize: '12px',
                            color: isSelected ? '#fbbf24' : '#9ca3af',
                            fontWeight: isSelected ? 600 : 500,
                          }}>
                            {t(r.resKey)}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* ── قسم الشراء بالذهب ── */}
                {(() => {
                  const currentGoldTimes = ft.allow_gold === false ? 0 : Math.max(0, Number(ft.gold_times) || 0)
                  const isGoldAllowed = currentGoldTimes > 0

                  const setGoldCount = (val: number) => {
                    const count = Math.max(0, val)
                    update('fountain', {
                      gold_times: count,
                      allow_gold: count > 0,
                    })
                  }

                  return (
                    <div style={{
                      background: isGoldAllowed ? 'rgba(234,179,8,0.08)' : 'rgba(255,255,255,0.03)',
                      border: isGoldAllowed ? '1px solid rgba(234,179,8,0.28)' : '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '12px',
                      padding: '12px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                      flexWrap: 'wrap',
                      transition: 'all 0.2s ease',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <img
                          src="/images/fountain/gold.png"
                          alt="Gold"
                          style={{
                            width: '28px',
                            height: '28px',
                            objectFit: 'contain',
                            filter: isGoldAllowed ? 'drop-shadow(0 0 6px rgba(245,158,11,0.5))' : 'grayscale(40%) opacity(0.7)',
                          }}
                          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                        />
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ color: isGoldAllowed ? '#fbbf24' : '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>
                              {t('tasks.allowGoldPurchase')}
                            </span>
                            <span style={{
                              padding: '1px 8px',
                              borderRadius: '9999px',
                              background: isGoldAllowed ? 'rgba(234,179,8,0.18)' : 'rgba(255,255,255,0.06)',
                              border: isGoldAllowed ? '1px solid rgba(234,179,8,0.40)' : '1px solid rgba(255,255,255,0.10)',
                              color: isGoldAllowed ? '#fef08a' : '#9ca3af',
                              fontSize: '11px',
                              fontWeight: 600,
                            }}>
                              {isGoldAllowed ? t('tasks.goldPerResource', { count: currentGoldTimes }) : t('tasks.noGold')}
                            </span>
                          </div>

                        </div>
                      </div>

                      {/* محدد الزيادة والنقصان (+ / -) */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Stepper
                          value={currentGoldTimes}
                          min={0}
                          max={50}
                          onChange={setGoldCount}
                        />
                      </div>
                    </div>
                  )
                })()}
              </div>
            </TaskRow>
          )
        })()}

        {/* ورشة المواد (Material Workshop) */}
        <TaskRow
          img="/images/daily/malzeme_atolyesi.png"
          label={t('tasks.materialWorkshop')}
          enabled={cfg.material_workshop.enabled}
          onToggle={toggle('material_workshop')}
        >
          <div style={{ display: 'flex', gap: '10px' }}>
            {WORKSHOP_MATERIALS.map(m => {
              const currentMats = cfg.material_workshop.materials || []
              const isAll = currentMats.includes('all') || currentMats.includes('الكل')
              const isSelected = isAll || currentMats.includes(m.key) || currentMats.includes(m.label)

              const handleToggle = () => {
                let nextMats: string[]
                if (isAll) {
                  nextMats = WORKSHOP_MATERIALS.filter(x => x.key !== m.key).map(x => x.key)
                } else if (isSelected) {
                  nextMats = currentMats.filter(x => x !== m.key && x !== m.label)
                } else {
                  nextMats = [...currentMats, m.key]
                }
                update('material_workshop', { materials: nextMats })
              }

              return (
                <button
                  key={m.key}
                  type="button"
                  className={clsx('task-workshop-card', isSelected ? 'selected' : 'unselected')}
                  onClick={handleToggle}
                  style={{
                    flex: 1,
                    padding: '16px 10px',
                    borderRadius: '12px',
                    border: isSelected ? '1.5px solid #f59e0b' : '1px solid rgba(255,255,255,0.08)',
                    background: isSelected ? 'rgba(245,158,11,0.10)' : 'rgba(255,255,255,0.03)',
                    boxShadow: isSelected ? '0 0 14px rgba(245,158,11,0.2)' : 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '10px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    transition: 'all 0.15s ease',
                    minHeight: '88px',
                  }}
                  onMouseEnter={e => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
                      e.currentTarget.style.borderColor = 'rgba(255,255,255,0.18)'
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
                      e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
                    }
                  }}
                >
                  <div style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '8px',
                    background: isSelected ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.35)',
                    border: isSelected ? '1px solid rgba(245,158,11,0.35)' : '1px solid rgba(255,255,255,0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.15s ease',
                  }}>
                    <img
                      src={`/images/workshop/${m.img}`}
                      alt={t(m.labelKey)}
                      style={{
                        width: '30px',
                        height: '30px',
                        objectFit: 'contain',
                        filter: isSelected ? 'drop-shadow(0 0 6px rgba(245,158,11,0.4))' : 'none',
                        transition: 'filter 0.15s ease',
                      }}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                  </div>
                  <span style={{
                    fontSize: '13px',
                    color: isSelected ? '#fbbf24' : '#9ca3af',
                    fontWeight: isSelected ? 600 : 500,
                  }}>
                    {t(m.labelKey)}
                  </span>
                </button>
              )
            })}
          </div>
        </TaskRow>

        {/* الدرع التلقائي (Peace Shield) */}
        <TaskRow
          img="/images/daily/kalkan.png"
          label={t('tasks.peaceShield')}
          enabled={sh.enabled}
          onToggle={toggle('shield')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '2px' }}>
            {/* مدة الدرع - القائمة المنسدلة */}
            <div>
              <select
                value={sh.duration || '8h'}
                className="task-shield-select"
                onChange={e => update('shield', { duration: e.target.value as typeof sh.duration })}
                style={{
                  width: '100%',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: '10px',
                  padding: '9px 14px',
                  fontSize: '13px',
                  color: '#f0fdf4',
                  outline: 'none',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                <option value="8h" style={{ background: '#111a11', color: '#f0fdf4' }}>
                  {t('tasks.hours8')}
                </option>
                <option value="24h" style={{ background: '#111a11', color: '#f0fdf4' }}>
                  {t('tasks.hours24')}
                </option>
                <option value="3d" style={{ background: '#111a11', color: '#f0fdf4' }}>
                  {t('tasks.days3')}
                </option>
              </select>
            </div>

            {/* خيار السماح بالشراء بالذهب (allow_gold) */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              background: sh.allow_gold ? 'rgba(245,158,11,0.08)' : 'rgba(255,255,255,0.03)',
              border: sh.allow_gold ? '1px solid rgba(245,158,11,0.25)' : '1px solid rgba(255,255,255,0.06)',
              borderRadius: '10px',
              transition: 'all 0.15s ease',
            }}>
              <div>
                <div style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: sh.allow_gold ? '#fbbf24' : '#e2e8f0',
                }}>
                  {t('tasks.buyWithGold')}
                </div>
              </div>
              <Toggle
                value={Boolean(sh.allow_gold)}
                onChange={v => update('shield', { allow_gold: v })}
                size="sm"
              />
            </div>
          </div>
        </TaskRow>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 8. التطوير والمكافآت (Building)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'building') {
    const bld = cfg.building
    const sk = cfg.skills

    const toggleSkill = (skill: string) => {
      const current = sk.target_skills
      const next = current.includes(skill) ? current.filter(x => x !== skill) : [...current, skill]
      update('skills', { target_skills: next })
    }

    const skillDefs = [
      { key: 'harvest',   img: '/images/development/hasatet.png',     labelKey: 'tasks.harvestBonus' },
      { key: 'gather',    img: '/images/development/hizlitopla.png',  labelKey: 'tasks.rapidGatherBonus' },
      { key: 'warehouse', img: '/images/development/tamponhasat.png', labelKey: 'tasks.warehouseHarvestBonus' },
    ]

    const targetBuildings = bld.target_buildings ?? {
      farm: true,
      sawmill: true,
      iron_mine: true,
      quartz_mine: true,
      hospital: true,
      military_tent: true,
    }

    const toggleTargetBuilding = (key: string) => {
      const current = targetBuildings[key as keyof typeof targetBuildings] ?? true
      const updated = {
        ...targetBuildings,
        [key]: !current,
      }
      update('building', { target_buildings: updated })
    }

    const selectAllBuildings = () => {
      update('building', {
        target_buildings: {
          farm: true,
          sawmill: true,
          iron_mine: true,
          quartz_mine: true,
          hospital: true,
          military_tent: true,
        },
      })
    }

    const deselectAllBuildings = () => {
      update('building', {
        target_buildings: {
          farm: false,
          sawmill: false,
          iron_mine: false,
          quartz_mine: false,
          hospital: false,
          military_tent: false,
        },
      })
    }

    const supportBuildingOptions = [
      { key: 'farm',          nameKey: 'tasks.bldFarm',         bid: '201', img: '/images/development/camps/tahilmaden.png' },
      { key: 'sawmill',       nameKey: 'tasks.bldSawmill',      bid: '202', img: '/images/development/camps/odunmaden.png' },
      { key: 'iron_mine',     nameKey: 'tasks.bldIronMine',     bid: '203', img: '/images/development/camps/demirmaden.png' },
      { key: 'quartz_mine',   nameKey: 'tasks.bldQuartzMine',   bid: '204', img: '/images/development/camps/kuvarsmaden.png' },
      { key: 'hospital',      nameKey: 'tasks.bldHospital',     bid: '206', img: '/images/development/camps/aramayi_tamamla.png' },
      { key: 'military_tent', nameKey: 'tasks.bldMilitaryTent', bid: '205', img: '/images/development/camps/egitimcadiri.png' },
    ]

    const activeBuildingsCount = Object.values(targetBuildings).filter(Boolean).length

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* تنفيذ البناء */}
        <TaskRow
          img="/images/development/insaat.png"
          label={t('tasks.executeBuilding')}
          enabled={bld.enabled}
          onToggle={toggle('building')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* القلعة فقط */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 12px',
              background: bld.upgrade_castle ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.02)',
              border: bld.upgrade_castle ? '1px solid rgba(34,197,94,0.2)' : '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px',
              transition: 'all 0.15s ease',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: '1px solid rgba(255,255,255,0.08)', flexShrink: 0,
                }}>
                  <img src="/images/development/insaat.png" alt="" style={{ width: '22px', height: '22px', objectFit: 'contain' }} />
                </div>
                <div>
                  <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>{t('tasks.castleOnly')}</div>
                </div>
              </div>
              <Toggle
                value={Boolean(bld.upgrade_castle)}
                onChange={v => update('building', { upgrade_castle: v })}
                size="sm"
              />
            </div>

            {/* استخدام التسريع */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 12px',
              background: bld.speedup_castle ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.02)',
              border: bld.speedup_castle ? '1px solid rgba(34,197,94,0.2)' : '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px',
              transition: 'all 0.15s ease',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: '1px solid rgba(255,255,255,0.08)', flexShrink: 0,
                }}>
                  <img src="/images/daily/yildirim_hizi.png" alt="" style={{ width: '22px', height: '22px', objectFit: 'contain' }} />
                </div>
                <div>
                  <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>{t('tasks.useSpeedup')}</div>
                  <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '1px' }}>{t('tasks.speedupCastleDesc')}</div>
                </div>
              </div>
              <Toggle
                value={Boolean(bld.speedup_castle)}
                onChange={v => update('building', { speedup_castle: v })}
                size="sm"
              />
            </div>

            {/* ترقية المعسكرات والمباني الداعمة */}
            <div style={{
              display: 'flex', flexDirection: 'column', gap: '8px',
              padding: '10px 12px',
              background: bld.upgrade_support_buildings ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.02)',
              border: bld.upgrade_support_buildings ? '1px solid rgba(34,197,94,0.2)' : '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px',
              transition: 'all 0.15s ease',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '8px',
                    background: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '1px solid rgba(255,255,255,0.08)', flexShrink: 0,
                  }}>
                    <img src="/images/development/camps/egitimcadiri.png" alt="" style={{ width: '24px', height: '20px', objectFit: 'contain' }} />
                  </div>
                  <div>
                    <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>{t('tasks.upgradeSupportBuildings')}</div>
                  </div>
                </div>
                <Toggle
                  value={Boolean(bld.upgrade_support_buildings)}
                  onChange={v => update('building', { upgrade_support_buildings: v })}
                  size="sm"
                />
              </div>

              {/* شبكة المباني الـ 6 التفاعلية */}
              {bld.upgrade_support_buildings && (
                <div className="task-support-bld-box" style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  marginTop: '6px',
                  padding: '10px',
                  background: 'rgba(0,0,0,0.3)',
                  borderRadius: '10px',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  {/* شريط التحكم السريع ومعلومات التفعيل */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '8px',
                    paddingBottom: '6px',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '10px',
                        background: activeBuildingsCount > 0 ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                        border: activeBuildingsCount > 0 ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(239,68,68,0.3)',
                        color: activeBuildingsCount > 0 ? '#4ade80' : '#f87171',
                        fontSize: '11px',
                        fontWeight: 600,
                      }}>
                        {t('tasks.activeBuildingsRatio', { active: activeBuildingsCount, total: 6 })}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={selectAllBuildings}
                        style={{
                          background: 'rgba(34,197,94,0.12)',
                          border: '1px solid rgba(34,197,94,0.25)',
                          borderRadius: '6px',
                          padding: '3px 9px',
                          color: '#86efac',
                          fontSize: '11px',
                          fontWeight: 500,
                          cursor: 'pointer',
                          fontFamily: 'inherit',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {t('common.selectAll')}
                      </button>
                      <button
                        type="button"
                        onClick={deselectAllBuildings}
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.08)',
                          borderRadius: '6px',
                          padding: '3px 9px',
                          color: '#9ca3af',
                          fontSize: '11px',
                          fontWeight: 500,
                          cursor: 'pointer',
                          fontFamily: 'inherit',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {t('common.cancelAll')}
                      </button>
                    </div>
                  </div>

                  {/* الشبكة التفاعلية للمباني الـ 6 */}
                  <div className="gap-2.5 sm:gap-3 grid grid-cols-2 sm:grid-cols-3">
                    {supportBuildingOptions.map(b => {
                      const isSelected = Boolean(targetBuildings[b.key as keyof typeof targetBuildings] ?? true)
                      return (
                        <button
                          key={b.key}
                          type="button"
                          className={clsx('relative flex flex-col justify-between items-center p-2.5 sm:p-3 rounded-xl transition-all duration-150 cursor-pointer task-support-bld-card', isSelected ? 'selected' : 'unselected')}
                          onClick={() => toggleTargetBuilding(b.key)}
                          style={{
                            background: isSelected
                              ? 'linear-gradient(135deg, rgba(16,185,129,0.14) 0%, rgba(5,150,105,0.08) 100%)'
                              : 'rgba(255,255,255,0.02)',
                            border: isSelected
                              ? '1.5px solid rgba(34,197,94,0.45)'
                              : '1px solid rgba(255,255,255,0.06)',
                            borderRadius: '10px',
                            boxShadow: isSelected ? '0 0 12px rgba(34,197,94,0.12)' : 'none',
                            opacity: isSelected ? 1 : 0.45,
                            fontFamily: 'inherit',
                            minHeight: '90px',
                          }}
                        >

                          <div style={{
                            width: '56px',
                            height: '40px',
                            background: isSelected ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.04)',
                            borderRadius: '8px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            border: isSelected ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(255,255,255,0.06)',
                            filter: isSelected ? 'drop-shadow(0 0 6px rgba(34,197,94,0.35))' : 'grayscale(25%)',
                            transition: 'all 0.15s',
                          }}>
                            <img src={b.img} alt={t(b.nameKey)} style={{ width: '46px', height: '34px', objectFit: 'contain' }} />
                          </div>

                          <span
                            className="task-support-bld-name"
                            style={{
                              color: isSelected ? '#f0fdf4' : '#9ca3af',
                              fontSize: '12px',
                              fontWeight: isSelected ? 600 : 500,
                              textAlign: 'center',
                              lineHeight: 1.25,
                              marginTop: '6px',
                            }}
                          >
                            {t(b.nameKey)}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </TaskRow>

        {/* إجراء الأبحاث */}
        <TaskRow
          img="/images/development/arastir.png" label={t('tasks.conductResearch')}
          enabled={cfg.research.enabled} onToggle={toggle('research')}
        />

        {/* Skills (مكافآت) */}
        {skillDefs.map(s => (
          <TaskRow
            key={s.key}
            img={s.img}
            label={t(s.labelKey)}
            enabled={sk.enabled && sk.target_skills.includes(s.key)}
            onToggle={v => {
              if (!sk.enabled) update('skills', { enabled: true })
              toggleSkill(s.key)
            }}
          />
        ))}

        {/* الريح الثانوية — coming soon */}
        <TaskRow
          img="/images/development/ikincil_ruzgar.png"
          label={t('tasks.secondaryWind')}
          enabled={false}
          onToggle={() => {}}
          comingSoon
        />

        {/* حفر سريع — coming soon */}
        <TaskRow
          img="/images/development/hizlikazi.png"
          label={t('tasks.fastDig')}
          enabled={false}
          onToggle={() => {}}
          comingSoon
        />
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 9. الفعاليات (Events)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'events') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* طروادة — coming soon */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '12px', padding: '12px 14px', opacity: 0.5,
        }}>
          <span style={{ fontSize: '20px' }}>🏛️</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>{t('tasks.troyEvent')}</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>{t('tasks.troyDesc')}</div>
          </div>
          <Toggle value={false} onChange={() => {}} disabled size="sm" />
        </div>

        {/* الزنزانة الأساسية (port_delegate) */}
        {(() => {
          const dungeonShopProducts = [
            { id: '1', nameKey: 'tasks.dungeonMorale',        num: '#1', price: '', img: '/images/events/basic_dungeon/1.png' },
            { id: '2', nameKey: 'tasks.dungeonCaesarSpirit',  num: '#2', price: '', img: '/images/events/basic_dungeon/2.png' },
            { id: '3', nameKey: 'tasks.dungeonRecruitCard',   num: '#3', price: '', img: '/images/events/basic_dungeon/3.png' },
            { id: '4', nameKey: 'tasks.dungeonResourceChest', num: '#4', price: '', img: '/images/events/basic_dungeon/4.png' },
            { id: '5', nameKey: 'tasks.dungeonExpBook',       num: '#5', price: '', img: '/images/events/basic_dungeon/5.png' },
            { id: '6', nameKey: 'tasks.dungeonTechStone',     num: '#6', price: '', img: '/images/events/basic_dungeon/6.png' },
            { id: '7', nameKey: 'tasks.dungeonEnhanceStone',  num: '#7', price: '', img: '/images/events/basic_dungeon/7.png' },
          ]

          // استخراج معرفات المنتجات المحددة حالياً (دعم 1، عدة خيارات كـ 2,4,6 أو الكل)
          const parseSelected = (raw: unknown): string[] => {
            if (!raw) return ['7']
            if (Array.isArray(raw)) {
              if (raw.includes('all') || raw.includes('الكل') || raw.length === 7) return ['1', '2', '3', '4', '5', '6', '7']
              if (raw.includes('none')) return []
              return raw.map(String)
            }
            const s = String(raw).trim().toLowerCase()
            if (s === 'all' || s === 'الكل' || s === 'all_items') return ['1', '2', '3', '4', '5', '6', '7']
            if (s === 'none' || s === 'لا_شيء' || s === '0' || s === '') return []
            return s.split(',').map(x => x.trim()).filter(Boolean)
          }

          const selectedIds = parseSelected(cfg.port_delegate.shop_item)
          const isAll = selectedIds.length === 7
          const isNone = selectedIds.length === 0

          const toggleProduct = (id: string) => {
            let next: string[]
            if (selectedIds.includes(id)) {
              next = selectedIds.filter(x => x !== id)
            } else {
              next = [...selectedIds, id].sort((a, b) => Number(a) - Number(b))
            }

            if (next.length === 0) {
              update('port_delegate', { shop_item: 'none' })
            } else if (next.length === 7) {
              update('port_delegate', { shop_item: 'all' })
            } else {
              update('port_delegate', { shop_item: next.join(',') })
            }
          }

          const selectAll = () => update('port_delegate', { shop_item: 'all' })
          const deselectAll = () => update('port_delegate', { shop_item: 'none' })

          return (
            <TaskRow
              img="/images/events/temel_zindan.png"
              label={t('tasks.basicDungeon')}
              enabled={cfg.port_delegate.enabled}
              onToggle={toggle('port_delegate')}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {/* شريط علوي بسيط ونظيف مع أزرار التحكم السريعة */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '10px',
                      fontSize: '11px',
                      fontWeight: 600,
                      background: isNone ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)',
                      border: isNone ? '1px solid rgba(239,68,68,0.3)' : '1px solid rgba(34,197,94,0.3)',
                      color: isNone ? '#f87171' : '#4ade80',
                    }}>
                      {isAll ? t('tasks.allSelected7') : isNone ? t('tasks.delegationOnly') : t('tasks.selectedDungeonRatio', { count: selectedIds.length })}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={selectAll}
                      style={{
                        background: isAll ? 'rgba(34,197,94,0.2)' : 'rgba(34,197,94,0.08)',
                        border: '1px solid rgba(34,197,94,0.25)',
                        borderRadius: '6px',
                        padding: '3px 10px',
                        color: '#86efac',
                        fontSize: '11px',
                        fontWeight: 500,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {t('common.selectAll')}
                    </button>
                    <button
                      type="button"
                      onClick={deselectAll}
                      style={{
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: '6px',
                        padding: '3px 10px',
                        color: '#9ca3af',
                        fontSize: '11px',
                        fontWeight: 500,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {t('common.cancelAll')}
                    </button>
                  </div>
                </div>

                {/* شبكة بسيطة ومباشرة للمنتجات السبعة */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(115px, 1fr))',
                  gap: '8px',
                }}>
                  {dungeonShopProducts.map(item => {
                    const isSelected = selectedIds.includes(item.id)
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={clsx('task-dungeon-product', isSelected ? 'selected' : 'unselected')}
                        onClick={() => toggleProduct(item.id)}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          padding: '8px 6px',
                          background: isSelected
                            ? 'linear-gradient(135deg, rgba(16,185,129,0.14) 0%, rgba(5,150,105,0.08) 100%)'
                            : 'rgba(255,255,255,0.02)',
                          border: isSelected
                            ? '1.5px solid rgba(34,197,94,0.45)'
                            : '1px solid rgba(255,255,255,0.06)',
                          borderRadius: '10px',
                          cursor: 'pointer',
                          position: 'relative',
                          transition: 'all 0.15s ease',
                          boxShadow: isSelected ? '0 0 10px rgba(34,197,94,0.12)' : 'none',
                          opacity: isSelected ? 1 : 0.5,
                          fontFamily: 'inherit',
                          gap: '4px',
                        }}
                      >
                        {/* الأيقونة الرسمية */}
                        <div style={{
                          width: '36px',
                          height: '36px',
                          marginTop: '4px',
                          background: isSelected ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.03)',
                          borderRadius: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          filter: isSelected ? 'drop-shadow(0 0 4px rgba(34,197,94,0.3))' : 'grayscale(40%)',
                        }}>
                          <img
                            src={item.img}
                            alt={t(item.nameKey)}
                            style={{ width: '30px', height: '30px', objectFit: 'contain' }}
                          />
                        </div>

                        {/* اسم المنتج */}
                        <span style={{
                          color: isSelected ? '#f0fdf4' : '#9ca3af',
                          fontSize: '11px',
                          fontWeight: isSelected ? 600 : 500,
                          textAlign: 'center',
                          lineHeight: 1.2,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: '100%',
                        }}>
                          {t(item.nameKey)}
                        </span>

                        {/* السعر */}
                        <span style={{
                          color: isSelected ? '#34d399' : '#6b7280',
                          fontSize: '9px',
                          fontWeight: 500,
                        }}>
                          {item.price}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            </TaskRow>
          )
        })()}

        {/* التوسع الإقليمي */}
        <TaskRow
          img="/images/events/bolgesel_genisleme.png" label={t('tasks.territoryExpansion')}
          enabled={cfg.territory_expansion.enabled} onToggle={toggle('territory_expansion')}
        />

        {/* صندوق مشعل رويال — coming soon */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '12px', padding: '12px 14px', opacity: 0.5,
        }}>
          <span style={{ fontSize: '20px' }}>🎰</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>{t('tasks.torchChest')}</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>{t('tasks.torchChestDesc')}</div>
          </div>
          <Toggle value={false} onChange={() => {}} disabled size="sm" />
        </div>

        {/* فتح صندوق مشعل رويال — coming soon */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '12px', padding: '12px 14px', opacity: 0.5,
        }}>
          <span style={{ fontSize: '20px' }}>📦</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>{t('tasks.openTorchChest')}</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>{t('tasks.openTorchChestDesc')}</div>
          </div>
          <Toggle value={false} onChange={() => {}} disabled size="sm" />
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 10. البحث عن الذهب (Gold)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'gold') {
    // gold_gather is optional field, default to empty if not present
    const gg = (cfg as unknown as { gold_gather?: { enabled: boolean; locations: GoldLocation[] } }).gold_gather
      ?? { enabled: false, locations: [] }

    const updateGg = (patch: Partial<typeof gg>) => {
      update('gold_gather' as keyof CastleConfig, { ...gg, ...patch } as unknown as Partial<CastleConfig[keyof CastleConfig]>)
    }

    const addLocation = () => updateGg({ locations: [...gg.locations, { x: 0, y: 0, alliance_tag: '' }] })
    const removeLocation = (i: number) => updateGg({ locations: gg.locations.filter((_, idx) => idx !== i) })
    const setLocation = (i: number, patch: Partial<GoldLocation>) => {
      const locs = gg.locations.map((loc, idx) => idx === i ? { ...loc, ...patch } : loc)
      updateGg({ locations: locs })
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header */}
        <div
          onClick={() => updateGg({ enabled: !gg.enabled })}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: gg.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: gg.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '14px', padding: '12px 14px',
            cursor: 'pointer', userSelect: 'none',
          }}
          className={clsx('transition-colors task-header-card', gg.enabled ? 'enabled' : 'disabled')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/gather/altin.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div className="task-header-title" style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>{t('tasks.goldSearch')}</div>
            </div>
          </div>
          <Toggle value={gg.enabled} onChange={v => updateGg({ enabled: v })} />
        </div>

        {gg.enabled && (
          <>
            {/* Locations */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {gg.locations.map((loc, i) => (
                <div key={i} className="task-gold-location-card" style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.10)',
                  borderRadius: '14px', padding: '14px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#eab308', display: 'inline-block' }} />
                      <span style={{ color: '#9ca3af', fontSize: '13px', fontWeight: 600 }}>{t('tasks.locationNumber', { index: i + 1 })}</span>
                    </div>
                    <button type="button" onClick={() => removeLocation(i)}
                      style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', padding: '2px', display: 'flex' }}>
                      <Trash2 size={15} />
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                    <div style={{ flex: 1 }}>
                      <div className="task-coord-label" style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>X</div>
                      <input
                        type="text"
                        inputMode="numeric"
                        placeholder="0"
                        value={loc.x ?? ''}
                        onChange={e => {
                          const val = e.target.value.replace(/[^0-9]/g, '')
                          setLocation(i, { x: val === '' ? 0 : Number(val) })
                        }}
                        style={inputStyle}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div className="task-coord-label" style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>Y</div>
                      <input
                        type="text"
                        inputMode="numeric"
                        placeholder="0"
                        value={loc.y ?? ''}
                        onChange={e => {
                          const val = e.target.value.replace(/[^0-9]/g, '')
                          setLocation(i, { y: val === '' ? 0 : Number(val) })
                        }}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                  <div>
                    <div style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>{t('tasks.allianceTag')}</div>
                    <input
                      type="text"
                      value={loc.alliance_tag ?? ''}
                      maxLength={5}
                      placeholder="ABC"
                      onChange={e => setLocation(i, { alliance_tag: e.target.value.toUpperCase() })}
                      style={{ ...inputStyle, textTransform: 'uppercase' }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Add location */}
            <button type="button" onClick={addLocation}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                width: '100%', padding: '11px',
                borderRadius: '12px', border: '1px dashed rgba(234,179,8,0.35)',
                background: 'rgba(234,179,8,0.05)',
                color: '#fbbf24', fontSize: '13px', fontWeight: 500,
                cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              <Plus size={15} />
              {t('tasks.addLocation')}
            </button>
          </>
        )}
      </div>
    )
  }

  return null
  }

  const transportHasMissingCoords = Boolean(
    coordsError &&
    cfg.march_manager?.transport?.enabled &&
    (!cfg.march_manager.transport.target_x || cfg.march_manager.transport.target_x <= 0 ||
     !cfg.march_manager.transport.target_y || cfg.march_manager.transport.target_y <= 0)
  )

  return (
    <div className="relative space-y-5 w-full task-tab-content-root">
      <TaskTabs
        active={currentTab}
        onChange={handleTabChange}
        errorTab={transportHasMissingCoords ? 'transport' : null}
      />

      <TaskAccordionContext.Provider value={{ expandedTaskId, toggleTask: toggleTaskAccordion }}>
        {renderTabContent()}
      </TaskAccordionContext.Provider>

      {/* Floating Save Widget on the Right (only when there are changes) */}
      {changesCount > 0 && typeof document !== 'undefined' && createPortal(
        <div
          className="right-4 sm:right-6 md:right-8 bottom-20 slide-in-from-bottom-3 md:bottom-6 z-[999] fixed animate-in duration-200 fade-in"
          style={{ maxWidth: 'calc(100vw - 32px)' }}
        >
          <div className="flex items-center gap-3 bg-gray-900/95 shadow-[0_10px_35px_rgba(0,0,0,0.7)] backdrop-blur-xl px-3.5 py-2 border border-emerald-500/30 rounded-xl text-white task-floating-save-bar">
            {/* Minimal counter */}
            <div className="flex items-center gap-2 text-xs">
              <span className="bg-amber-400 rounded-full w-2 h-2 animate-pulse shrink-0" />
              <span className="font-semibold text-gray-200">
                {isBatchMode
                  ? (batchTargetCount > 0 ? `${changesCount} ${t('common.edits')} • ${batchTargetCount} ${t('accounts.accountUnit')}` : `${changesCount} ${t('common.edits')}`)
                  : `${changesCount} ${t('common.unsavedChanges')}`}
              </span>
            </div>

            {/* Subtle Divider */}
            <div className="bg-white/10 w-px h-4" />

            {/* Action Buttons */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={isPending}
                onClick={handleCancel}
                className="hover:bg-white/10 px-2.5 py-1 rounded-lg text-gray-400 hover:text-white text-xs transition-colors cursor-pointer"
              >
                {t('common.cancel')}
              </button>

              <button
                type="button"
                disabled={isPending || (isBatchMode && batchTargetCount === 0)}
                onClick={handleSave}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1 rounded-lg font-semibold text-xs transition-all duration-200',
                  !isPending && (!isBatchMode || batchTargetCount > 0)
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm hover:shadow-emerald-500/25 active:scale-95 cursor-pointer'
                    : 'bg-white/10 text-gray-500 cursor-not-allowed opacity-60'
                )}
              >
                {isPending ? (
                  <Loader2 size={13} className="text-white animate-spin" />
                ) : (
                  <Check size={13} className="text-white" />
                )}
                <span>
                  {isBatchMode
                    ? (batchTargetCount > 0 ? `${t('common.apply')} (${batchTargetCount})` : t('common.apply'))
                    : t('common.save')}
                </span>
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
