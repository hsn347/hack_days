import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ChevronDown, ChevronUp, Play, Square, Settings, Trash2, Edit2, Clock, RefreshCw,
  Zap, Globe, MapPin, Swords, Crown, Activity
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
        'relative rounded-2xl transition-all duration-300 overflow-hidden backdrop-blur-xl',
        isRunningNow
          ? 'bg-gradient-to-br from-emerald-950/40 via-gray-900/90 to-gray-950/95 border-2 border-emerald-500/50 shadow-[0_0_35px_rgba(16,185,129,0.22)] ring-1 ring-emerald-500/30'
          : isWaitingCycle
          ? 'bg-gradient-to-br from-sky-950/30 via-gray-900/90 to-gray-950/95 border-2 border-sky-500/40 shadow-[0_0_30px_rgba(56,189,248,0.18)] ring-1 ring-sky-500/30'
          : isDisconnected
          ? 'bg-amber-950/20 border-2 border-amber-500/50 shadow-[0_0_25px_rgba(245,158,11,0.18)]'
          : isReconnecting
          ? 'bg-orange-950/20 border border-orange-500/35 shadow-md'
          : isPending || liveState === 'pending'
          ? 'bg-amber-950/15 border border-amber-500/30 shadow-md'
          : isError
          ? 'bg-rose-950/15 border border-rose-500/30 shadow-md'
          : 'bg-gray-900/70 border border-white/10 hover:border-white/20 hover:bg-gray-900/90 shadow-md'
      )}
    >
      {/* ── Top Shimmer Glowing Ambient Beam ── */}
      {isRunningNow && (
        <div className="top-0 inset-x-0 absolute bg-gradient-to-r from-transparent via-emerald-400 to-transparent h-[2.5px] animate-pulse" />
      )}
      {isWaitingCycle && (
        <div className="top-0 inset-x-0 absolute bg-gradient-to-r from-transparent via-sky-400 to-transparent h-[2.5px] animate-pulse" />
      )}
      {isDisconnected && (
        <div className="top-0 inset-x-0 absolute bg-gradient-to-r from-transparent via-amber-400 to-transparent h-[2.5px] animate-pulse" />
      )}

      {/* ── Header Row ─────────────────────────────────────── */}
      <div className="p-4 sm:p-5 flex flex-wrap lg:flex-nowrap items-center justify-between gap-4">
        {/* Left / Castle Info */}
        <div className="flex items-center gap-3.5 min-w-0 flex-1">
          {/* Index Number */}
          {typeof index === 'number' && (
            <span className="hidden sm:inline-block font-mono text-xs font-bold text-gray-500 w-5 select-none">
              {String(index + 1).padStart(2, '0')}
            </span>
          )}

          {/* Castle Level / Lord Avatar Badge */}
          <div className="relative flex-shrink-0">
            <div
              className={clsx(
                'w-12 h-12 rounded-2xl flex items-center justify-center font-black text-base transition-all duration-300',
                isRunningNow
                  ? 'bg-gradient-to-br from-emerald-500/25 via-emerald-600/35 to-teal-500/25 border-2 border-emerald-400/60 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.4)]'
                  : isWaitingCycle
                  ? 'bg-gradient-to-br from-sky-500/25 via-sky-600/35 to-blue-500/25 border-2 border-sky-400/60 text-sky-300 shadow-[0_0_20px_rgba(56,189,248,0.3)]'
                  : isDisconnected
                  ? 'bg-gradient-to-br from-amber-500/25 via-amber-600/35 to-orange-500/25 border-2 border-amber-400/60 text-amber-300'
                  : 'bg-white/[0.05] border border-white/15 text-white/80'
              )}
            >
              {info.lord_name?.[0]?.toUpperCase() || '🏰'}
            </div>

            {/* Pulsing Beacon Ring on Avatar */}
            {isRunningNow && (
              <span className="absolute -top-1 -end-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-80"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-gray-950"></span>
              </span>
            )}
            {isWaitingCycle && (
              <span className="absolute -top-1 -end-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-80"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-sky-500 border-2 border-gray-950"></span>
              </span>
            )}
            {isDisconnected && (
              <span className="absolute -top-1 -end-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-80"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-amber-500 border-2 border-gray-950"></span>
              </span>
            )}

            {/* Castle Level Tag at Bottom */}
            <span
              className={clsx(
                'absolute -bottom-1 -start-1 text-[9px] font-extrabold px-1.5 py-0.2 rounded-full border shadow-sm backdrop-blur-md',
                isBotActive
                  ? 'bg-amber-500/25 border-amber-400/60 text-amber-300'
                  : 'bg-gray-800/80 border-white/20 text-gray-300'
              )}
            >
              Lv.{info.castle_level || 1}
            </span>
          </div>

          {/* Main Titles and Meta Badges */}
          <div className="min-w-0 flex-1">
            {/* Row 1: Name, Alliance, Status Badge */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-white text-base tracking-wide truncate">
                {info.lord_name}
              </span>

              {info.alliance_name && (
                <span className="text-xs font-semibold text-primary-300 bg-primary-500/15 border border-primary-500/30 px-2 py-0.5 rounded-md">
                  [{info.alliance_name.split(' ')[0]}]
                </span>
              )}

              {info.vip_level > 0 && (
                <span className="flex items-center gap-1 text-[10px] font-bold text-amber-300 bg-gradient-to-r from-amber-500/20 to-yellow-500/20 border border-amber-500/40 px-1.5 py-0.5 rounded-md">
                  <Crown size={10} className="text-amber-400" />
                  VIP {info.vip_level}
                </span>
              )}

              {/* Status Badge */}
              {isPending || liveState === 'pending' ? (
                <span className="flex items-center gap-1 text-xs font-semibold text-amber-400 bg-amber-500/15 border border-amber-500/30 px-2.5 py-0.5 rounded-full">
                  <Clock size={12} />
                  بانتظار الموافقة
                </span>
              ) : isDisconnected ? (
                <span className="flex items-center gap-1.5 text-xs font-bold text-amber-300 bg-amber-500/20 border border-amber-500/50 px-2.5 py-0.5 rounded-full animate-pulse">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-70"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400"></span>
                  </span>
                  <span>دخول من جهاز آخر</span>
                </span>
              ) : isReconnecting ? (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-orange-300 bg-orange-500/15 border border-orange-500/35 px-2.5 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-400 animate-spin" style={{borderRadius:'50%', border:'2px solid transparent', borderTopColor:'#fb923c'}} />
                  <span>جاري إعادة الاتصال...</span>
                </span>
              ) : isWaitingCycle ? (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-sky-300 bg-sky-500/15 border border-sky-500/35 px-2.5 py-0.5 rounded-full shadow-[0_0_10px_rgba(56,189,248,0.2)]">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-50"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-400"></span>
                  </span>
                  <span>بانتظار الدورة القادمة</span>
                </span>
              ) : isRunningNow ? (
                <span className="flex items-center gap-2 text-xs font-bold text-emerald-300 bg-emerald-500/20 border border-emerald-500/50 px-3 py-0.5 rounded-full shadow-[0_0_15px_rgba(16,185,129,0.35)] animate-pulse">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-80"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
                  </span>
                  <span>البوت يعمل الآن</span>
                </span>
              ) : isError ? (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-rose-300 bg-rose-500/15 border border-rose-500/40 px-2.5 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
                  <span>خطأ / تنبيه</span>
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs font-medium text-gray-400 bg-white/5 border border-white/10 px-2.5 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-500" />
                  <span>متوقف</span>
                </span>
              )}
            </div>

            {/* Row 2: Email */}
            <div className="text-xs text-gray-400 font-mono mt-0.5 truncate select-all">
              {castle.email}
            </div>

            {/* Row 3: Meta Stat Badges */}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {/* Power */}
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-purple-500/10 border border-purple-500/25 text-purple-300">
                <Zap size={11} className="text-purple-400" />
                {(info.lord_power / 1_000_000).toFixed(1)}M قوة
              </span>

              {/* Server */}
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-blue-500/10 border border-blue-500/25 text-blue-300">
                <Globe size={11} className="text-blue-400" />
                #{info.server_id}
              </span>

              {/* Coordinates */}
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-cyan-500/10 border border-cyan-500/25 text-cyan-300">
                <MapPin size={11} className="text-cyan-400" />
                {info.coordinates.x},{info.coordinates.y}
              </span>

              {/* Marches */}
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-500/10 border border-amber-500/25 text-amber-300">
                <Swords size={11} className="text-amber-400" />
                {bot.active_marches}/{bot.max_marches} مسيرات
              </span>

              {castle.castle_id && (
                <span className="text-[10px] text-gray-500 font-mono hidden sm:inline">
                  UID: {castle.castle_id.slice(-6)}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right / Actions */}
        <div className="flex items-center gap-2 flex-shrink-0 ms-auto">
          {/* Main Start / Stop Button */}
          {isPending || liveState === 'pending' ? (
            <span className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-yellow-500/30 bg-yellow-500/10 text-yellow-400 cursor-not-allowed">
              <Clock size={12} />
              بانتظار الموافقة
            </span>
          ) : (
            <button
              onClick={handleToggleClick}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-200 cursor-pointer active:scale-95 select-none',
                isBotActive
                  ? 'bg-rose-500/20 border border-rose-500/50 text-rose-300 hover:bg-rose-500/30 hover:border-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.25)]'
                  : 'bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white shadow-[0_0_20px_rgba(16,185,129,0.35)]'
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
          <div className="flex items-center gap-0.5 bg-white/[0.04] border border-white/8 rounded-lg p-0.5">
            {/* Refresh live castle data */}
            <button
              onClick={handleRefreshCastleData}
              disabled={isRefreshing}
              className={clsx(
                'p-1.5 rounded-md text-gray-400 hover:text-primary-400 hover:bg-white/8 transition-colors cursor-pointer',
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
                className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/8 transition-colors cursor-pointer"
                title="تعديل بيانات الاعتماد"
              >
                <Edit2 size={14} />
              </button>
            )}

            {/* Castle Detail Page */}
            <button
              onClick={() => navigate(`/accounts/${castle.id}`)}
              className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/8 transition-colors cursor-pointer"
              title={t('accounts.settings')}
            >
              <Settings size={14} />
            </button>

            {/* Delete Account */}
            {onDelete && (
              <button
                onClick={() => onDelete(castle.id, castle.is_active)}
                className="p-1.5 rounded-md text-gray-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                title={t('accounts.confirmDelete')}
              >
                <Trash2 size={14} />
              </button>
            )}

            {/* Expand / Accordion toggle */}
            <button
              onClick={() => setExpanded(e => !e)}
              className={clsx(
                'p-1.5 rounded-md transition-colors cursor-pointer',
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

      {/* ── Live Activity Ticker (When Active) ─────────────── */}
      {isBotActive && (
        <div className={clsx(
          'mx-4 sm:mx-5 mb-3 px-3.5 py-2 rounded-xl flex items-center justify-between gap-3 shadow-inner border',
          isRunningNow
            ? 'bg-gradient-to-r from-emerald-500/15 via-emerald-500/10 to-teal-500/10 border-emerald-500/30'
            : isWaitingCycle
            ? 'bg-gradient-to-r from-sky-500/15 via-sky-500/10 to-blue-500/10 border-sky-500/30'
            : isDisconnected
            ? 'bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-yellow-500/10 border-amber-500/30'
            : 'bg-gradient-to-r from-orange-500/15 via-orange-500/10 to-amber-500/10 border-orange-500/30'
        )}>
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="relative flex h-2.5 w-2.5 shrink-0">
              <span className={clsx(
                'animate-ping absolute inline-flex h-full w-full rounded-full opacity-80',
                isRunningNow ? 'bg-emerald-400' : isWaitingCycle ? 'bg-sky-400' : isDisconnected ? 'bg-amber-400' : 'bg-orange-400'
              )}></span>
              <span className={clsx(
                'relative inline-flex rounded-full h-2.5 w-2.5',
                isRunningNow ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : isWaitingCycle ? 'bg-sky-400 shadow-[0_0_8px_#38bdf8]' : isDisconnected ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24]' : 'bg-orange-400 shadow-[0_0_8px_#fb923c]'
              )}></span>
            </span>
            <span className={clsx(
              'text-xs font-bold truncate',
              isRunningNow ? 'text-emerald-200' : isWaitingCycle ? 'text-sky-200' : isDisconnected ? 'text-amber-200' : 'text-orange-200'
            )}>
              {bot.conn_message || bot.last_run_message || (
                isRunningNow ? 'البوت يعمل الآن ويتابع مهام القلعة والموارد تلقائياً...' :
                isWaitingCycle ? 'اكتملت الدورة — بانتظار موعد الدورة القادمة...' :
                isDisconnected ? 'تم رصد دخول من جهاز آخر — في وضع الانتظار...' :
                'جاري إعادة الاتصال...'
              )}
            </span>
          </div>
          <div className={clsx(
            'flex items-center gap-1.5 text-[11px] font-semibold shrink-0 px-2.5 py-0.5 rounded-md border',
            isRunningNow
              ? 'text-emerald-400 bg-emerald-950/60 border-emerald-500/30'
              : isWaitingCycle
              ? 'text-sky-400 bg-sky-950/60 border-sky-500/30'
              : isDisconnected
              ? 'text-amber-400 bg-amber-950/60 border-amber-500/30'
              : 'text-orange-400 bg-orange-950/60 border-orange-500/30'
          )}>
            <Activity size={12} className="animate-pulse" />
            <span>
              {isRunningNow ? 'متصل ونشط' : isWaitingCycle ? 'في الانتظار' : isDisconnected ? 'جهاز آخر' : 'إعادة اتصال'}
            </span>
          </div>
        </div>
      )}

      {/* ── Resources Row & Timers ─────────────────────────── */}
      <div className="px-4 sm:px-5 pb-3.5 pt-3 border-t border-white/8 bg-white/[0.01]">
        <ResourceBar resources={resources} />
        <div className="flex flex-wrap items-center justify-between gap-3 mt-2.5 text-xs text-gray-500">
          <div className="flex items-center gap-4 flex-wrap">
            <span>
              {t('accounts.lastRun')}:{' '}
              <span className="text-gray-300 font-medium">
                {formatRelativeTime(bot.last_run_time)}
              </span>
            </span>
            <span>
              {t('accounts.nextRun')}:{' '}
              <span className="text-gray-300 font-medium">
                {formatRelativeTime(bot.next_run_time)}
              </span>
            </span>
            {bot.last_error && (
              <span className="text-rose-400 truncate max-w-[200px]" title={bot.last_error}>
                ⚠ {bot.last_error}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Expanded Task Settings Accordion ───────────────── */}
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
