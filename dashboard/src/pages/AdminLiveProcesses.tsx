import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Activity, RefreshCw, Search, Shield, AlertTriangle,
  Play, Pause, Clock, Cpu, User, CheckCircle2,
  StopCircle, ArrowRight, Radio, Eye, ChevronLeft, ChevronRight
} from 'lucide-react'
import { clsx } from 'clsx'
import { AdminLayout } from '../components/layout/AdminLayout'
import { getAdminLiveProcesses, stopBot, type LiveProcessInfo, type LiveProcessesResponse } from '../lib/botApi'
import { useAuth } from '../hooks/useAuth'
import { useDebounce } from '../hooks/useDebounce'
import toast from 'react-hot-toast'
import { ActionConfirmModal } from '../components/common/ActionConfirmModal'

export function AdminLiveProcessesView({ isActive = true }: { isActive?: boolean }) {
  const { t } = useTranslation()
  const { firebaseUser, isSuperAdmin } = useAuth()
  const [data, setData] = useState<LiveProcessesResponse | null>(null)

  const [loading, setLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery, 300)
  const [activeFilter, setActiveFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const [stoppingIds, setStoppingIds] = useState<Set<string>>(new Set())
  const [confirmStopTarget, setConfirmStopTarget] = useState<{ castleId: string; targetName: string } | null>(null)

  const timerRef = useRef<any>(null)

  // Reset to page 1 whenever debounced search or filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearchQuery, activeFilter, pageSize])

  const fetchProcesses = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true)
    try {
      const res = await getAdminLiveProcesses({
        page: currentPage,
        page_size: pageSize,
        search: debouncedSearchQuery,
        status: activeFilter,
      })
      setData(res)
    } catch (err: any) {
      if (isManual) {
        toast.error(t('admin.live.fetchError', { message: err?.message || t('common.error') }))
      }
    } finally {
      setLoading(false)
      if (isManual) setIsRefreshing(false)
    }
  }, [currentPage, pageSize, debouncedSearchQuery, activeFilter, t])

  // Fetch when page, search, or filter changes
  useEffect(() => {
    fetchProcesses(false)
  }, [fetchProcesses])

  // Auto-refresh timer only ticks when tab is actively visible and autoRefresh is ON
  useEffect(() => {
    if (!isActive || !autoRefresh) {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }

    timerRef.current = setInterval(() => {
      fetchProcesses(false)
    }, 5000)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isActive, autoRefresh, fetchProcesses])

  const handleStopProcess = (castleId: string, email: string) => {
    const targetName = email || castleId
    setConfirmStopTarget({ castleId, targetName })
  }

  const executeStopProcess = async () => {
    if (!confirmStopTarget) return
    const { castleId, targetName } = confirmStopTarget

    setStoppingIds(prev => new Set(prev).add(castleId))
    try {
      await stopBot(castleId)
      toast.success(t('admin.live.stopSuccess', { target: targetName }))
      setConfirmStopTarget(null)
      await fetchProcesses(false)
    } catch (err: any) {
      toast.error(t('admin.live.stopError', { error: err?.message || t('common.error') }))
    } finally {
      setStoppingIds(prev => {
        const next = new Set(prev)
        next.delete(castleId)
        return next
      })
    }
  }

  // Format uptime in friendly localized string
  const formatUptime = (sec: number) => {
    if (!sec || sec < 0) return `0 ${t('common.seconds', 'ث')}`
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    if (h > 0) return `${h} ${t('common.hours', 'س')} ${m} ${t('common.minutes', 'د')}`
    if (m > 0) return `${m} ${t('common.minutes', 'د')} ${s} ${t('common.seconds', 'ث')}`
    return `${s} ${t('common.seconds', 'ث')}`
  }

  const summary = data?.summary || {
    total_active: 0,
    running: 0,
    waiting_next_cycle: 0,
    other_device_login: 0,
    reconnecting: 0,
    waiting_relogin: 0,
    starting: 0,
    stalled: 0,
  }

  const totalActive = summary.total_active ?? data?.total_active ?? 0
  const runningCount = summary.running ?? summary.Running ?? 0
  const waitingCount = summary.waiting_next_cycle ?? summary['Waiting for Next Cycle'] ?? summary.waiting ?? 0
  const otherLoginCount = summary.other_device_login ?? summary['Other Device Login'] ?? summary.other_login ?? 0
  const reconnectingCount = summary.reconnecting ?? summary.Reconnecting ?? 0
  const waitingReloginCount = summary.waiting_relogin ?? summary['Waiting for Re-login'] ?? 0
  const startingCount = summary.starting ?? summary.Starting ?? 0
  const stalledCount = summary.stalled ?? summary.stalled_count ?? 0

  const processes = data?.processes || []
  const totalItems = data?.total_count ?? totalActive
  const totalPages = data?.total_pages ?? Math.max(1, Math.ceil(totalItems / pageSize))
  const validPage = Math.min(currentPage, totalPages)
  const startIndex = (validPage - 1) * pageSize
  const endIndex = Math.min(startIndex + processes.length, totalItems)

  const filterTabs = [
    { id: 'all', label: 'الكل', count: totalActive },
    { id: 'running', label: 'شغال', count: runningCount },
    { id: 'waiting_next_cycle', label: 'انتظار دورة', count: waitingCount },
    { id: 'other_device_login', label: 'دخول آخر', count: otherLoginCount },
    { id: 'reconnecting', label: 'إعادة اتصال', count: reconnectingCount },
    { id: 'waiting_relogin', label: 'انتظار دخول', count: waitingReloginCount },
    { id: 'starting', label: 'بدء', count: startingCount },
    ...(stalledCount > 0 ? [{ id: 'stalled', label: `معطل (${stalledCount})`, count: stalledCount }] : []),
  ]

  if (!firebaseUser || !isSuperAdmin) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* ── Top Bar: Title + Controls ── */}
      <div className="flex sm:flex-row flex-col justify-between sm:items-center gap-3 pb-2 border-slate-200 dark:border-white/10 border-b">
        <div className="flex items-center gap-2.5">
          <div className="bg-emerald-500/10 dark:bg-emerald-500/20 p-2 border border-emerald-500/30 rounded-xl text-emerald-600 dark:text-emerald-400">
            <Activity size={20} className={clsx(isRefreshing && 'animate-spin')} />
          </div>
          <div className="flex items-center gap-2">
            <h1 className="font-bold text-slate-900 dark:text-white text-lg sm:text-xl">
              العمليات الحية
            </h1>
            <span className="bg-emerald-500/10 px-2 py-0.5 border border-emerald-500/20 rounded-md font-mono text-emerald-600 dark:text-emerald-400 text-xs">
              {totalActive} نشط
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Auto Refresh Toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 border rounded-xl font-bold text-xs transition-colors cursor-pointer',
              autoRefresh
                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                : 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-gray-400 border-slate-200 dark:border-white/10'
            )}
            title="تحديث تلقائي"
          >
            <Radio size={13} className={autoRefresh ? 'animate-pulse text-emerald-500' : ''} />
            <span>تلقائي</span>
          </button>

          {/* Manual Refresh Button */}
          <button
            onClick={() => fetchProcesses(true)}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 disabled:opacity-50 px-3 py-1.5 border border-slate-200 dark:border-white/10 rounded-xl font-bold text-slate-700 dark:text-gray-200 text-xs transition-all cursor-pointer"
          >
            <RefreshCw size={13} className={isRefreshing ? 'animate-spin text-emerald-500' : ''} />
            <span>تحديث</span>
          </button>
        </div>
      </div>

      {/* ── Summary Counters (Fast Cards) ── */}
      <div className="gap-2.5 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7">
        {/* Total Active */}
        <div
          onClick={() => setActiveFilter('all')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'all'
              ? 'bg-slate-100 text-slate-900 dark:bg-white/10 dark:text-white border-slate-300 dark:border-white/30 shadow-xs'
              : 'bg-white dark:bg-[#0c1410] border-slate-200 dark:border-white/10 hover:border-slate-300'
          )}
        >
          <div className="flex justify-between items-center text-slate-500 dark:text-slate-400">
            <span className="font-semibold text-xs">الكل</span>
            <Cpu size={14} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{totalActive}</div>
        </div>

        {/* Running Now */}
        <div
          onClick={() => setActiveFilter('running')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'running'
              ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/40 shadow-xs font-bold'
              : 'bg-white dark:bg-[#0c1410] border-emerald-500/20 text-emerald-600 dark:text-emerald-400 hover:border-emerald-500/40'
          )}
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold text-xs">شغال</span>
            <Play size={13} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{runningCount}</div>
        </div>

        {/* Waiting for Next Loop */}
        <div
          onClick={() => setActiveFilter('waiting_next_cycle')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'waiting_next_cycle'
              ? 'bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/40 shadow-xs font-bold'
              : 'bg-white dark:bg-[#0c1410] border-amber-500/20 text-amber-600 dark:text-amber-400 hover:border-amber-500/40'
          )}
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold text-xs">انتظار دورة</span>
            <Clock size={13} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{waitingCount}</div>
        </div>

        {/* Other Device Login */}
        <div
          onClick={() => setActiveFilter('other_device_login')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'other_device_login'
              ? 'bg-rose-500/20 text-rose-700 dark:text-rose-300 border-rose-500/40 shadow-xs font-bold'
              : 'bg-white dark:bg-[#0c1410] border-rose-500/20 text-rose-600 dark:text-rose-400 hover:border-rose-500/40'
          )}
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold text-xs">دخول آخر</span>
            <AlertTriangle size={13} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{otherLoginCount}</div>
        </div>

        {/* Reconnecting */}
        <div
          onClick={() => setActiveFilter('reconnecting')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'reconnecting'
              ? 'bg-blue-500/20 text-blue-700 dark:text-blue-300 border-blue-500/40 shadow-xs font-bold'
              : 'bg-white dark:bg-[#0c1410] border-blue-500/20 text-blue-600 dark:text-blue-400 hover:border-blue-500/40'
          )}
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold text-xs">إعادة اتصال</span>
            <RefreshCw size={13} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{reconnectingCount}</div>
        </div>

        {/* Waiting for Re-login */}
        <div
          onClick={() => setActiveFilter('waiting_relogin')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'waiting_relogin'
              ? 'bg-purple-500/20 text-purple-700 dark:text-purple-300 border-purple-500/40 shadow-xs font-bold'
              : 'bg-white dark:bg-[#0c1410] border-purple-500/20 text-purple-600 dark:text-purple-400 hover:border-purple-500/40'
          )}
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold text-xs">انتظار دخول</span>
            <User size={13} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{waitingReloginCount}</div>
        </div>

        {/* Starting */}
        <div
          onClick={() => setActiveFilter('starting')}
          className={clsx(
            'p-3 border rounded-xl transition-all cursor-pointer select-none',
            activeFilter === 'starting'
              ? 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border-cyan-500/40 shadow-xs font-bold'
              : 'bg-white dark:bg-[#0c1410] border-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:border-cyan-500/40'
          )}
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold text-xs">بدء</span>
            <Activity size={13} />
          </div>
          <div className="mt-1 font-mono font-bold text-lg">{startingCount}</div>
        </div>
      </div>

      {/* ── Search Bar & Filter Tabs ── */}
      <div className="flex sm:flex-row flex-col items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search size={16} className="top-1/2 absolute text-slate-400 -translate-y-1/2 start-3.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="بحث بالبريد، معرف القلعة، أو المستخدم..."
            className="bg-white dark:bg-[#0c1410] py-2.5 ps-10 pe-4 border border-slate-200 focus:border-emerald-500/50 dark:border-white/10 rounded-xl focus:outline-none w-full text-slate-900 dark:text-white placeholder:text-slate-400 text-xs"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 pb-1 sm:pb-0 w-full sm:w-auto overflow-x-auto">
          {filterTabs.map(f => (
            <button
              key={f.id}
              onClick={() => setActiveFilter(f.id)}
              className={clsx(
                'px-3 py-1.5 rounded-lg font-bold text-xs whitespace-nowrap transition-colors cursor-pointer',
                activeFilter === f.id
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-gray-400 hover:text-slate-900 dark:hover:text-white'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Process List ── */}
      {loading && !data ? (
        <div className="flex flex-col justify-center items-center gap-3 py-20 text-emerald-600 dark:text-emerald-400">
          <div className="border-2 border-emerald-500/30 border-t-emerald-500 rounded-full w-8 h-8 animate-spin" />
          <span className="font-mono text-xs">{t('admin.live.loadingThreads', 'جاري جلب العمليات الحية...')}</span>
        </div>
      ) : processes.length === 0 ? (
        <div className="bg-white dark:bg-[#0c1410] p-8 py-16 border border-slate-200 dark:border-white/10 rounded-2xl text-center">
          <Activity size={36} className="mx-auto mb-3 text-slate-300 dark:text-white/20" />
          <h3 className="font-bold text-slate-800 dark:text-white text-sm">{t('admin.live.noMatchTitle', 'لا توجد عمليات حية')}</h3>
          <p className="mt-1 text-slate-500 dark:text-gray-400 text-xs">
            {totalActive === 0
              ? t('admin.live.emptyProcesses', 'لا توجد أي عمليات بوت قيد التشغيل حالياً.')
              : t('admin.live.tryChangeFilter', 'جرب تغيير شروط البحث أو التصفية')}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="gap-3 grid grid-cols-1">
            {processes.map((proc, idx) => {
              const isStopping = stoppingIds.has(proc.castle_id)
              const isOtherLogin = proc.live_category === 'other_device_login' || proc.live_category === 'other_login'
              const isWaiting = proc.live_category === 'waiting_next_cycle' || proc.live_category === 'waiting'
              const isRunning = proc.live_category === 'running'
              const isReconnecting = proc.live_category === 'reconnecting'
              const isWaitingRelogin = proc.live_category === 'waiting_relogin'
              const isStarting = proc.live_category === 'starting'
              const isStalled = proc.live_category === 'stalled' || proc.is_stalled

              return (
                <div
                  key={proc.castle_id || proc.thread_id || idx}
                  className={clsx(
                    'bg-white dark:bg-[#0c1410] shadow-xs p-4 border rounded-xl transition-all',
                    isOtherLogin
                      ? 'border-rose-400/40 dark:border-rose-500/30'
                      : isWaiting
                      ? 'border-amber-400/30 dark:border-amber-500/20'
                      : isReconnecting
                      ? 'border-blue-400/30 dark:border-blue-500/20'
                      : isWaitingRelogin
                      ? 'border-purple-400/30 dark:border-purple-500/20'
                      : isStarting
                      ? 'border-cyan-400/30 dark:border-cyan-500/20'
                      : isStalled
                      ? 'border-red-400/50 dark:border-red-500/40 bg-red-50/10'
                      : 'border-emerald-500/25 dark:border-emerald-500/20'
                  )}
                >
                  <div className="flex sm:flex-row flex-col justify-between sm:items-center gap-3">
                    {/* Left: Email, User, Status Badge */}
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Status Indicator Dot */}
                        <span className="relative flex w-2.5 h-2.5">
                          {isRunning && (
                            <span className="inline-flex absolute bg-emerald-400 opacity-75 rounded-full w-full h-full animate-ping" />
                          )}
                          <span
                            className={clsx(
                              'inline-flex relative rounded-full w-2.5 h-2.5',
                              isRunning
                                ? 'bg-emerald-500'
                                : isWaiting
                                ? 'bg-amber-500'
                                : isOtherLogin
                                ? 'bg-rose-500'
                                : isReconnecting
                                ? 'bg-blue-500'
                                : isWaitingRelogin
                                ? 'bg-purple-500'
                                : isStarting
                                ? 'bg-cyan-500'
                                : isStalled
                                ? 'bg-red-500'
                                : 'bg-slate-400'
                            )}
                          />
                        </span>

                        <span className="font-bold text-slate-900 dark:text-white text-sm select-all">
                          {proc.email || proc.castle_id}
                        </span>

                        {/* Runtime Socket IP Badge */}
                        {(proc.real_ip || proc.proxy_ip) && (
                          <span
                            title={
                              proc.real_ip_type === 'socks5'
                                ? `فحص المقبس الحي: نفق SOCKS5 نشط (الطرف: ${proc.socket_peer || proc.real_ip || proc.proxy_ip}) — بدون تسريب`
                                : `فحص المقبس الحي: اتصال مباشر عبر IP السيرفر (${proc.real_ip && proc.real_ip !== 'direct' ? proc.real_ip : 'مباشر'})`
                            }
                            className={clsx(
                              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-mono border font-bold shadow-2xs select-none",
                              (proc.real_ip_type === "direct" || proc.real_ip === "direct" || proc.proxy_ip === "direct")
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/25"
                                : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/25"
                            )}
                          >
                            {(proc.real_ip_type === "direct" || proc.real_ip === "direct" || proc.proxy_ip === "direct") ? (
                              <>
                                <span className="text-[10px]">🌐</span>
                                <span>{proc.real_ip && proc.real_ip !== 'direct' ? proc.real_ip : 'مباشر (السيرفر)'}</span>
                              </>
                            ) : (
                              <>
                                <span className="text-[10px]">🛡️</span>
                                <span>{proc.real_ip || proc.proxy_ip}</span>
                              </>
                            )}
                          </span>
                        )}

                        {/* Live Category Badge */}
                        <span
                          className={clsx(
                            'px-2 py-0.5 border rounded-md font-bold text-[11px]',
                            isRunning
                              ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                              : isWaiting
                              ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30'
                              : isOtherLogin
                              ? 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30 animate-pulse'
                              : isReconnecting
                              ? 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30'
                              : isWaitingRelogin
                              ? 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/30'
                              : isStarting
                              ? 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-400 border-cyan-500/30'
                              : isStalled
                              ? 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30 font-black'
                              : 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-gray-400 border-slate-200 dark:border-white/10'
                          )}
                        >
                          {proc.category_label || proc.state}
                        </span>

                        {/* Current Task Execution Badge */}
                        {proc.current_step && (
                          <span className="bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-md font-bold text-[11px] inline-flex items-center gap-1">
                            <span>⚡</span>
                            <span>{proc.current_step}</span>
                          </span>
                        )}

                        {/* Next Run Time Badge */}
                        {proc.next_run_time && isWaiting && (
                          <span className="bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-md font-mono text-[11px] inline-flex items-center gap-1">
                            <Clock size={11} />
                            <span>{new Date(proc.next_run_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                          </span>
                        )}

                        {/* Iteration Badge */}
                        {proc.iteration > 0 && (
                          <span className="bg-slate-100 dark:bg-white/5 px-2 py-0.5 border border-slate-200 dark:border-white/10 rounded-md font-mono text-[11px] text-slate-700 dark:text-gray-300">
                            {t('admin.live.iteration', { num: proc.iteration })}
                          </span>
                        )}

                        {/* Thread ID */}
                        {proc.thread_id && (
                          <span className="font-mono text-[10px] text-slate-400 dark:text-gray-500">
                            Thread #{proc.thread_id}
                          </span>
                        )}
                      </div>

                      {/* Owner / Account info */}
                      {(proc.user_email || proc.user_id) && (
                        <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-slate-500 dark:text-gray-400">
                          <User size={12} className="shrink-0" />
                          <span className="font-mono text-slate-700 dark:text-gray-300 select-all">
                            {proc.user_email || proc.user_id}
                          </span>
                          <span className="text-slate-300 dark:text-white/10">•</span>
                          <span className="font-mono text-[10px] text-slate-400 dark:text-gray-500 select-all">
                            ID: {proc.castle_id?.slice(0, 12)}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Right: Runtime Counters + Stop Action */}
                    <div className="flex sm:flex-col justify-between items-center sm:items-end gap-2 pt-2 sm:pt-0 border-slate-100 dark:border-white/5 border-t sm:border-t-0 shrink-0">
                      <div className="text-start sm:text-end">
                        <div className="text-[10px] text-slate-400">{t('admin.live.uptimeLabel', 'مدة التشغيل')}</div>
                        <div className="font-mono font-bold text-slate-800 dark:text-gray-200 text-xs">
                          {formatUptime(proc.uptime_seconds)}
                        </div>
                      </div>

                      {/* Stop Action Button */}
                      <button
                        onClick={() => handleStopProcess(proc.castle_id, proc.email)}
                        disabled={isStopping}
                        className="flex items-center gap-1 bg-rose-50 hover:bg-rose-600 dark:bg-rose-500/10 dark:hover:bg-rose-600 disabled:opacity-50 shadow-xs px-3 py-1.5 border border-rose-200 dark:border-rose-500/30 rounded-lg font-bold text-rose-600 hover:text-white text-xs active:scale-95 transition-all cursor-pointer"
                      >
                        <StopCircle size={14} className={isStopping ? 'animate-spin' : ''} />
                        <span>{isStopping ? t('admin.live.stopping', 'جاري الإيقاف...') : t('admin.live.stopProcess', 'إيقاف')}</span>
                      </button>
                    </div>
                  </div>

                  {/* Prominent Alert Box for other device login */}
                  {isOtherLogin && (
                    <div className="flex justify-between items-center gap-2 bg-rose-50 dark:bg-rose-500/10 mt-3 p-2.5 border border-rose-200 dark:border-rose-500/30 rounded-lg text-rose-800 dark:text-rose-300 text-xs">
                      <div className="flex items-center gap-2">
                        <AlertTriangle size={15} className="text-rose-600 dark:text-rose-400 shrink-0" />
                        <span>
                          <strong>{t('admin.live.alertWarning', 'تنبيه:')}</strong>{' '}
                          {proc.last_kick_reason
                            ? t('admin.live.disconnectedReason', { reason: proc.last_kick_reason })
                            : t('admin.live.otherLoginMsg', 'تم تسجيل الدخول من جهاز آخر')}
                        </span>
                      </div>
                      {proc.reconnect_attempt > 0 && (
                        <span className="bg-rose-200/60 dark:bg-rose-500/20 px-2 py-0.5 rounded font-mono font-bold text-[11px] text-rose-900 dark:text-rose-200 shrink-0">
                          {proc.reconnect_attempt} / {proc.max_reconnect_attempts}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* ── True Pagination Controls (matching Admin.tsx) ── */}
          {totalItems > 0 && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 bg-slate-50/75 dark:bg-white/[0.01] border border-slate-200/80 dark:border-white/8 rounded-xl text-xs select-none">
              {/* Left: Range and total count */}
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-mono">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  {totalItems > 0 ? startIndex + 1 : 0}–{endIndex}
                </span>
                <span>/</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {totalItems}
                </span>
                <span>{t('admin.live.processesCount', 'عملية حية')}</span>
              </div>

              {/* Center: Prev / Next / Page Numbers */}
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  id="live-pagination-prev"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={validPage <= 1}
                  className="flex items-center justify-center w-8 h-8 rounded-lg border border-slate-200/80 dark:border-white/10 bg-white dark:bg-white/5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
                  title={t('common.prev', 'السابق')}
                >
                  <ChevronRight size={15} className="rtl:rotate-0 rotate-180" />
                </button>

                <div className="flex items-center px-2 py-1 font-mono font-bold text-slate-700 dark:text-slate-300 text-xs">
                  <span>{validPage}</span>
                  <span className="mx-1 text-slate-400">/</span>
                  <span>{totalPages}</span>
                </div>

                <button
                  type="button"
                  id="live-pagination-next"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={validPage >= totalPages}
                  className="flex items-center justify-center w-8 h-8 rounded-lg border border-slate-200/80 dark:border-white/10 bg-white dark:bg-white/5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
                  title={t('common.next', 'التالي')}
                >
                  <ChevronLeft size={15} className="rtl:rotate-0 rotate-180" />
                </button>
              </div>

              {/* Right: Page Size Selector */}
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 text-[11px] font-mono">{t('common.pageSize', 'عرض:')}</span>
                {[10, 25, 50, 100].map(sz => (
                  <button
                    key={sz}
                    type="button"
                    onClick={() => { setPageSize(sz); setCurrentPage(1); }}
                    className={`px-2 py-1 rounded-md text-xs font-mono font-semibold transition cursor-pointer ${
                      pageSize === sz
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'bg-white dark:bg-white/5 border border-slate-200/80 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/10'
                    }`}
                  >
                    {sz}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Non-blocking Confirm Modal */}
      <ActionConfirmModal
        isOpen={!!confirmStopTarget}
        onClose={() => setConfirmStopTarget(null)}
        onConfirm={executeStopProcess}
        title={t('admin.live.stopProcess', 'إيقاف العملية')}
        message={t('admin.live.confirmStop', { target: confirmStopTarget?.targetName || '' })}
        confirmText={t('admin.live.stopProcess', 'إيقاف')}
        variant="danger"
        detail={confirmStopTarget?.targetName}
        isPending={!!confirmStopTarget && stoppingIds.has(confirmStopTarget.castleId)}
      />
    </div>
  )
}

export function AdminLiveProcessesPage() {
  const { t } = useTranslation()
  return (
    <AdminLayout title={t('admin.live.title', 'العمليات الحية')}>
      <AdminLiveProcessesView isActive={true} />
    </AdminLayout>
  )
}
