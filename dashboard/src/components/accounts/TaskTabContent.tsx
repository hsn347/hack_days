import React, { useState, useEffect, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Plus, Trash2, Check, RotateCcw, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { Toggle } from '../ui/Toggle'
import { useUpdateCastleConfig } from '../../hooks/useCastles'
import type { Castle, TaskTab, CastleConfig, GoldLocation } from '../../types'
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

/** زر رقمي +/- */
function Stepper({ value, min = 1, max = 99, onChange }: { value: number; min?: number; max?: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        style={stepBtn}
      >−</button>
      <span style={{ color: '#22c55e', fontWeight: 700, fontSize: '15px', minWidth: '24px', textAlign: 'center' }}>{value}</span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        style={stepBtn}
      >+</button>
    </div>
  )
}

/** بطاقة مورد قابلة للتحديد */
function ResCard({ img, label, selected, onClick }: { img: string; label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        flex: '1 1 0',
        minWidth: '80px',
        padding: '12px 8px',
        borderRadius: '12px',
        border: selected ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
        background: selected ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
        cursor: 'pointer',
        transition: 'all 0.15s',
        color: selected ? '#6ee7b7' : '#9ca3af',
        fontSize: '12px', fontWeight: selected ? 600 : 400,
        fontFamily: 'inherit',
      }}
    >
      <img src={img} alt={label} style={{ width: '36px', height: '36px', objectFit: 'contain' }}
        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
      />
      {label}
    </button>
  )
}

/** صف مهمة مع toggle و optional children */
function TaskRow({
  img, emoji, label, description, enabled, onToggle, children, comingSoon,
}: {
  img?: string; emoji?: string; label: string; description?: string;
  enabled: boolean; onToggle: (v: boolean) => void;
  children?: React.ReactNode; comingSoon?: boolean;
}) {
  return (
    <div style={{
      background: enabled && !comingSoon ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
      border: enabled && !comingSoon ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
      borderRadius: '14px', overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
          {img ? (
            <img src={img} alt={label} style={{ width: '32px', height: '32px', objectFit: 'contain', flexShrink: 0 }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : emoji ? (
            <span style={{ fontSize: '20px', flexShrink: 0 }}>{emoji}</span>
          ) : null}
          <div style={{ minWidth: 0 }}>
            <div style={{ color: comingSoon ? '#6b7280' : '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>{label}</div>
            {description && <div style={{ color: '#6b7280', fontSize: '12px', marginTop: '2px' }}>{description}</div>}
          </div>
        </div>
        <Toggle value={enabled} onChange={onToggle} disabled={comingSoon} size="sm" />
      </div>
      {children && enabled && !comingSoon && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ paddingTop: '12px' }}>{children}</div>
        </div>
      )}
    </div>
  )
}

/** عنوان قسم */
function SectionLabel({ text }: { text: string }) {
  return <div style={{ color: '#9ca3af', fontSize: '12px', fontWeight: 500, marginBottom: '8px' }}>{text}</div>
}

// ─── Resource definitions ────────────────────────────────────────────────────

const MARCH_RESOURCES = [
  { v: 2, img: '/images/gather/mtahil.png', label: 'القمح' },
  { v: 3, img: '/images/gather/modun.png',  label: 'الخشب' },
  { v: 4, img: '/images/gather/mdemir.png', label: 'الحديد' },
  { v: 5, img: '/images/gather/mkuvars.png',label: 'الكوارتز' },
  { v: 1, img: '/images/gather/altin.png',  label: 'الذهب' },
]

const TRANSPORT_RESOURCES = [
  { id: 1002, img: '/images/resources/mtahil.png', label: 'القمح' },
  { id: 1003, img: '/images/resources/modun.png',  label: 'الخشب' },
  { id: 1004, img: '/images/resources/mdemir.png', label: 'الحديد' },
  { id: 1005, img: '/images/resources/mkuvars.png',label: 'الكوارتز' },
]

const WATERMILL_RESOURCES = [
  { key: 'food',    img: '/images/watermill/uretimtahil.png',  label: 'القمح'  },
  { key: 'wood',    img: '/images/watermill/uretimodun.png',   label: 'الخشب'  },
  { key: 'iron',    img: '/images/watermill/uretimdemir.png',  label: 'الحديد' },
  { key: 'diamond', img: '/images/watermill/uretimkuvars.png', label: 'ألماس' },
]

// أنواع القوات والتدريب العسكري
const BARRACKS_TYPES = [
  { key: 'infantry', label: 'مشاة'  },
  { key: 'cavalry',  label: 'فرسان' },
  { key: 'archers',  label: 'رماة'  },
  { key: 'chariots', label: 'عربات' },
]

const PETS = [
  { name: 'غزال' }, { name: 'أسد' },  { name: 'صقر' },
  { name: 'ذئب'  }, { name: 'نمر' },  { name: 'دب'   },
  { name: 'فيل'  }, { name: 'تنين' },
]

const TACTICS_OPTIONS = [
  { id: 'القلعة الفارغة', label: 'القلعة الفارغة' },
  { id: 'قمة الإتقان',   label: 'قمة الإتقان'   },
]

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
  tab: TaskTab
  castle: Castle
  userId: string
}

export function TaskTabContent({ tab, castle, userId }: Props) {
  // Local draft of castle.config — allows multiple edits without immediately saving to Firebase
  const [draftConfig, setDraftConfig] = useState<CastleConfig>(() =>
    JSON.parse(JSON.stringify(castle.config))
  )

  const lastSavedConfigRef = useRef<CastleConfig>(castle.config)
  const currentCastleIdRef = useRef<string>(castle.id)

  // Sync with Firestore when castle changes (switch castle or server refresh)
  useEffect(() => {
    if (currentCastleIdRef.current !== castle.id) {
      currentCastleIdRef.current = castle.id
      lastSavedConfigRef.current = castle.config
      setDraftConfig(JSON.parse(JSON.stringify(castle.config)))
      return
    }
    if (JSON.stringify(lastSavedConfigRef.current) !== JSON.stringify(castle.config)) {
      lastSavedConfigRef.current = castle.config
      setDraftConfig(JSON.parse(JSON.stringify(castle.config)))
    }
  }, [castle.id, castle.config])

  const updateConfig = useUpdateCastleConfig(userId, castle.id)

  const changesCount = useMemo(() => {
    return countConfigChanges(lastSavedConfigRef.current, draftConfig)
  }, [draftConfig])

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

  const handleSave = () => {
    if (changesCount === 0 || updateConfig.isPending) return

    const changedSections: Partial<CastleConfig> = {}
    for (const key of Object.keys(draftConfig) as (keyof CastleConfig)[]) {
      if (JSON.stringify(draftConfig[key]) !== JSON.stringify(castle.config[key])) {
        ;(changedSections as Record<string, unknown>)[key] = draftConfig[key]
      }
    }

    const origGg = (castle.config as unknown as { gold_gather?: unknown }).gold_gather
    const draftGg = (draftConfig as unknown as { gold_gather?: unknown }).gold_gather
    if (JSON.stringify(draftGg) !== JSON.stringify(origGg)) {
      (changedSections as Record<string, unknown>).gold_gather = draftGg
    }

    const count = changesCount
    updateConfig.mutate(changedSections, {
      onSuccess: () => {
        lastSavedConfigRef.current = JSON.parse(JSON.stringify(draftConfig))
        toast.success(`✅ تم حفظ ${count} تغييرات بنجاح`)
      },
      onError: (err) => {
        toast.error('❌ فشل حفظ التغييرات: ' + (err instanceof Error ? err.message : 'خطأ غير معروف'))
      },
    })
  }

  const handleCancel = () => {
    if (changesCount === 0) return
    setDraftConfig(JSON.parse(JSON.stringify(lastSavedConfigRef.current)))
    toast('تم إلغاء التغييرات واستعادة الإعدادات الأصلية', { icon: '↩️' })
  }

  const cfg = draftConfig

  function renderTabContent() {
    // ─────────────────────────────────────────────────────────────────────────
    // 1. جمع الموارد (Gather)
    // ─────────────────────────────────────────────────────────────────────────
    if (tab === 'gather') {
    const g = cfg.march_manager.gather
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header toggle */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: g.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: g.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/gather/mtahil.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>جمع الموارد</div>
              <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
                {g.enabled ? 'المهمة مفعّلة' : 'المهمة معطّلة'}
              </div>
            </div>
          </div>
          <Toggle value={g.enabled} onChange={v => update('march_manager', { gather: { ...g, enabled: v } })} />
        </div>

        {/* Sub-options only shown when enabled */}
        {g.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Level stepper */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <SectionLabel text="الحد الأدنى لمستوى الموارد" />
              <Stepper value={g.level} min={1} max={7} onChange={v => update('march_manager', { gather: { ...g, level: v } })} />
            </div>

            {/* Resource type cards */}
            <div>
              <SectionLabel text="نوع المورد" />
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {MARCH_RESOURCES.map(r => (
                  <ResCard
                    key={r.v}
                    img={r.img}
                    label={r.label}
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
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: tr.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: tr.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>⚔️</span>
            <div>
              <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>التدريب العسكري</div>
              <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
                {tr.enabled ? 'المهمة مفعّلة' : 'المهمة معطّلة'}
              </div>
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
                  <div key={key} style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.10)',
                    borderRadius: '14px', padding: '14px',
                  }}>
                    {/* Card header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                        <span style={{ color: '#9ca3af', fontSize: '13px', fontWeight: 600 }}>قوات #{idx + 1}</span>
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
                    <SectionLabel text="نوع القوات" />
                    <div style={{ display: 'flex', gap: '6px', marginBottom: '12px', flexWrap: 'wrap' }}>
                      {BARRACKS_TYPES.map(b => {
                        const isSelected = b.key === key
                        const isUsedElsewhere = !isSelected && activeList.includes(b.key as BarracksKey)
                        return (
                          <button
                            key={b.key}
                            type="button"
                            disabled={isUsedElsewhere}
                            onClick={() => {
                              if (isUsedElsewhere) return
                              const newLevels = { ...tr.levels, [key]: 0, [b.key]: tr.levels[key] || 1 }
                              update('train', { levels: newLevels } as Partial<typeof tr>)
                            }}
                            style={{
                              flex: '1 1 0', minWidth: '80px',
                              padding: '8px 6px', borderRadius: '10px',
                              border: isSelected ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                              background: isSelected ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                              color: isSelected ? '#6ee7b7' : isUsedElsewhere ? '#374151' : '#9ca3af',
                              fontSize: '12px', fontWeight: isSelected ? 600 : 400,
                              cursor: isUsedElsewhere ? 'not-allowed' : 'pointer',
                              fontFamily: 'inherit', transition: 'all 0.15s',
                              opacity: isUsedElsewhere ? 0.38 : 1,
                            }}
                          >
                            {b.label}
                          </button>
                        )
                      })}
                    </div>

                    {/* Level stepper */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <SectionLabel text="المستوى" />
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
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                  width: '100%', padding: '11px',
                  borderRadius: '12px', border: '1px dashed rgba(34,197,94,0.3)',
                  background: 'rgba(16,185,129,0.05)',
                  color: '#6ee7b7', fontSize: '13px', fontWeight: 500,
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'all 0.15s',
                }}
              >
                <Plus size={15} />
                إضافة نوع قوات
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
        }}>
          <span style={{ fontSize: '24px' }}>🗡️</span>
          <div>
            <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>الهجوم والمسيرات الحربية</div>
            <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
              اختر الجيش وحدد أهداف الهجوم واستكشاف الأطلال والملاجئ
            </div>
          </div>
        </div>

        {/* Formation selector */}
        <div>
          <SectionLabel text="الجيش المحدد" />
          <div style={{ display: 'flex', gap: '8px' }}>
            {[1, 2, 3, 4].map(f => (
              <button
                key={f}
                type="button"
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
                  alt={`تشكيلة ${f}`}
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
            { key: 'elf',      img: '/images/combat/elitifrit.png',   label: 'نخبة العفريت',    desc: 'يستخدم الجيش المحدد للهجوم' },
            { key: 'invaders', img: '/images/combat/yagmaci.png',     label: 'الغزاة',           desc: 'يستخدم الجيش المحدد للهجوم' },
            { key: 'rebels',   img: '/images/combat/yagmaci.png',     label: 'نخبة المتمردين',  desc: 'يستخدم الجيش المحدد للهجوم' },
          ] as const).map(opt => {
            const isActive = combatChoice === opt.key
            const configData = opt.key === 'elf' ? mm.elf : opt.key === 'invaders' ? mm.invaders : mm.rebels
            return (
              <div key={opt.key} style={{
                background: isActive ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)',
                border: isActive ? '1px solid rgba(34,197,94,0.25)' : '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px', padding: '12px 14px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <img src={opt.img} alt="" style={{ width: '28px', height: '28px', objectFit: 'contain' }}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    <div>
                      <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>{opt.label}</div>
                      <div style={{ color: '#6b7280', fontSize: '11px' }}>{opt.desc}</div>
                    </div>
                  </div>
                  <Toggle value={isActive} onChange={v => setCombatChoice(v ? opt.key : null)} size="sm" />
                </div>
                {/* Level for invaders/rebels */}
                {isActive && opt.key !== 'elf' && (
                  <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ color: '#9ca3af', fontSize: '12px' }}>الحد الأقصى للمستوى</span>
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
        <div style={{
          background: mm.ruins.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: mm.ruins.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: mm.ruins.enabled ? '12px' : 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <img src="/images/combat/kesif.png" alt="" style={{ width: '28px' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              <div>
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>الأطلال</div>
                <div style={{ color: '#6b7280', fontSize: '11px' }}>مسيرة واحدة فقط</div>
              </div>
            </div>
            <Toggle value={mm.ruins.enabled} onChange={v => update('march_manager', { enabled: true, ruins: { ...mm.ruins, enabled: v } })} size="sm" />
          </div>
          {mm.ruins.enabled && (
            <div style={{ marginTop: '4px' }}>
              <SectionLabel text="مدة المسيرة" />
              <div style={{ display: 'flex', gap: '6px' }}>
                {[
                  { s: 900,   label: 'سريع',    sub: '15 دق'  },
                  { s: 3600,  label: 'عادي',    sub: 'ساعة'   },
                  { s: 7200,  label: 'بطيء',    sub: 'ساعتان' },
                  { s: 43200, label: 'نصف يوم', sub: ''        },
                ].map(opt => (
                  <button
                    key={opt.s}
                    type="button"
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
                    <div>{opt.label}</div>
                    {opt.sub && <div style={{ fontSize: '10px', opacity: 0.75 }}>{opt.sub}</div>}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Stronghold */}
        <div style={{
          background: mm.stronghold.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: mm.stronghold.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: mm.stronghold.enabled ? '12px' : 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <img src="/images/prestige/siginak (1).png" alt="" style={{ width: '28px' }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              <div>
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>الملجأ</div>
                <div style={{ color: '#6b7280', fontSize: '11px' }}>هجوم مرحلي على الملاجئ</div>
              </div>
            </div>
            <Toggle value={mm.stronghold.enabled} onChange={v => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, enabled: v } })} size="sm" />
          </div>
          {mm.stronghold.enabled && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#9ca3af', fontSize: '12px' }}>الحد الأقصى للمستوى</span>
                <Stepper value={mm.stronghold.level} min={1} max={35}
                  onChange={v => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, level: v } })} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#9ca3af', fontSize: '12px' }}>عدد الهجمات في وقت واحد</span>
                <Stepper
                  value={Math.min(mm.stronghold.count || 1, 5)}
                  min={1}
                  max={5}
                  onChange={v => update('march_manager', { enabled: true, stronghold: { ...mm.stronghold, count: v } })}
                />
              </div>
            </>
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
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: wm.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: wm.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/watermill/uretimbonusust.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>مكافأة الطاحونة</div>
              <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
                {wm.enabled ? 'المهمة مفعّلة' : 'المهمة معطّلة'}
              </div>
            </div>
          </div>
          <Toggle value={wm.enabled} onChange={toggle('watermill')} />
        </div>

        {wm.enabled && (
          <>
            <div>
              <SectionLabel text="أنواع المكافآت" />
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {WATERMILL_RESOURCES.map(r => (
                  <ResCard
                    key={r.key}
                    img={r.img}
                    label={r.label}
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
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>الشراء من متجر التحالف</div>
                <div style={{ color: '#6b7280', fontSize: '11px' }}>يشتري من متجر التحالف إذا لم يكن في المخزون</div>
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
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: tr.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: tr.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🔗</span>
            <div>
              <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>مساعدة الموارد</div>
              <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
                {tr.enabled ? 'المهمة مفعّلة' : 'المهمة معطّلة'}
              </div>
            </div>
          </div>
          <Toggle value={tr.enabled} onChange={v => update('march_manager', { transport: { ...tr, enabled: v } })} />
        </div>

        {tr.enabled && (
          <>
            <div>
              <SectionLabel text="أنواع الموارد" />
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {TRANSPORT_RESOURCES.map(r => (
                  <ResCard
                    key={r.id}
                    img={r.img}
                    label={r.label}
                    selected={tr.resource_ids.includes(r.id)}
                    onClick={() => toggleResId(r.id)}
                  />
                ))}
              </div>
            </div>

            <div>
              <SectionLabel text="الموقع" />
              <div style={{ display: 'flex', gap: '10px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>X</div>
                  <input
                    type="number"
                    value={tr.target_x ?? 0}
                    onChange={e => update('march_manager', { transport: { ...tr, target_x: Number(e.target.value) } })}
                    style={inputStyle}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>Y</div>
                  <input
                    type="number"
                    value={tr.target_y ?? 0}
                    onChange={e => update('march_manager', { transport: { ...tr, target_y: Number(e.target.value) } })}
                    style={inputStyle}
                  />
                </div>
              </div>
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
      { key: 'smuggler',   img: '/images/prestige/kacakci.png',        label: 'متجر المهربين',  desc: '10 مشتريات بالموارد' },
      { key: 'gather',     img: '/images/prestige/uretimtahil (1).png', label: 'جمع الموارد',    desc: 'يجمع 25 ألف من كل مورد' },
      { key: 'watermill',  img: '/images/development/tamponhasat.png',  label: 'مكافأة الطاحونة', desc: 'يفعّل مكافأة الطاحونة ويشتريها إن لم تتوفر' },
      { key: 'train',      img: '/images/prestige/asker_egit.png',      label: 'تدريب الجنود',  desc: 'يدرّب 250 من كل جندي' },
      { key: 'invaders',   img: '/images/prestige/yagmaci.png',         label: 'الغزاة',         desc: 'يقاتل 5 غزاة' },
      { key: 'stronghold', img: '/images/prestige/siginak (1).png',     label: 'الملجأ',         desc: 'يهجم على ملجأين' },
    ] as const

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: pr.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: pr.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/prestige/kacakci.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>مهام الهيبة</div>
              <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
                {pr.enabled ? 'المهمة مفعّلة' : 'المهمة معطّلة'}
              </div>
            </div>
          </div>
          <Toggle value={pr.enabled} onChange={toggle('prestige')} />
        </div>

        {pr.enabled && (
          <>
            {subtaskDefs.map(st => (
              <div key={st.key} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                background: pr.subtasks[st.key] ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
                border: pr.subtasks[st.key] ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px', padding: '12px 14px',
              }}>
                <img src={st.img} alt="" style={{ width: '30px', height: '30px', objectFit: 'contain', flexShrink: 0 }}
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>{st.label}</div>
                  <div style={{ color: '#6b7280', fontSize: '11px' }}>{st.desc}</div>
                </div>
                <Toggle
                  value={pr.subtasks[st.key]}
                  onChange={v => update('prestige', { subtasks: { ...pr.subtasks, [st.key]: v } } as Partial<typeof pr>)}
                  size="sm"
                />
              </div>
            ))}

            {/* invaders max level */}
            {pr.subtasks.invaders && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
                <span style={{ color: '#9ca3af', fontSize: '12px' }}>الحد الأقصى لمستوى الغزاة</span>
                <Stepper value={pr.invaders_max_lv} min={1} max={35}
                  onChange={v => update('prestige', { invaders_max_lv: v } as Partial<typeof pr>)} />
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 7. المهام اليومية (Daily)
  // ─────────────────────────────────────────────────────────────────────────
  if (tab === 'daily') {
    const sh = cfg.shield
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* قافلة الغنيمة */}
        <TaskRow
          img="/images/daily/ganimetkaravani.png" label="قافلة الغنيمة"
          description="إرسال القافلة وجمع الجوائز تلقائياً"
          enabled={cfg.caravan.enabled} onToggle={toggle('caravan')}
        />

        {/* مهام التحالف */}
        <TaskRow
          img="/images/daily/lonca.png" label="مهام التحالف"
          description="مساعدة الأعضاء وتبرعات العلوم"
          enabled={cfg.alliance.enabled} onToggle={toggle('alliance')}
        />

        {/* دورية الحيوانات */}
        <TaskRow
          emoji="🦅" label="دورية الحيوانات"
          description="دورية الحيوان الأليف واستلام جوائزها"
          enabled={cfg.pet_patrol.enabled} onToggle={toggle('pet_patrol')}
        >
          <div>
            <SectionLabel text="الحيوان الأليف" />
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {PETS.map(p => (
                <button key={p.name} type="button"
                  onClick={() => update('pet_patrol', { pet: p.name })}
                  style={{
                    padding: '5px 10px', borderRadius: '8px', fontFamily: 'inherit',
                    border: cfg.pet_patrol.pet === p.name ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                    background: cfg.pet_patrol.pet === p.name ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                    color: cfg.pet_patrol.pet === p.name ? '#6ee7b7' : '#9ca3af',
                    fontSize: '12px', cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >{p.name}</button>
              ))}
            </div>
          </div>
        </TaskRow>

        {/* القدرة على التحمل (Stamina) */}
        <TaskRow
          img="/images/daily/dayaniklilik_2.png" label="القدرة على التحمل"
          description="استخدام وشراء جرعات الطاقة"
          enabled={cfg.stamina.enabled} onToggle={toggle('stamina')}
        />

        {/* الشارات الملكية (Hero Draw) */}
        <TaskRow
          img="/images/daily/kahramanlarsalonu.png" label="الشارات الملكية"
          description="تجنيد الأبطال وسحب الصناديق اليومية"
          enabled={cfg.hero_draw.enabled} onToggle={toggle('hero_draw')}
        />

        {/* بنك الادخار */}
        <TaskRow
          emoji="🏦" label="بنك الادخار"
          description="استثمار الذهب وسحب الأرباح تلقائياً"
          enabled={cfg.savings_bank.enabled} onToggle={toggle('savings_bank')}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { d: 7,  label: '7\nأيام' },
              { d: 15, label: '15\nيوم' },
              { d: 30, label: '30\nيوم' },
            ].map(opt => (
              <button key={opt.d} type="button"
                onClick={() => update('savings_bank', { days: opt.d })}
                style={{
                  flex: 1, padding: '10px 6px', borderRadius: '10px',
                  border: cfg.savings_bank.days === opt.d ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                  background: cfg.savings_bank.days === opt.d ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                  color: cfg.savings_bank.days === opt.d ? '#6ee7b7' : '#9ca3af',
                  fontSize: '12px', fontWeight: cfg.savings_bank.days === opt.d ? 600 : 400,
                  cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'pre-line', textAlign: 'center',
                  transition: 'all 0.15s',
                }}
              >{opt.label}</button>
            ))}
          </div>
        </TaskRow>

        {/* القاعة الاستراتيجية (Tactics Hall) */}
        <TaskRow
          img="/images/daily/lonca.png" label="قاعة الاستراتيجيات"
          description="أبحاث قاعة الاستراتيجيات"
          enabled={cfg.tactics_hall.enabled} onToggle={toggle('tactics_hall')}
        >
          <div>
            <SectionLabel text="البحث المستهدف" />
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {TACTICS_OPTIONS.map(t => (
                <button key={t.id} type="button"
                  onClick={() => update('tactics_hall', { tactic: t.id })}
                  style={{
                    flex: 1, padding: '8px', borderRadius: '10px', fontFamily: 'inherit',
                    border: cfg.tactics_hall.tactic === t.id ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                    background: cfg.tactics_hall.tactic === t.id ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                    color: cfg.tactics_hall.tactic === t.id ? '#6ee7b7' : '#9ca3af',
                    fontSize: '12px', cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >{t.label}</button>
              ))}
            </div>
          </div>
        </TaskRow>

        {/* ورشة المواد */}
        <TaskRow
          img="/images/daily/malzeme_atolyesi.png" label="ورشة المواد"
          description="تصنيع خامات العتاد تلقائياً"
          enabled={cfg.material_workshop.enabled} onToggle={toggle('material_workshop')}
        >
          <div>
            <SectionLabel text="الخامات" />
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {[
                { key: 'fang',  label: 'الناب'   },
                { key: 'fur',   label: 'الفرو'   },
                { key: 'metal', label: 'المعدن'  },
                { key: 'coal',  label: 'الفحم'   },
              ].map(m => {
                const active = cfg.material_workshop.materials.includes(m.key)
                return (
                  <button key={m.key} type="button"
                    onClick={() => {
                      const mats = active
                        ? cfg.material_workshop.materials.filter(x => x !== m.key)
                        : [...cfg.material_workshop.materials, m.key]
                      update('material_workshop', { materials: mats })
                    }}
                    style={{
                      padding: '6px 12px', borderRadius: '8px', fontFamily: 'inherit',
                      border: active ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                      background: active ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                      color: active ? '#6ee7b7' : '#9ca3af',
                      fontSize: '12px', cursor: 'pointer', transition: 'all 0.15s',
                    }}
                  >{m.label}</button>
                )
              })}
            </div>
          </div>
        </TaskRow>

        {/* الدرع التلقائي */}
        <TaskRow
          img="/images/daily/kalkan.png" label="الدرع التلقائي"
          description="درع السلام لحماية القلعة"
          enabled={sh.enabled} onToggle={toggle('shield')}
        >
          <div>
            <SectionLabel text="مدة الدرع" />
            <div style={{ display: 'flex', gap: '6px' }}>
              {['8h', '24h', '3d'].map(d => (
                <button key={d} type="button"
                  onClick={() => update('shield', { duration: d as typeof sh.duration })}
                  style={{
                    flex: 1, padding: '8px', borderRadius: '10px', fontFamily: 'inherit',
                    border: sh.duration === d ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                    background: sh.duration === d ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                    color: sh.duration === d ? '#6ee7b7' : '#9ca3af',
                    fontSize: '12px', cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >{d}</button>
              ))}
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
      { key: 'harvest',   img: '/images/development/hasatet.png',     label: 'مكافأة الحصاد',       desc: 'حصاد وافر' },
      { key: 'gather',    img: '/images/development/hasatet.png',     label: 'مكافأة الجمع السريع', desc: 'الجمع السريع' },
      { key: 'warehouse', img: '/images/development/tamponhasat.png', label: 'مكافأة حصاد المخزن', desc: 'حصاد المخزن' },
    ]

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* تنفيذ البناء */}
        <div style={{
          background: bld.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: bld.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', overflow: 'hidden',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <img src="/images/development/insaat.png" style={{ width: '30px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
              <div>
                <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '14px' }}>تنفيذ البناء</div>
                <div style={{ color: '#6b7280', fontSize: '11px' }}>يرقّي ويبني المباني تلقائياً</div>
              </div>
            </div>
            <Toggle value={bld.enabled} onChange={toggle('building')} size="sm" />
          </div>
          {bld.enabled && (
            <div style={{ padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { key: 'upgrade_castle',            label: 'ترقية القلعة' },
                { key: 'speedup_castle',             label: 'تسريع القلعة' },
                { key: 'upgrade_support_buildings',  label: 'ترقية المباني الداعمة' },
              ].map(opt => (
                <label key={opt.key} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input type="checkbox"
                    checked={bld[opt.key as keyof typeof bld] as boolean}
                    onChange={e => update('building', { [opt.key]: e.target.checked } as Partial<typeof bld>)}
                    style={{ accentColor: '#22c55e', width: '15px', height: '15px' }}
                  />
                  <span style={{ color: '#d1d5db', fontSize: '13px' }}>{opt.label}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* إجراء الأبحاث */}
        <TaskRow
          img="/images/development/arastir.png" label="إجراء الأبحاث"
          description="أبحاث الأكاديمية والعلوم"
          enabled={cfg.research.enabled} onToggle={toggle('research')}
        />

        {/* ترقية المعسكرات */}
        <TaskRow
          img="/images/development/insaat.png" label="ترقية المعسكرات"
          description="ترقية الثكنات والمرافق العسكرية"
          enabled={bld.upgrade_support_buildings && bld.enabled}
          onToggle={v => update('building', { upgrade_support_buildings: v })}
        />

        {/* Skills (مكافآت) */}
        {skillDefs.map(s => (
          <div key={s.key} style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            background: sk.target_skills.includes(s.key) && sk.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
            border: sk.target_skills.includes(s.key) && sk.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px', padding: '12px 14px',
          }}>
            <img src={s.img} alt="" style={{ width: '30px', height: '30px', objectFit: 'contain', flexShrink: 0 }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div style={{ flex: 1 }}>
              <div style={{ color: '#f0fdf4', fontWeight: 600, fontSize: '13px' }}>{s.label}</div>
              <div style={{ color: '#6b7280', fontSize: '11px' }}>{s.desc}</div>
            </div>
            <Toggle
              value={sk.enabled && sk.target_skills.includes(s.key)}
              onChange={v => {
                if (!sk.enabled) update('skills', { enabled: true })
                toggleSkill(s.key)
              }}
              size="sm"
            />
          </div>
        ))}

        {/* الريح الثانوية — coming soon */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '12px', padding: '12px 14px', opacity: 0.5,
        }}>
          <span style={{ fontSize: '20px' }}>💨</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>الريح الثانوية</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>قريباً...</div>
          </div>
          <Toggle value={false} onChange={() => {}} disabled size="sm" />
        </div>

        {/* حفر سريع — coming soon */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '12px', padding: '12px 14px', opacity: 0.5,
        }}>
          <span style={{ fontSize: '20px' }}>⛏️</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>حفر سريع</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>قريباً...</div>
          </div>
          <Toggle value={false} onChange={() => {}} disabled size="sm" />
        </div>
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
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>فعالية طروادة</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>يجمع مكافآت فعالية طروادة</div>
          </div>
          <Toggle value={false} onChange={() => {}} disabled size="sm" />
        </div>

        {/* الزنزانة الأساسية (port_delegate) */}
        <TaskRow
          img="/images/events/zindanlar.png" label="الزنزانة الأساسية"
          description="ينفذ مهام الزنزانة ويجمع مكافآتها"
          enabled={cfg.port_delegate.enabled} onToggle={toggle('port_delegate')}
        >
          <div>
            <SectionLabel text="المنتج المطلوب من المتجر" />
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {['1','2','3','4','5','6','7','all'].map(v => (
                <button key={v} type="button"
                  onClick={() => update('port_delegate', { shop_item: v })}
                  style={{
                    padding: '5px 10px', borderRadius: '8px', fontFamily: 'inherit',
                    border: cfg.port_delegate.shop_item === v ? '1.5px solid rgba(34,197,94,0.6)' : '1px solid rgba(255,255,255,0.10)',
                    background: cfg.port_delegate.shop_item === v ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.04)',
                    color: cfg.port_delegate.shop_item === v ? '#6ee7b7' : '#9ca3af',
                    fontSize: '12px', cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >{v === 'all' ? 'الكل' : `#${v}`}</button>
              ))}
            </div>
          </div>
        </TaskRow>

        {/* التوسع الإقليمي */}
        <TaskRow
          img="/images/events/bolgesel_genisleme.png" label="التوسع الإقليمي"
          description="يجمع مكافآت التوسع الإقليمي"
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
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>صندوق مشعل رويال</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>يشتري صندوق المشعل خلال فعالية رويال</div>
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
            <div style={{ color: '#9ca3af', fontWeight: 600, fontSize: '13px' }}>فتح صندوق مشعل رويال</div>
            <div style={{ color: '#6b7280', fontSize: '11px' }}>يفتح صندوق المشعل خلال فعالية رويال</div>
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
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: gg.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
          border: gg.enabled ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.08)',
          borderRadius: '14px', padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img src="/images/gather/altin.png" style={{ width: '32px' }} alt="" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            <div>
              <div style={{ color: '#f0fdf4', fontWeight: 700, fontSize: '15px' }}>البحث عن الذهب</div>
              <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>
                {gg.enabled ? 'المهمة مفعّلة' : 'المهمة معطّلة'}
              </div>
            </div>
          </div>
          <Toggle value={gg.enabled} onChange={v => updateGg({ enabled: v })} />
        </div>

        {gg.enabled && (
          <>
            {/* Locations */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {gg.locations.map((loc, i) => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.10)',
                  borderRadius: '14px', padding: '14px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#eab308', display: 'inline-block' }} />
                      <span style={{ color: '#9ca3af', fontSize: '13px', fontWeight: 600 }}>الموقع #{i + 1}</span>
                    </div>
                    <button type="button" onClick={() => removeLocation(i)}
                      style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', padding: '2px', display: 'flex' }}>
                      <Trash2 size={15} />
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>X</div>
                      <input type="number" value={loc.x}
                        onChange={e => setLocation(i, { x: Number(e.target.value) })}
                        style={inputStyle} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>Y</div>
                      <input type="number" value={loc.y}
                        onChange={e => setLocation(i, { y: Number(e.target.value) })}
                        style={inputStyle} />
                    </div>
                  </div>
                  <div>
                    <div style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '6px' }}>اختصار التحالف</div>
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
              إضافة موقع
            </button>
          </>
        )}
      </div>
    )
  }

  return null
  }

  return (
    <div className="w-full relative">
      {renderTabContent()}

      {/* Fixed Full-Page Bottom Bar via createPortal to body */}
      {typeof document !== 'undefined' && createPortal(
        <div
          className="fixed bottom-0 start-0 end-0 md:start-[var(--sidebar-w)] z-[999] bg-gray-950/95 backdrop-blur-2xl border-t border-white/10 shadow-[0_-10px_40px_rgba(0,0,0,0.85)] px-4 sm:px-8 py-3.5 transition-all duration-300"
          style={{ minHeight: '64px' }}
        >
          <div className="w-full max-w-7xl mx-auto flex items-center justify-between gap-4 flex-wrap">
            {/* Left/Start side: Castle Info & Status */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-primary-900/60 border border-primary-700/40 flex items-center justify-center text-sm font-bold text-primary-400 flex-shrink-0">
                {castle.castle_info?.lord_name?.[0]?.toUpperCase() || '🏰'}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-white text-sm truncate">
                    {castle.castle_info?.lord_name || 'قلعة'}
                  </span>
                  {changesCount > 0 ? (
                    <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-xs font-semibold flex items-center gap-1.5 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      {changesCount} تعديل غير محفوظ
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium flex items-center gap-1.5">
                      <Check size={12} />
                      جميع الإعدادات محفوظة
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-gray-400 truncate mt-0.5">
                  {changesCount > 0
                    ? 'لديك تعديلات معلّقة — اضغط حفظ التغييرات لتطبيقها على البوت، أو إلغاء للرجوع'
                    : `سيرفر #${castle.castle_info?.server_id || '—'} • ${castle.email}`}
                </div>
              </div>
            </div>

            {/* Right/End side: Action Buttons */}
            <div className="flex items-center gap-3 ms-auto">
              {/* Cancel Button */}
              <button
                type="button"
                disabled={changesCount === 0 || updateConfig.isPending}
                onClick={handleCancel}
                className={clsx(
                  'flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium transition-all duration-200 border',
                  changesCount > 0
                    ? 'text-gray-300 border-white/10 hover:text-white hover:bg-white/10 active:scale-95 cursor-pointer'
                    : 'text-gray-600 border-transparent opacity-40 cursor-not-allowed'
                )}
              >
                <RotateCcw size={14} />
                <span>إلغاء التغييرات</span>
              </button>

              {/* Save Button */}
              <button
                type="button"
                disabled={changesCount === 0 || updateConfig.isPending}
                onClick={handleSave}
                className={clsx(
                  'flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold transition-all duration-200 shadow-md',
                  changesCount > 0
                    ? 'bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white shadow-[0_0_20px_rgba(16,185,129,0.35)] active:scale-95 cursor-pointer'
                    : 'bg-white/5 text-gray-500 border border-white/10 opacity-60 cursor-not-allowed'
                )}
              >
                {updateConfig.isPending ? (
                  <Loader2 size={15} className="animate-spin text-white" />
                ) : changesCount > 0 ? (
                  <Check size={15} className="text-white" />
                ) : (
                  <Check size={15} className="text-gray-500" />
                )}
                <span>{changesCount > 0 ? `حفظ التغييرات (${changesCount})` : 'لا توجد تغييرات'}</span>
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
