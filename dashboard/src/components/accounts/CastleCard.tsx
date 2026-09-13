import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronUp, Play, Square, Settings, Trash2, Edit2, Clock } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { useNavigate } from 'react-router-dom'
import { doc, onSnapshot } from 'firebase/firestore'
import { db } from '../../lib/firebase'
import { ResourceBar } from './ResourceBar'
import { StatusBadge } from '../ui/StatusBadge'
import { TaskTabContent } from './TaskTabContent'
import { TaskTabs } from './TaskTabs'
import type { Castle, BotState, TaskTab } from '../../types'
import { useBotControl } from '../../hooks/useCastles'

interface CastleCardProps {
  castle: Castle
  userId: string
  index?: number
  onDelete?: (id: string, wasActive?: boolean) => void
  onEdit?: (castle: Castle) => void
  isPending?: boolean
}

// March slot images
const SLOT_IMAGES = ['/images/combat/slot1.png', '/images/combat/slot2.png', '/images/combat/slot3.png', '/images/combat/slot4.png']

export function CastleCard({ castle, userId, index, onDelete, onEdit, isPending }: CastleCardProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState<TaskTab>('gather')
  const [liveState, setLiveState] = useState<BotState>(castle.bot_status.state)
  const botControl = useBotControl(userId)

  // Real-time bot_status listener (lightweight — one field only)
  useEffect(() => {
    const ref = doc(db, 'users', userId, 'castles', castle.id)
    const unsub = onSnapshot(ref, (snap) => {
      const s = snap.data()?.bot_status?.state
      if (s) setLiveState(s as BotState)
    })
    return unsub
  }, [userId, castle.id])

  const toggleBot = () => {
    const newState = liveState === 'running' ? 'idle' : 'running'
    setLiveState(newState as BotState)  // optimistic update
    botControl.mutate({ castle, state: newState as 'running' | 'idle' })
  }

  const info = castle.castle_info
  const bot  = castle.bot_status
  const isRunning = liveState === 'running'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card overflow-hidden"
    >
      {/* ── Header Row ─────────────────────────────────────── */}
      <div className="flex items-start justify-between p-4 gap-3">
        {/* Left: castle info */}
        <div className="flex items-start gap-3 min-w-0">
          {/* Index numbering like 01, 02 */}
          {typeof index === 'number' && (
            <span className="text-xs font-bold text-gray-500 self-center font-mono w-5">
              {String(index + 1).padStart(2, '0')}
            </span>
          )}

          {/* Castle level/avatar badge */}
          <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-primary-900/60 border border-primary-700/40 flex items-center justify-center text-sm font-bold text-primary-400">
            {castle.email?.[0]?.toUpperCase() ?? info.castle_level}
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-white truncate">{info.lord_name}</span>
              {info.alliance_name && (
                <span className="text-xs text-gray-400 bg-white/6 px-1.5 py-0.5 rounded">[{info.alliance_name.split(' ')[0]}]</span>
              )}
              {isPending || liveState === 'pending' ? (
                <span className="badge badge-yellow flex items-center gap-1">
                  <Clock size={11} />
                  بانتظار الموافقة
                </span>
              ) : (
                <StatusBadge state={liveState} label={t(`status.${liveState}`)} />
              )}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">{castle.email}</div>
            <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
              <span>⚡ {(info.lord_power / 1_000_000).toFixed(1)}M</span>
              <span>🌍 #{info.server_id}</span>
              <span>📍 {info.coordinates.x},{info.coordinates.y}</span>
              <span>UID: {castle.castle_id ? castle.castle_id.slice(-8) : '—'}</span>
            </div>
          </div>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* March slots */}
          <div className="hidden sm:flex items-center gap-1">
            {Array.from({ length: bot.max_marches }).map((_, i) => (
              <div
                key={i}
                className={clsx(
                  'w-5 h-5 rounded border text-[9px] flex items-center justify-center',
                  i < bot.active_marches
                    ? 'bg-primary-700/60 border-primary-600/50 text-primary-300'
                    : 'bg-white/4 border-white/10 text-gray-600'
                )}
              >
                {i < bot.active_marches ? '⚔' : '·'}
              </div>
            ))}
          </div>

          {/* Action button */}
          {isPending || liveState === 'pending' ? (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-yellow-500/30 bg-yellow-500/10 text-yellow-500 cursor-not-allowed">
              <Clock size={12} />
              بانتظار الموافقة
            </span>
          ) : (
            <button
              onClick={toggleBot}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
                isRunning
                  ? 'bg-red-600/20 text-red-400 border border-red-600/30 hover:bg-red-600/30'
                  : 'bg-primary-600/20 text-primary-400 border border-primary-600/30 hover:bg-primary-600/30'
              )}
            >
              {isRunning ? <Square size={12} /> : <Play size={12} />}
              {isRunning ? t('accounts.stopBot') : t('accounts.startBot')}
            </button>
          )}

          {/* Edit Credentials */}
          {onEdit && (
            <button
              onClick={() => onEdit(castle)}
              className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/8 transition-colors"
              title="تعديل بيانات الاعتماد"
            >
              <Edit2 size={15} />
            </button>
          )}

          <button
            onClick={() => navigate(`/accounts/${castle.id}`)}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/8 transition-colors"
            title={t('accounts.settings')}
          >
            <Settings size={15} />
          </button>

          {onDelete && (
            <button
              onClick={() => onDelete(castle.id, castle.is_active)}
              className="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-600/10 transition-colors"
              title={t('accounts.confirmDelete')}
            >
              <Trash2 size={15} />
            </button>
          )}

          <button
            onClick={() => setExpanded(e => !e)}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/8 transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* ── Resources Row ──────────────────────────────────── */}
      <div className="px-4 pb-3 border-t border-white/6 pt-3">
        <ResourceBar resources={castle.resources} />
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-600">
          <span>{t('accounts.lastRun')}: <span className="text-gray-400">{formatRelativeTime(bot.last_run_time)}</span></span>
          <span>{t('accounts.nextRun')}: <span className="text-gray-400">{formatRelativeTime(bot.next_run_time)}</span></span>
          {bot.last_error && (
            <span className="text-red-400 truncate max-w-[200px]" title={bot.last_error}>⚠ {bot.last_error}</span>
          )}
        </div>
      </div>

      {/* ── Expanded Tabs ──────────────────────────────────── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="border-t border-white/8 w-full"
          >
            <div className="p-4 md:p-6 space-y-5 w-full">
              <TaskTabs active={activeTab} onChange={setActiveTab} />
              <div className="w-full">
                <TaskTabContent
                  tab={activeTab}
                  castle={castle}
                  userId={userId}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function formatRelativeTime(iso: string): string {
  if (!iso) return '—'
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const abs  = Math.abs(diff)
    const mins = Math.floor(abs / 60000)
    const hrs  = Math.floor(mins / 60)
    if (diff < 0) return `في ${hrs > 0 ? `${hrs}س` : `${mins}د`}`
    if (hrs > 0)  return `${hrs}س مضت`
    if (mins > 0) return `${mins}د مضت`
    return 'الآن'
  } catch { return '—' }
}
