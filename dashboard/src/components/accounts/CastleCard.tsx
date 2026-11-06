import React, { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ChevronDown, ChevronUp, Play, Square, Trash2, Edit2, Clock,
  Zap, Globe, MapPin, Crown, Activity, Lock, ShieldAlert, AlertTriangle,
  Sparkles, Loader2
} from 'lucide-react'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { ResourceBar } from './ResourceBar'
import { TaskTabContent } from './TaskTabContent'
import { ConfirmStopModal } from './ConfirmStopModal'
import { ConfirmPresetModal } from './ConfirmPresetModal'
import { Castle, BotState, FIXED_PRESET_CONFIG } from '../../types'
import { useBotControl, useRealBotStatus, useUpdateCastleConfig } from '../../hooks/useCastles'
import { useAuth } from '../../hooks/useAuth'

export interface CastleCardProps {
  castle: Castle
  userId: string
  index?: number
  onDelete?: (id: string, wasActive?: boolean) => void
  onEdit?: (castle: Castle) => void
  onSetBatchTemplate?: (castleId: string) => void
  isPending?: boolean
  isExpanded?: boolean
  onToggleExpand?: () => void
}

export function CastleCard({
  castle,
  userId,
  index,
  onDelete,
  onEdit,
  onSetBatchTemplate,
  isPending,
  isExpanded,
  onToggleExpand,
}: CastleCardProps) {
  const { t } = useTranslation()
  const isControlled = typeof isExpanded === 'boolean'
  const [internalExpanded, setInternalExpanded] = useState(false)
  const expanded = isControlled ? isExpanded : internalExpanded
  const [hasBeenExpanded, setHasBeenExpanded] = useState(false)

  useEffect(() => {
    if (expanded) setHasBeenExpanded(true)
  }, [expanded])

  const handleToggleExpand = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    if (isControlled) {
      onToggleExpand?.()
    } else {
      setInternalExpanded(prev => {
        const next = !prev
        if (next) setHasBeenExpanded(true)
        return next
      })
    }
  }
  const [showStopModal, setShowStopModal] = useState(false)
  const [showPresetModal, setShowPresetModal] = useState(false)
  const [isApplyingPreset, setIsApplyingPreset] = useState(false)
  const botControl = useBotControl(userId)
  const updateConfig = useUpdateCastleConfig(userId, castle.id)
  const { user } = useAuth()

  const isSuperAdmin = user?.role === 'admin' || user?.email?.trim().toLowerCase() === 'ibraboths@gmail.com'
  const isBanned = !isSuperAdmin && Boolean(user?.is_banned)
  const isExpired = !isSuperAdmin && (
    user?.subscription?.status === 'expired' ||
    (user?.subscription?.expires_at ? new Date(user.subscription.expires_at).getTime() < Date.now() : false)
  )

  // Single Source of Truth: derive mutation and active status directly without local state forks
  const isMutationPending = botControl.isPending && botControl.variables?.castle?.id === castle.id
  const isStarting = isMutationPending && botControl.variables?.state === 'running'
  const isStopping = isMutationPending && botControl.variables?.state === 'idle'

  // WebSocket Real-time listener (Multiplexed single socket per user)
  const { status: realStatus } = useRealBotStatus(castle.id, true, userId)

  // Authoritative active status: User mutation > WebSocket live status > Stored cache status
  const effectiveStatus = useMemo(() => {
    if (isStarting) return 'starting'
    if (isStopping) return 'stopping'
    if (realStatus && realStatus !== 'offline') return realStatus
    return castle.bot_status?.conn_state || castle.bot_status?.state || 'idle'
  }, [isStarting, isStopping, realStatus, castle.bot_status?.conn_state, castle.bot_status?.state])

  const info      = castle.castle_info || {} as any
  const bot       = castle.bot_status  || {} as any
  const resources = castle.resources   || {} as any

  const emailPrefix = (castle.email || '').split('@')[0] || t('common.castle', 'قلعة')
  const isGenericName = !info?.lord_name || ['لورد الإمبراطورية', 'القلعة الملكية', 'قلعة جديدة', 'غير معروف', 'قلعة'].includes(info.lord_name)
  const displayLordName = isGenericName ? emailPrefix : info.lord_name

  const avatarPath = String(info?.avatar || '')
  const isCustomAvatar = Boolean(avatarPath && (avatarPath.startsWith('/') || avatarPath.includes('customAvatar') || avatarPath.startsWith('http')))
  const avatarUrl = isCustomAvatar ? (avatarPath.startsWith('http') ? avatarPath : `/api/castles/${castle.id}/avatar`) : ''
  const [imgError, setImgError] = useState(false)

  const isDeploying      = effectiveStatus === 'deploying'
  const isStoppingActive = isStopping || effectiveStatus === 'stopping'
  const isStartingActive = isStarting || effectiveStatus === 'starting'
  const isError          = !isDeploying && !isStoppingActive && !isStartingActive && (
    effectiveStatus === 'error' ||
    bot?.conn_state === 'error' ||
    bot?.state === 'error'
  )
  const isDisconnected   = !isDeploying && !isStoppingActive && !isStartingActive && !isError && effectiveStatus === 'disconnected'
  const isReconnecting   = !isDeploying && !isStoppingActive && !isStartingActive && !isError && effectiveStatus === 'reconnecting'
  const isWaitingCycle   = !isDeploying && !isStoppingActive && !isStartingActive && !isError && effectiveStatus === 'waiting'
  const isRunningNow     = !isDeploying && !isStoppingActive && !isStartingActive && !isError && (effectiveStatus === 'connected' || effectiveStatus === 'running')
  const isBotActive      = !isError && !isStoppingActive && (isRunningNow || isWaitingCycle || isDisconnected || isReconnecting)

  // مؤقت لتحديث العد التنازلي للدورة تلقائياً كل 30 ثانية
  const [nowTick, setNowTick] = useState(Date.now())
  useEffect(() => {
    if (!isWaitingCycle) return
    const timer = setInterval(() => setNowTick(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [isWaitingCycle])

  // حساب الدقائق المتبقية للدورة القادمة بدقة
  const waitingMinutes = useMemo(() => {
    if (!isWaitingCycle) return null

    // 1. حساب عبر next_run_time إن وُجد في Firestore
    if (bot?.next_run_time) {
      const nextMs = new Date(bot.next_run_time).getTime()
      if (!isNaN(nextMs)) {
        const diffMs = nextMs - nowTick
        if (diffMs > 0) {
          return Math.max(1, Math.round(diffMs / 60000))
        }
      }
    }

    const msg = bot?.conn_message || ''

    // 2. البحث عن عدد الدقائق الصريح (متبقي X دقيقة أو انتظار X دقيقة)
    const explicitMins = msg.match(/(?:متبقي|انتظار)\s*(\d+(?:\.\d+)?)\s*دقيقة/i)
    if (explicitMins) {
      const parsed = Math.round(parseFloat(explicitMins[1]))
      if (parsed > 0) return parsed
    }

    // 3. البحث عن وقت الساعة المستهدفة (مثال: الساعة 15:30)
    const timeMatch = msg.match(/الساعة\s*(\d{1,2}):(\d{2})(?::\d{2})?/)
    if (timeMatch) {
      const targetHour = parseInt(timeMatch[1], 10)
      const targetMin = parseInt(timeMatch[2], 10)
      const now = new Date(nowTick)
      const target = new Date(nowTick)
      target.setHours(targetHour, targetMin, 0, 0)
      const diffMs = target.getTime() - now.getTime()
      if (diffMs < -60000) {
        target.setDate(target.getDate() + 1)
      }
      const diffMins = Math.round((target.getTime() - now.getTime()) / 60000)
      if (diffMins > 0) return diffMins
      return 1
    }

    return null
  }, [isWaitingCycle, bot?.next_run_time, bot?.conn_message, nowTick])

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (isDeploying) {
      toast.error(t('accounts.deployingToast', 'جاري رفع التغييرات إلى السيرفر... يرجى الانتظار حتى اكتمال التحديث واستئناف البوت تلقائياً'))
      return
    }
    if (isBanned) {
      toast.error(t('accounts.bannedToast'))
      return
    }
    if (isExpired) {
      toast.error(t('accounts.expiredToast'))
      return
    }
    if (isBotActive) {
      setShowStopModal(true)
    } else {
      botControl.mutate({ castle, state: 'running' }, {
        onError: (err: any) => {
          toast.error(err instanceof Error ? err.message : t('accounts.botStartError', 'فشل تشغيل البوت'))
        }
      })
    }
  }

  const handleConfirmStop = () => {
    setShowStopModal(false)
    botControl.mutate({ castle, state: 'idle' }, {
      onSuccess: () => {
        toast.success(t('accounts.botStoppedSuccess'))
      },
      onError: (err: any) => {
        toast.error(err instanceof Error ? err.message : t('accounts.botStopError'))
      }
    })
  }

  const handleConfirmPreset = async () => {
    setIsApplyingPreset(true)
    try {
      await updateConfig.mutateAsync(FIXED_PRESET_CONFIG)
      toast.success(t('accounts.fixedPresetSuccess'))
      setShowPresetModal(false)
    } catch {
      toast.error(t('common.error'))
    } finally {
      setIsApplyingPreset(false)
    }
  }

  return (
    <div
      onClick={handleToggleExpand}
      className={clsx(
        'relative border rounded-2xl overflow-hidden transition-colors duration-150 cursor-pointer select-none castle-card',
        (isBanned || isExpired) && !isRunningNow
          ? 'castle-card-locked dark:bg-gray-900 border-rose-500/40'
          : isDeploying
          ? 'castle-card-deploying dark:bg-gray-900 border-amber-500/50 ring-1 ring-amber-500/20'
          : isError
          ? 'castle-card-error dark:bg-gray-900 border-rose-500/50 ring-1 ring-rose-500/20'
          : isRunningNow
          ? 'castle-card-running dark:bg-gray-900 border-emerald-500/50 ring-1 ring-emerald-500/20'
          : isWaitingCycle
          ? 'castle-card-waiting dark:bg-gray-900 border-sky-500/40 ring-1 ring-sky-500/20'
          : isDisconnected
          ? 'castle-card-disconnected dark:bg-gray-900 border-amber-500/40'
          : isReconnecting
          ? 'castle-card-reconnecting dark:bg-gray-900 border-orange-500/40'
          : isPending || effectiveStatus === 'pending'
          ? 'castle-card-pending dark:bg-gray-900 border-amber-500/30'
          : 'castle-card-idle dark:bg-gray-900/90 border-gray-800 hover:border-gray-700'
      )}
    >

      {/* ── Header Row ─────────────────────────────────────── */}
      <div
        className="flex sm:flex-row flex-col justify-between sm:items-center gap-3.5 p-3.5 sm:p-5 select-none castle-card-header"
      >
        {/* Left / Castle Info */}
        <div className="flex items-start sm:items-center gap-3 min-w-0">
          {/* Index Number */}
          {typeof index === 'number' && (
            <span className="hidden sm:inline-block w-5 font-mono font-bold text-gray-500 text-xs select-none castle-index">
              {String(index + 1).padStart(2, '0')}
            </span>
          )}

          {/* Castle Level / Lord Avatar Badge */}
          <div className="relative flex-shrink-0">
            <div
              className={clsx(
                'flex justify-center items-center rounded-2xl w-11 sm:w-12 h-11 sm:h-12 overflow-hidden font-black text-base transition-all duration-300 castle-avatar',
                isDeploying
                  ? 'avatar-deploying bg-gradient-to-br from-amber-500/25 via-amber-600/35 to-orange-500/25 border-2 border-amber-400/60 text-amber-800 dark:text-amber-300'
                  : isError
                  ? 'avatar-error bg-gradient-to-br from-rose-500/25 via-rose-600/35 to-red-500/25 border-2 border-rose-400/60 text-rose-300 shadow-[0_0_15px_rgba(244,63,94,0.3)]'
                  : isRunningNow
                  ? 'avatar-running bg-gradient-to-br from-emerald-500/25 via-emerald-600/35 to-teal-500/25 border-2 border-emerald-400/60 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.4)]'
                  : isWaitingCycle
                  ? 'avatar-waiting bg-gradient-to-br from-sky-500/25 via-sky-600/35 to-blue-500/25 border-2 border-sky-400/60 text-sky-300 shadow-[0_0_20px_rgba(56,189,248,0.3)]'
                  : isDisconnected
                  ? 'avatar-disconnected bg-gradient-to-br from-amber-500/25 via-amber-600/35 to-orange-500/25 border-2 border-amber-400/60 text-amber-300'
                  : 'avatar-idle bg-white/[0.05] border border-white/15 text-white/80'
              )}
            >
              {isCustomAvatar && !imgError ? (
                <img
                  src={avatarUrl}
                  alt={displayLordName}
                  className="rounded-2xl w-full h-full object-cover select-none"
                  onError={() => setImgError(true)}
                  loading="lazy"
                />
              ) : (
                displayLordName[0]?.toUpperCase() || '🏰'
              )}
            </div>
          </div>

          {/* Main Titles and Meta Badges */}
          <div className="flex-1 min-w-0">
            {/* Row 1: Name, Alliance, Status Badge */}
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              <span className="font-bold text-white text-sm sm:text-base truncate tracking-wide castle-lord-name">
                {displayLordName}
              </span>

              {info.alliance_name && (
                <span className="bg-primary-500/15 px-1.5 sm:px-2 py-0.5 border border-primary-500/30 rounded-md font-semibold text-[10px] text-primary-300 sm:text-xs castle-alliance-badge">
                  [{info.alliance_name.split(' ')[0]}]
                </span>
              )}

              {info.vip_level > 0 && (
                <span className="flex items-center gap-1 bg-gradient-to-r from-amber-500/20 to-yellow-500/20 px-1.5 py-0.5 border border-amber-500/40 rounded-md font-bold text-[10px] text-amber-300 castle-vip-badge">
                  <Crown size={10} className="text-amber-400" />
                  VIP {info.vip_level}
                </span>
              )}

              {/* Status Badge */}
              {isDeploying ? (
                <span className="flex items-center gap-1.5 bg-amber-500/20 shadow-[0_0_12px_rgba(245,158,11,0.3)] px-2.5 py-0.5 border border-amber-500/50 rounded-full font-bold text-[10px] text-amber-800 dark:text-amber-300 sm:text-xs animate-pulse castle-status-badge status-badge-deploying">
                  <Loader2 size={12} className="text-amber-600 dark:text-amber-400 animate-spin" />
                  <span>{t('accounts.deployingBadge', 'جاري رفع التحديثات...')}</span>
                </span>
              ) : isBanned ? (
                <span className="flex items-center gap-1.5 bg-rose-500/20 shadow-[0_0_12px_rgba(244,63,94,0.3)] px-2.5 py-0.5 border border-rose-500/50 rounded-full font-bold text-[10px] text-rose-300 sm:text-xs castle-status-badge status-badge-banned">
                  <ShieldAlert size={12} className="text-rose-400" />
                  <span>{t('status.banned')}</span>
                </span>
              ) : isExpired ? (
                <span className="flex items-center gap-1.5 bg-rose-500/15 shadow-[0_0_12px_rgba(244,63,94,0.25)] px-2.5 py-0.5 border border-rose-500/40 rounded-full font-bold text-[10px] text-rose-300 sm:text-xs castle-status-badge status-badge-expired">
                  <AlertTriangle size={12} className="text-rose-400" />
                  <span>{t('status.stoppedExpired')}</span>
                </span>
              ) : isError ? (
                <span className="flex items-center gap-1.5 bg-rose-500/20 shadow-[0_0_12px_rgba(244,63,94,0.3)] px-2.5 py-0.5 border border-rose-500/50 rounded-full font-bold text-[10px] text-rose-300 sm:text-xs animate-pulse castle-status-badge status-badge-error">
                  <span className="bg-rose-400 rounded-full w-1.5 h-1.5" />
                  <span>{bot?.conn_message ? t('status.authError', 'خطأ في المصادقة') : t('status.error', 'خطأ')}</span>
                </span>
              ) : isPending || effectiveStatus === 'pending' ? (
                <span className="flex items-center gap-1 bg-amber-500/15 px-2 py-0.5 border border-amber-500/30 rounded-full font-semibold text-[10px] text-amber-400 sm:text-xs castle-status-badge status-badge-pending">
                  <Clock size={11} />
                  <span>{t('status.pending')}</span>
                </span>
              ) : isDisconnected ? (
                <span className="flex items-center gap-1 bg-amber-500/20 px-2 py-0.5 border border-amber-500/50 rounded-full font-bold text-[10px] text-amber-300 sm:text-xs animate-pulse castle-status-badge status-badge-disconnected">
                  <span className="relative flex w-1.5 h-1.5">
                    <span className="inline-flex absolute bg-amber-400 opacity-70 rounded-full w-full h-full animate-ping"></span>
                    <span className="inline-flex relative bg-amber-400 rounded-full w-1.5 h-1.5"></span>
                  </span>
                  <span>{t('status.otherDevice')}</span>
                </span>
              ) : isReconnecting ? (
                <span className="flex items-center gap-1 bg-orange-500/15 px-2 py-0.5 border border-orange-500/35 rounded-full font-semibold text-[10px] text-orange-300 sm:text-xs castle-status-badge status-badge-reconnecting">
                  <span className="bg-orange-400 rounded-full w-1.5 h-1.5 animate-spin" style={{borderRadius:'50%', border:'2px solid transparent', borderTopColor:'#fb923c'}} />
                  <span>{t('status.reconnecting')}</span>
                </span>
              ) : isWaitingCycle ? (
                <span
                  className="flex items-center gap-1.5 bg-sky-500/15 shadow-[0_0_10px_rgba(56,189,248,0.2)] px-2 py-0.5 border border-sky-500/35 rounded-full font-semibold text-[10px] text-sky-300 sm:text-xs castle-status-badge status-badge-waiting"
                  title={bot?.conn_message || t('status.waitingCycle')}
                >
                  <span className="relative flex w-1.5 h-1.5">
                    <span className="inline-flex absolute bg-sky-400 opacity-50 rounded-full w-full h-full animate-ping"></span>
                    <span className="inline-flex relative bg-sky-400 rounded-full w-1.5 h-1.5"></span>
                  </span>
                  <span>
                    {waitingMinutes != null
                      ? t('status.waitingCountdown', { count: waitingMinutes })
                      : t('status.waitingCycle')}
                  </span>
                </span>
              ) : isRunningNow ? (
                <span
                  className="flex items-center gap-1.5 bg-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.35)] px-2.5 py-0.5 border border-emerald-500/50 rounded-full font-bold text-[10px] text-emerald-300 sm:text-xs animate-pulse castle-status-badge status-badge-running"
                  title={bot?.conn_message || t('status.runningNow')}
                >
                  <span className="relative flex w-1.5 h-1.5">
                    <span className="inline-flex absolute bg-emerald-400 opacity-80 rounded-full w-full h-full animate-ping"></span>
                    <span className="inline-flex relative bg-emerald-400 rounded-full w-1.5 h-1.5"></span>
                  </span>
                  <span>{t('status.runningNow')}</span>
                </span>
              ) : (
                <span className="flex items-center gap-1 bg-white/5 px-2 py-0.5 border border-white/10 rounded-full font-medium text-[10px] text-gray-400 sm:text-xs castle-status-badge status-badge-idle">
                  <span className="bg-gray-500 rounded-full w-1.5 h-1.5" />
                  <span>{t('status.idle')}</span>
                </span>
              )}
            </div>

            {/* Row 2: Email */}
            <div className="mt-0.5 font-mono text-[11px] text-gray-400 sm:text-xs truncate select-none castle-email">
              {castle.email}
            </div>

            {/* Error Alert Strip */}
            {isError && (
              <div className="flex items-center gap-1.5 bg-rose-500/15 mt-1.5 px-2.5 py-1 border border-rose-500/35 rounded-lg font-semibold text-[11px] text-rose-200 animate-pulse">
                <AlertTriangle size={13} className="text-rose-400 shrink-0" />
                <span className="truncate" title={bot?.conn_message || bot?.last_error || t('accounts.authFixPrompt', 'خطأ في البريد أو كلمة المرور — اضغط ✏️ للتعديل')}>
                  {bot?.conn_message || bot?.last_error || t('accounts.authFixPrompt', 'خطأ في البريد أو كلمة المرور — اضغط ✏️ للتعديل')}
                </span>
              </div>
            )}

            {/* Row 3: Meta Stat Badges */}
            <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
              {/* Power */}
              <span className="flex items-center gap-1 bg-purple-500/10 px-1.5 sm:px-2 py-0.5 border border-purple-500/25 rounded-md font-semibold text-[10px] text-purple-300 sm:text-[11px] castle-stat-power">
                <Zap size={10} className="text-purple-400" />
                {(info.lord_power / 1_000_000).toFixed(1)}M
              </span>

              {/* Server */}
              <span className="flex items-center gap-1 bg-blue-500/10 px-1.5 sm:px-2 py-0.5 border border-blue-500/25 rounded-md font-semibold text-[10px] text-blue-300 sm:text-[11px] castle-stat-server">
                <Globe size={10} className="text-blue-400" />
                #{info.server_id}
              </span>

              {/* Coordinates */}
              <span className="flex items-center gap-1 bg-cyan-500/10 px-1.5 sm:px-2 py-0.5 border border-cyan-500/25 rounded-md font-semibold text-[10px] text-cyan-300 sm:text-[11px] castle-stat-coords">
                <MapPin size={10} className="text-cyan-400" />
                {info.coordinates.x},{info.coordinates.y}
              </span>
            </div>
          </div>
        </div>

        {/* Right / Actions: on mobile full width with distinct thumb button, on desktop inline */}
        <div className="flex justify-between sm:justify-end items-center gap-2 sm:ms-auto pt-2 sm:pt-0 border-white/6 border-t sm:border-t-0 w-full sm:w-auto">
          {/* Main Start / Stop Button */}
          {isDeploying ? (
            <button
              type="button"
              disabled
              onClick={e => e.stopPropagation()}
              className="flex sm:flex-initial flex-1 justify-center items-center gap-1.5 bg-amber-50 dark:bg-amber-500/10 px-3.5 py-2 sm:py-1.5 border border-amber-300 dark:border-amber-500/30 rounded-xl sm:rounded-lg font-bold text-amber-800 dark:text-amber-300 text-xs cursor-not-allowed select-none btn-deploying"
            >
              <Loader2 size={13} className="text-amber-600 dark:text-amber-400 animate-spin" />
              <span>{t('accounts.updating', 'جاري التحديث...')}</span>
            </button>
          ) : isBanned ? (
            <button
              type="button"
              onClick={handleToggleClick}
              title={t('accounts.bannedTooltip')}
              className="flex sm:flex-initial flex-1 justify-center items-center gap-1.5 bg-rose-500/15 hover:bg-rose-500/25 px-3.5 py-2 sm:py-1.5 border border-rose-500/40 rounded-xl sm:rounded-lg font-bold text-rose-300 text-xs transition-all duration-200 cursor-pointer select-none castle-btn-toggle btn-locked"
            >
              <Lock size={13} className="text-rose-400" />
              <span>{t('accounts.lockedBanned')}</span>
            </button>
          ) : isExpired ? (
            <button
              type="button"
              onClick={handleToggleClick}
              title={t('accounts.expiredTooltip')}
              className="flex sm:flex-initial flex-1 justify-center items-center gap-1.5 bg-rose-500/15 hover:bg-rose-500/25 px-3.5 py-2 sm:py-1.5 border border-rose-500/40 rounded-xl sm:rounded-lg font-bold text-rose-300 text-xs transition-all duration-200 cursor-pointer select-none castle-btn-toggle btn-locked"
            >
              <Lock size={13} className="text-rose-400" />
              <span>{t('accounts.lockedExpired')}</span>
            </button>
          ) : isPending || effectiveStatus === 'pending' ? (
            <span
              onClick={e => e.stopPropagation()}
              className="flex sm:flex-initial flex-1 justify-center items-center gap-1 bg-amber-50 dark:bg-yellow-500/10 px-3 py-2 sm:py-1.5 border border-amber-300 dark:border-yellow-500/30 rounded-xl sm:rounded-lg font-semibold text-amber-800 dark:text-yellow-400 text-xs cursor-not-allowed"
            >
              <Clock size={13} />
              {t('status.pending')}
            </span>
          ) : (
            <button
              onClick={handleToggleClick}
              disabled={isStoppingActive || isStartingActive}
              style={!isBotActive && !isStoppingActive && !isStartingActive ? { backgroundColor: 'var(--theme-primary)', color: '#ffffff' } : {}}
              className={clsx(
                'flex sm:flex-initial flex-1 justify-center items-center gap-1.5 px-3.5 py-2 sm:py-1.5 rounded-xl sm:rounded-lg font-bold text-xs transition-colors cursor-pointer select-none castle-btn-toggle',
                isStoppingActive
                  ? 'btn-stopping bg-slate-100 dark:bg-gray-800 border border-slate-300 dark:border-gray-700 text-slate-700 dark:text-gray-400 cursor-not-allowed'
                  : isStartingActive
                  ? 'btn-starting bg-emerald-50 dark:bg-gray-800 border border-emerald-300 dark:border-gray-700 text-emerald-800 dark:text-gray-300 cursor-not-allowed'
                  : isBotActive
                  ? 'btn-stop-bot bg-rose-600 hover:bg-rose-700 text-white'
                  : 'btn-start-bot text-white hover:opacity-90'
              )}
            >
              {isStoppingActive ? (
                <>
                  <Loader2 size={13} className="text-slate-500 dark:text-gray-300 animate-spin stopping-spinner" />
                  <span className="stopping-text">{t('status.stopping', 'جاري الإيقاف...')}</span>
                </>
              ) : isStartingActive ? (
                <>
                  <Loader2 size={13} className="text-emerald-600 dark:text-emerald-400 animate-spin starting-spinner" />
                  <span className="starting-text">{t('status.starting', 'جاري التشغيل...')}</span>
                </>
              ) : isBotActive ? (
                <>
                  <Square size={13} className="fill-white text-white" />
                  <span>{t('accounts.stopBot')}</span>
                </>
              ) : (
                <>
                  <Play size={13} className="fill-white text-white" />
                  <span>{t('accounts.startBot')}</span>
                </>
              )}
            </button>
          )}

          {/* Icon Controls Group */}
          <div
            onClick={e => e.stopPropagation()}
            className="castle-icon-group flex items-center gap-0.5 bg-white/[0.04] p-1 sm:p-0.5 border border-white/8 rounded-xl sm:rounded-lg shrink-0"
          >
            {/* Fixed Preset Settings */}
            {!isPending && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setShowPresetModal(true) }}
                disabled={isApplyingPreset}
                title={t('accounts.fixedPresetTooltip')}
                className="hover:bg-amber-500/15 disabled:opacity-50 p-2 sm:p-1.5 rounded-lg sm:rounded-md text-amber-500 hover:text-amber-400 transition-colors cursor-pointer castle-action-btn castle-action-btn-preset"
              >
                <Sparkles size={15} className={isApplyingPreset ? 'animate-spin text-amber-400' : 'text-amber-500'} />
              </button>
            )}

            {/* Edit credentials */}
            {onEdit && (
              <button
                onClick={(e) => { e.stopPropagation(); onEdit(castle) }}
                className="hover:bg-white/8 p-2 sm:p-1.5 rounded-lg sm:rounded-md text-gray-400 hover:text-white transition-colors cursor-pointer castle-action-btn"
                title={t('accounts.editCredentials')}
              >
                <Edit2 size={15} />
              </button>
            )}

            {/* Delete Account */}
            {onDelete && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(castle.id, castle.is_active) }}
                className="hover:bg-rose-500/10 p-2 sm:p-1.5 rounded-lg sm:rounded-md text-gray-500 hover:text-rose-400 transition-colors cursor-pointer castle-action-btn castle-action-btn-delete"
                title={t('accounts.confirmDelete')}
              >
                <Trash2 size={15} />
              </button>
            )}

            {/* Expand / Accordion toggle */}
            <button
              type="button"
              onClick={handleToggleExpand}
              className={clsx(
                'p-2 sm:p-1.5 rounded-lg sm:rounded-md transition-colors cursor-pointer castle-action-btn castle-action-btn-expand',
                expanded
                  ? 'text-primary-400 bg-primary-500/15'
                  : 'text-gray-400 hover:text-white hover:bg-white/8'
              )}
              title={expanded ? t('accounts.hideSettings') : t('accounts.showSettings')}
            >
              {expanded ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
            </button>
          </div>
        </div>
      </div>

      {/* ── Resources Row ─────────────────────────────────── */}
      <div
        className="bg-white/[0.01] px-4 sm:px-5 pt-3 pb-3.5 border-white/8 border-t select-none castle-resources-row"
      >
        <ResourceBar resources={resources} />
        {bot.last_error && (
          <div className="flex items-center gap-2 mt-2 text-rose-400 text-xs">
            <span className="max-w-full truncate" title={bot.last_error}>
              ⚠ {bot.last_error}
            </span>
          </div>
        )}
      </div>

      {/* ── Expanded Task Settings Accordion (Instant & Fast) ── */}
      {hasBeenExpanded && (
        <div
          className={clsx(
            'border-white/8 border-t w-full castle-expanded-section',
            expanded ? 'block' : 'hidden'
          )}
          onClick={e => e.stopPropagation()}
        >
          <div className="space-y-5 p-4 md:p-6 w-full">
            <div className="w-full">
              <TaskTabContent
                castle={castle}
                userId={userId}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm Preset Modal ───────────────────────────── */}
      <ConfirmPresetModal
        isOpen={showPresetModal}
        onClose={() => setShowPresetModal(false)}
        onConfirm={handleConfirmPreset}
        lordName={displayLordName}
        email={castle.email}
        isPending={isApplyingPreset}
      />

      {/* ── Confirm Stop Modal ─────────────────────────────── */}
      <ConfirmStopModal
        isOpen={showStopModal}
        onClose={() => setShowStopModal(false)}
        onConfirm={handleConfirmStop}
        lordName={displayLordName}
        email={castle.email}
        isPending={botControl.isPending}
      />
    </div>
  )
}

export default CastleCard
