import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ChevronDown, ChevronUp, Play, Square, Settings, Trash2, Edit2, Clock, RefreshCw,
  Zap, Globe, MapPin, Crown, Activity
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { useNavigate } from 'react-router-dom'
import { doc, onSnapshot } from 'firebase/firestore'
import toast from 'react-hot-toast'
import { db } from '../../lib/firebase'
import { ResourceBar } from './ResourceBar'
import { TaskTabContent } from './TaskTabContent'
import { ConfirmStopModal } from './ConfirmStopModal'
import type { Castle, BotState } from '../../types'
import { useBotControl } from '../../hooks/useCastles'

export interface CastleCardProps {
  castle: Castle
  userId: string
  index?: number
  onDelete?: (id: string, wasActive?: boolean) => void
  onEdit?: (castle: Castle) => void
  isPending?: boolean
}

export function CastleCard({ castle, userId, index, onDelete, onEdit, isPending }: CastleCardProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const [liveCastle, setLiveCastle] = useState<Castle>(castle)
  const [liveState, setLiveState] = useState<string>(castle.bot_status.state)
  const [connState, setConnState] = useState<string>(castle.bot_status?.conn_state ?? '')
  const [showStopModal, setShowStopModal] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const botControl = useBotControl(userId)

  // Sync prop changes
  useEffect(() => {
    setLiveCastle(castle)
    setLiveState(castle.bot_status.state)
    setConnState(castle.bot_status?.conn_state ?? '')
  }, [castle])

  // Real-time listener — Firebase هو المصدر الوحيد للحقيقة
  useEffect(() => {
    const ref = doc(db, 'users', userId, 'castles', castle.id)
    const unsub = onSnapshot(ref, (snap) => {
      if (snap.exists()) {
        const data = snap.data() as Record<string, unknown>
        setLiveCastle(prev => ({
          ...prev,
          ...data,
          castle_info: (data.castle_info as any) || prev.castle_info,
          resources:   (data.resources   as any) || prev.resources,
          bot_status:  (data.bot_status  as any) || prev.bot_status,
        }))
        const bs = data.bot_status as any
        if (bs?.state) setLiveState(bs.state)
        if (bs?.conn_state !== undefined) setConnState(bs.conn_state ?? '')
      }
    })
    return unsub
  }, [userId, castle.id])

  const handleRefreshCastleData = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRefreshing(true)
    try {
      await fetch(
        `http://localhost:8000/api/castle-data/${encodeURIComponent(castle.email)}?user_id=${encodeURIComponent(userId)}&castle_id=${encodeURIComponent(castle.id)}`
      )
    } catch (err) {
      console.warn('⚠️ فشل جلب بيانات القلعة:', err)
    } finally {
      setIsRefreshing(false)
    }
  }

  const info      = liveCastle.castle_info || castle.castle_info
  const bot       = liveCastle.bot_status  || castle.bot_status
  const resources = liveCastle.resources   || castle.resources

  const isDisconnected = connState === 'disconnected' || liveState === 'disconnected'
  const isReconnecting = connState === 'reconnecting' || liveState === 'reconnecting'
  const isWaitingCycle = connState === 'waiting'      || liveState === 'waiting'
  const isRunningNow   = connState === 'connected'    || (liveState === 'running' && !isDisconnected && !isReconnecting && !isWaitingCycle)
  const isError        = liveState === 'error'        || connState === 'error'
  const isBotActive    = isRunningNow || isWaitingCycle || isDisconnected || isReconnecting || liveState === 'running'

  const handleToggleClick = () => {
    if (isBotActive) {
      setShowStopModal(true)
    } else {
      setLiveState('running')
      setConnState('connected')
      botControl.mutate({ castle, state: 'running' })
    }
  }

  const handleConfirmStop = () => {
    setLiveState('idle')
    setConnState('idle')
    botControl.mutate({ castle, state: 'idle' }, {
      onSuccess: () => {
        toast.success('تم إيقاف البوت بنجاح')
      },
      onError: () => {
        toast.error('حدث خطأ أثناء إيقاف البوت')
      }
    })
    setShowStopModal(false)
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        'castle-card relative backdrop-blur-xl rounded-2xl overflow-hidden transition-all duration-300',
        isRunningNow
          ? 'castle-card-running bg-gradient-to-br from-emerald-950/40 via-gray-900/90 to-gray-950/95 border-2 border-emerald-500/50 shadow-[0_0_35px_rgba(16,185,129,0.22)] ring-1 ring-emerald-500/30'
          : isWaitingCycle
          ? 'castle-card-waiting bg-gradient-to-br from-sky-950/30 via-gray-900/90 to-gray-950/95 border-2 border-sky-500/40 shadow-[0_0_30px_rgba(56,189,248,0.18)] ring-1 ring-sky-500/30'
          : isDisconnected
          ? 'castle-card-disconnected bg-amber-950/20 border-2 border-amber-500/50 shadow-[0_0_25px_rgba(245,158,11,0.18)]'
          : isReconnecting
          ? 'castle-card-reconnecting bg-orange-950/20 border border-orange-500/35 shadow-md'
          : isPending || liveState === 'pending'
          ? 'castle-card-pending bg-amber-950/15 border border-amber-500/30 shadow-md'
          : isError
          ? 'castle-card-error bg-rose-950/15 border border-rose-500/30 shadow-md'
          : 'castle-card-idle bg-gray-900/70 border border-white/10 hover:border-white/20 hover:bg-gray-900/90 shadow-md'
      )}
    >
      {/* ── Top Shimmer Glowing Ambient Beam ── */}
      {isRunningNow && (
        <div className="top-0 absolute inset-x-0 bg-gradient-to-r from-transparent via-emerald-400 to-transparent h-[2.5px] animate-pulse" />
      )}
      {isWaitingCycle && (
        <div className="top-0 absolute inset-x-0 bg-gradient-to-r from-transparent via-sky-400 to-transparent h-[2.5px] animate-pulse" />
      )}
      {isDisconnected && (
        <div className="top-0 absolute inset-x-0 bg-gradient-to-r from-transparent via-amber-400 to-transparent h-[2.5px] animate-pulse" />
      )}

      {/* ── Header Row ─────────────────────────────────────── */}
      <div className="flex flex-wrap lg:flex-nowrap justify-between items-center gap-4 p-4 sm:p-5">
        {/* Left / Castle Info */}
        <div className="flex flex-1 items-center gap-3.5 min-w-0">
          {/* Index Number */}
          {typeof index === 'number' && (
            <span className="castle-index hidden sm:inline-block w-5 font-mono font-bold text-gray-500 text-xs select-none">
              {String(index + 1).padStart(2, '0')}
            </span>
          )}

          {/* Castle Level / Lord Avatar Badge */}
          <div className="relative flex-shrink-0">
            <div
              className={clsx(
                'castle-avatar flex justify-center items-center rounded-2xl w-12 h-12 font-black text-base transition-all duration-300',
                isRunningNow
                  ? 'avatar-running bg-gradient-to-br from-emerald-500/25 via-emerald-600/35 to-teal-500/25 border-2 border-emerald-400/60 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.4)]'
                  : isWaitingCycle
                  ? 'avatar-waiting bg-gradient-to-br from-sky-500/25 via-sky-600/35 to-blue-500/25 border-2 border-sky-400/60 text-sky-300 shadow-[0_0_20px_rgba(56,189,248,0.3)]'
                  : isDisconnected
                  ? 'avatar-disconnected bg-gradient-to-br from-amber-500/25 via-amber-600/35 to-orange-500/25 border-2 border-amber-400/60 text-amber-300'
                  : 'avatar-idle bg-white/[0.05] border border-white/15 text-white/80'
              )}
            >
              {info.lord_name?.[0]?.toUpperCase() || '🏰'}
            </div>

            {/* Pulsing Beacon Ring on Avatar */}
            {isRunningNow && (
              <span className="-top-1 absolute flex w-3.5 h-3.5 -end-1">
                <span className="inline-flex absolute bg-emerald-400 opacity-80 rounded-full w-full h-full animate-ping"></span>
                <span className="castle-beacon-dot inline-flex relative bg-emerald-500 border-2 border-gray-950 rounded-full w-3.5 h-3.5"></span>
              </span>
            )}
            {isWaitingCycle && (
              <span className="-top-1 absolute flex w-3.5 h-3.5 -end-1">
                <span className="inline-flex absolute bg-sky-400 opacity-80 rounded-full w-full h-full animate-ping"></span>
                <span className="castle-beacon-dot inline-flex relative bg-sky-500 border-2 border-gray-950 rounded-full w-3.5 h-3.5"></span>
              </span>
            )}
            {isDisconnected && (
              <span className="-top-1 absolute flex w-3.5 h-3.5 -end-1">
                <span className="inline-flex absolute bg-amber-400 opacity-80 rounded-full w-full h-full animate-ping"></span>
                <span className="castle-beacon-dot inline-flex relative bg-amber-500 border-2 border-gray-950 rounded-full w-3.5 h-3.5"></span>
              </span>
            )}
          </div>

          {/* Main Titles and Meta Badges */}
          <div className="flex-1 min-w-0">
            {/* Row 1: Name, Alliance, Status Badge */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="castle-lord-name font-bold text-white text-base truncate tracking-wide">
                {info.lord_name}
              </span>

              {info.alliance_name && (
                <span className="castle-alliance-badge bg-primary-500/15 px-2 py-0.5 border border-primary-500/30 rounded-md font-semibold text-primary-300 text-xs">
                  [{info.alliance_name.split(' ')[0]}]
                </span>
              )}

              {info.vip_level > 0 && (
                <span className="castle-vip-badge flex items-center gap-1 bg-gradient-to-r from-amber-500/20 to-yellow-500/20 px-1.5 py-0.5 border border-amber-500/40 rounded-md font-bold text-[10px] text-amber-300">
                  <Crown size={10} className="text-amber-400" />
                  VIP {info.vip_level}
                </span>
              )}

              {/* Status Badge */}
              {isPending || liveState === 'pending' ? (
                <span className="castle-status-badge status-badge-pending flex items-center gap-1 bg-amber-500/15 px-2.5 py-0.5 border border-amber-500/30 rounded-full font-semibold text-amber-400 text-xs">
                  <Clock size={12} />
                  بانتظار الموافقة
                </span>
              ) : isDisconnected ? (
                <span className="castle-status-badge status-badge-disconnected flex items-center gap-1.5 bg-amber-500/20 px-2.5 py-0.5 border border-amber-500/50 rounded-full font-bold text-amber-300 text-xs animate-pulse">
                  <span className="relative flex w-2 h-2">
                    <span className="inline-flex absolute bg-amber-400 opacity-70 rounded-full w-full h-full animate-ping"></span>
                    <span className="inline-flex relative bg-amber-400 rounded-full w-2 h-2"></span>
                  </span>
                  <span>دخول من جهاز آخر</span>
                </span>
              ) : isReconnecting ? (
                <span className="castle-status-badge status-badge-reconnecting flex items-center gap-1.5 bg-orange-500/15 px-2.5 py-0.5 border border-orange-500/35 rounded-full font-semibold text-orange-300 text-xs">
                  <span className="bg-orange-400 rounded-full w-1.5 h-1.5 animate-spin" style={{borderRadius:'50%', border:'2px solid transparent', borderTopColor:'#fb923c'}} />
                  <span>جاري إعادة الاتصال...</span>
                </span>
              ) : isWaitingCycle ? (
                <span className="castle-status-badge status-badge-waiting flex items-center gap-1.5 bg-sky-500/15 shadow-[0_0_10px_rgba(56,189,248,0.2)] px-2.5 py-0.5 border border-sky-500/35 rounded-full font-semibold text-sky-300 text-xs">
                  <span className="relative flex w-2 h-2">
                    <span className="inline-flex absolute bg-sky-400 opacity-50 rounded-full w-full h-full animate-ping"></span>
                    <span className="inline-flex relative bg-sky-400 rounded-full w-2 h-2"></span>
                  </span>
                  <span>بانتظار الدورة القادمة</span>
                </span>
              ) : isRunningNow ? (
                <span className="castle-status-badge status-badge-running flex items-center gap-2 bg-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.35)] px-3 py-0.5 border border-emerald-500/50 rounded-full font-bold text-emerald-300 text-xs animate-pulse">
                  <span className="relative flex w-2 h-2">
                    <span className="inline-flex absolute bg-emerald-400 opacity-80 rounded-full w-full h-full animate-ping"></span>
                    <span className="inline-flex relative bg-emerald-400 rounded-full w-2 h-2"></span>
                  </span>
                  <span>البوت يعمل الآن</span>
                </span>
              ) : isError ? (
                <span className="castle-status-badge status-badge-error flex items-center gap-1.5 bg-rose-500/15 px-2.5 py-0.5 border border-rose-500/40 rounded-full font-semibold text-rose-300 text-xs">
                  <span className="bg-rose-400 rounded-full w-1.5 h-1.5 animate-pulse" />
                  <span>خطأ / تنبيه</span>
                </span>
              ) : (
                <span className="castle-status-badge status-badge-idle flex items-center gap-1.5 bg-white/5 px-2.5 py-0.5 border border-white/10 rounded-full font-medium text-gray-400 text-xs">
                  <span className="bg-gray-500 rounded-full w-1.5 h-1.5" />
                  <span>متوقف</span>
                </span>
              )}
            </div>

            {/* Row 2: Email */}
            <div className="castle-email mt-0.5 font-mono text-gray-400 text-xs truncate select-all">
              {castle.email}
            </div>

            {/* Row 3: Meta Stat Badges */}
            <div className="flex flex-wrap items-center gap-2 mt-2">
              {/* Power */}
              <span className="castle-stat-power flex items-center gap-1 bg-purple-500/10 px-2 py-0.5 border border-purple-500/25 rounded-md font-semibold text-[11px] text-purple-300">
                <Zap size={11} className="text-purple-400" />
                {(info.lord_power / 1_000_000).toFixed(1)}M قوة
              </span>

              {/* Server */}
              <span className="castle-stat-server flex items-center gap-1 bg-blue-500/10 px-2 py-0.5 border border-blue-500/25 rounded-md font-semibold text-[11px] text-blue-300">
                <Globe size={11} className="text-blue-400" />
                #{info.server_id}
              </span>

              {/* Coordinates */}
              <span className="castle-stat-coords flex items-center gap-1 bg-cyan-500/10 px-2 py-0.5 border border-cyan-500/25 rounded-md font-semibold text-[11px] text-cyan-300">
                <MapPin size={11} className="text-cyan-400" />
                {info.coordinates.x},{info.coordinates.y}
              </span>
            </div>
          </div>
        </div>

        {/* Right / Actions */}
        <div className="flex flex-shrink-0 items-center gap-2 ms-auto">
          {/* Main Start / Stop Button */}
          {isPending || liveState === 'pending' ? (
            <span className="flex items-center gap-1 bg-yellow-500/10 px-2.5 py-1.5 border border-yellow-500/30 rounded-lg font-semibold text-yellow-400 text-xs cursor-not-allowed">
              <Clock size={12} />
              بانتظار الموافقة
            </span>
          ) : (
            <button
              onClick={handleToggleClick}
              className={clsx(
                'castle-btn-toggle flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-bold text-xs active:scale-95 transition-all duration-200 cursor-pointer select-none',
                isBotActive
                  ? 'btn-stop-bot bg-rose-500/20 border border-rose-500/50 text-rose-300 hover:bg-rose-500/30 hover:border-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.25)]'
                  : 'btn-start-bot bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white shadow-[0_0_20px_rgba(16,185,129,0.35)]'
              )}
            >
              {isBotActive ? (
                <>
                  <Square size={12} className="fill-rose-400 text-rose-400" />
                  <span>{t('accounts.stopBot')}</span>
                </>
              ) : (
                <>
                  <Play size={12} className="fill-white text-white" />
                  <span>{t('accounts.startBot')}</span>
                </>
              )}
            </button>
          )}

          {/* Icon Controls Group */}
          <div className="castle-icon-group flex items-center gap-0.5 bg-white/[0.04] p-0.5 border border-white/8 rounded-lg">
            {/* Refresh live castle data */}
            <button
              onClick={handleRefreshCastleData}
              disabled={isRefreshing}
              className={clsx(
                'castle-action-btn hover:bg-white/8 p-1.5 rounded-md text-gray-400 hover:text-primary-400 transition-colors cursor-pointer',
                isRefreshing && 'animate-spin text-primary-400'
              )}
              title="تحديث بيانات وموارد القلعة مباشرة من السيرفر"
            >
              <RefreshCw size={14} />
            </button>

            {/* Edit credentials */}
            {onEdit && (
              <button
                onClick={() => onEdit(castle)}
                className="castle-action-btn hover:bg-white/8 p-1.5 rounded-md text-gray-400 hover:text-white transition-colors cursor-pointer"
                title="تعديل بيانات الاعتماد"
              >
                <Edit2 size={14} />
              </button>
            )}

            {/* Castle Detail Page */}
            <button
              onClick={() => navigate(`/accounts/${castle.id}`)}
              className="castle-action-btn hover:bg-white/8 p-1.5 rounded-md text-gray-400 hover:text-white transition-colors cursor-pointer"
              title={t('accounts.settings')}
            >
              <Settings size={14} />
            </button>

            {/* Delete Account */}
            {onDelete && (
              <button
                onClick={() => onDelete(castle.id, castle.is_active)}
                className="castle-action-btn castle-action-btn-delete hover:bg-rose-500/10 p-1.5 rounded-md text-gray-500 hover:text-rose-400 transition-colors cursor-pointer"
                title={t('accounts.confirmDelete')}
              >
                <Trash2 size={14} />
              </button>
            )}

            {/* Expand / Accordion toggle */}
            <button
              onClick={() => setExpanded(e => !e)}
              className={clsx(
                'castle-action-btn castle-action-btn-expand p-1.5 rounded-md transition-colors cursor-pointer',
                expanded
                  ? 'text-primary-400 bg-primary-500/15'
                  : 'text-gray-400 hover:text-white hover:bg-white/8'
              )}
              title={expanded ? 'إخفاء الإعدادات' : 'عرض إعدادات القلعة والمهام'}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>
        </div>
      </div>

      {/* ── Resources Row ─────────────────────────────────── */}
      <div className="castle-resources-row bg-white/[0.01] px-4 sm:px-5 pt-3 pb-3.5 border-white/8 border-t">
        <ResourceBar resources={resources} />
        {bot.last_error && (
          <div className="flex items-center gap-2 mt-2 text-xs text-rose-400">
            <span className="max-w-full truncate" title={bot.last_error}>
              ⚠ {bot.last_error}
            </span>
          </div>
        )}
      </div>

      {/* ── Expanded Task Settings Accordion ───────────────── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="castle-expanded-section border-white/8 border-t w-full"
          >
            <div className="space-y-5 p-4 md:p-6 w-full">
              <div className="w-full">
                <TaskTabContent
                  castle={castle}
                  userId={userId}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Confirm Stop Modal ─────────────────────────────── */}
      <ConfirmStopModal
        isOpen={showStopModal}
        onClose={() => setShowStopModal(false)}
        onConfirm={handleConfirmStop}
        lordName={info.lord_name}
        email={castle.email}
        isPending={botControl.isPending}
      />
    </motion.div>
  )
}

export default CastleCard
