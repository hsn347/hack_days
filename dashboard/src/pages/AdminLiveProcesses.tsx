import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Link, Navigate } from 'react-router-dom'
import {
  Activity, RefreshCw, Search, Shield, AlertTriangle,
  Play, Pause, Clock, Cpu, User, CheckCircle2,
  StopCircle, ArrowRight, Radio, Eye
} from 'lucide-react'
import { clsx } from 'clsx'
import { AdminLayout } from '../components/layout/AdminLayout'
import { getAdminLiveProcesses, stopBot, type LiveProcessInfo, type LiveProcessesResponse } from '../lib/botApi'
import { useAuth } from '../hooks/useAuth'
import toast from 'react-hot-toast'

export function AdminLiveProcessesView({ isActive = true }: { isActive?: boolean }) {
  const { firebaseUser, isAdmin } = useAuth()
  const adminEmail = (firebaseUser?.email || '').trim().toLowerCase()
  if (!firebaseUser || adminEmail !== 'ibraboths@gmail.com' || !isAdmin) {
    return <Navigate to="/dashboard" replace />
  }
  const [data, setData] = useState<LiveProcessesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState<'all' | 'running' | 'waiting' | 'other_login' | 'reconnecting'>('all')
  const [stoppingIds, setStoppingIds] = useState<Set<string>>(new Set())

  const timerRef = useRef<any>(null)

  const fetchProcesses = async (isManual = false) => {
    if (isManual) setIsRefreshing(true)
    try {
      const res = await getAdminLiveProcesses()
      setData(res)
    } catch (err: any) {
      if (isManual) {
        toast.error('تعذر جلب العمليات الحية: ' + (err?.message || 'خطأ في الاتصال'))
      }
    } finally {
      setLoading(false)
      if (isManual) setIsRefreshing(false)
    }
  }

  // Pre-fetch immediately on mount
  useEffect(() => {
    fetchProcesses(false)
  }, [])

  // Auto-refresh timer only ticks when tab is actively visible and autoRefresh is ON
  useEffect(() => {
    if (!isActive || !autoRefresh) {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    // Fetch immediately on activation if data was not fetched recently
    fetchProcesses(false)

    timerRef.current = setInterval(() => {
      fetchProcesses(false)
    }, 5000)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isActive, autoRefresh])

  const handleStopProcess = async (castleId: string, email: string) => {
    if (!confirm(`هل أنت متأكد من إيقاف عملية البوت للقلعة:\n${email || castleId}؟`)) {
      return
    }

    setStoppingIds(prev => new Set(prev).add(castleId))
    try {
      await stopBot(castleId)
      toast.success(`تم إيقاف عملية ${email || castleId} بنجاح`)
      await fetchProcesses(false)
    } catch (err: any) {
      toast.error('فشل إيقاف العملية: ' + (err?.message || 'خطأ'))
    } finally {
      setStoppingIds(prev => {
        const next = new Set(prev)
        next.delete(castleId)
        return next
      })
    }
  }

  // Format uptime in friendly Arabic string
  const formatUptime = (sec: number) => {
    if (!sec || sec < 0) return '0 ثانية'
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    if (h > 0) return `${h} س و ${m} د`
    if (m > 0) return `${m} د و ${s} ث`
    return `${s} ثانية`
  }

  // Filtered list
  const filteredProcesses = useMemo(() => {
    if (!data?.processes) return []
    return data.processes.filter(p => {
      // 1. Search Query
      const q = searchQuery.toLowerCase().trim()
      if (q) {
        const matchEmail = (p.email || '').toLowerCase().includes(q)
        const matchCid = (p.castle_id || '').toLowerCase().includes(q)
        const matchUser = (p.user_email || '').toLowerCase().includes(q) || (p.user_id || '').toLowerCase().includes(q)
        if (!matchEmail && !matchCid && !matchUser) return false
      }

      // 2. Filter Category
      if (activeFilter === 'running') return p.live_category === 'running'
      if (activeFilter === 'waiting') return p.live_category === 'waiting'
      if (activeFilter === 'other_login') return p.live_category === 'other_login'
      if (activeFilter === 'reconnecting') return p.live_category === 'reconnecting'

      return true
    })
  }, [data, searchQuery, activeFilter])

  const summary = data?.summary || {
    total_active: 0,
    running: 0,
    waiting: 0,
    other_login: 0,
    reconnecting: 0,
    starting: 0,
  }

  return (
    <div className="space-y-6">
        {/* ── Top Bar: Title + Controls ── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-white/10">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                <Activity size={22} className="animate-pulse" />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                  العمليات الحية بالذاكرة
                  <span className="text-xs font-mono font-normal bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/20">
                    Live Runtime Threads
                  </span>
                </h1>
                <p className="text-xs text-slate-500 dark:text-gray-400 mt-0.5">
                  استعلام مباشر ولحظي من الـ Threads وكائنات التشغيل الفعلية (بدون الرجوع لقاعدة البيانات)
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            {/* Auto Refresh Toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition-colors cursor-pointer',
                autoRefresh
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                  : 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-gray-400 border-slate-200 dark:border-white/10'
              )}
              title="تحديث تلقائي كل 5 ثوانٍ"
            >
              <Radio size={14} className={autoRefresh ? 'animate-pulse text-emerald-500' : ''} />
              <span>تحديث تلقائي (5ث)</span>
            </button>

            {/* Manual Refresh Button */}
            <button
              onClick={() => fetchProcesses(true)}
              disabled={isRefreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-900 dark:bg-white/10 text-white hover:bg-slate-800 dark:hover:bg-white/15 border border-slate-800 dark:border-white/20 transition-all cursor-pointer disabled:opacity-50"
            >
              <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
              <span>تحديث الآن</span>
            </button>

            {/* Back to admin overview */}
            <Link
              to="/admin"
              className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-gray-300 border border-slate-200 dark:border-white/10 transition-colors"
            >
              <span>لوحة الإدارة</span>
              <ArrowRight size={13} />
            </Link>
          </div>
        </div>

        {/* ── Summary Counters (Fast Cards) ── */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {/* Total Active */}
          <div
            onClick={() => setActiveFilter('all')}
            className={clsx(
              'p-3.5 rounded-xl border transition-all cursor-pointer select-none',
              activeFilter === 'all'
                ? 'bg-slate-900 text-white dark:bg-white/10 dark:text-white border-slate-900 dark:border-white/30 shadow-sm'
                : 'bg-white dark:bg-[#0c1410] border-slate-200 dark:border-white/10 hover:border-slate-300 dark:hover:border-white/20'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold opacity-80">إجمالي العمليات</span>
              <Cpu size={16} className="opacity-70" />
            </div>
            <div className="text-2xl font-black mt-1 font-mono">{summary.total_active}</div>
            <div className="text-[10px] opacity-70 mt-0.5">Thread يعمل حالياً</div>
          </div>

          {/* Running Now */}
          <div
            onClick={() => setActiveFilter('running')}
            className={clsx(
              'p-3.5 rounded-xl border transition-all cursor-pointer select-none',
              activeFilter === 'running'
                ? 'bg-emerald-600 text-white dark:bg-emerald-500/25 dark:text-emerald-300 border-emerald-600 dark:border-emerald-500/40 shadow-sm'
                : 'bg-white dark:bg-[#0c1410] border-emerald-500/20 text-emerald-600 dark:text-emerald-400 hover:border-emerald-500/40'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold">شغالة فعلياً</span>
              <Play size={15} />
            </div>
            <div className="text-2xl font-black mt-1 font-mono">{summary.running}</div>
            <div className="text-[10px] opacity-80 mt-0.5">تنفذ مهام الآن</div>
          </div>

          {/* Waiting for Next Loop */}
          <div
            onClick={() => setActiveFilter('waiting')}
            className={clsx(
              'p-3.5 rounded-xl border transition-all cursor-pointer select-none',
              activeFilter === 'waiting'
                ? 'bg-amber-600 text-white dark:bg-amber-500/25 dark:text-amber-300 border-amber-600 dark:border-amber-500/40 shadow-sm'
                : 'bg-white dark:bg-[#0c1410] border-amber-500/20 text-amber-600 dark:text-amber-400 hover:border-amber-500/40'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold">بانتظار الدورة</span>
              <Clock size={15} />
            </div>
            <div className="text-2xl font-black mt-1 font-mono">{summary.waiting}</div>
            <div className="text-[10px] opacity-80 mt-0.5">في استراحة دورية</div>
          </div>

          {/* Other Device Login */}
          <div
            onClick={() => setActiveFilter('other_login')}
            className={clsx(
              'p-3.5 rounded-xl border transition-all cursor-pointer select-none',
              activeFilter === 'other_login'
                ? 'bg-rose-600 text-white dark:bg-rose-500/25 dark:text-rose-300 border-rose-600 dark:border-rose-500/40 shadow-sm'
                : 'bg-white dark:bg-[#0c1410] border-rose-500/20 text-rose-600 dark:text-rose-400 hover:border-rose-500/40'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold">دخول من جهاز آخر</span>
              <AlertTriangle size={15} />
            </div>
            <div className="text-2xl font-black mt-1 font-mono">{summary.other_login}</div>
            <div className="text-[10px] opacity-80 mt-0.5">اللاعب دخل الحساب</div>
          </div>

          {/* Reconnecting */}
          <div
            onClick={() => setActiveFilter('reconnecting')}
            className={clsx(
              'p-3.5 rounded-xl border transition-all cursor-pointer select-none col-span-2 sm:col-span-1',
              activeFilter === 'reconnecting'
                ? 'bg-blue-600 text-white dark:bg-blue-500/25 dark:text-blue-300 border-blue-600 dark:border-blue-500/40 shadow-sm'
                : 'bg-white dark:bg-[#0c1410] border-blue-500/20 text-blue-600 dark:text-blue-400 hover:border-blue-500/40'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold">إعادة الاتصال</span>
              <RefreshCw size={15} />
            </div>
            <div className="text-2xl font-black mt-1 font-mono">{summary.reconnecting}</div>
            <div className="text-[10px] opacity-80 mt-0.5">محاولات الدخول</div>
          </div>
        </div>

        {/* ── Search Bar & Filter Tabs ── */}
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search size={16} className="absolute start-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="البحث بالبريد الإلكتروني، معرف القلعة، أو المالك..."
              className="w-full ps-10 pe-4 py-2.5 rounded-xl bg-white dark:bg-[#0c1410] border border-slate-200 dark:border-white/10 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-emerald-500/50"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
            {[
              { id: 'all', label: 'الكل' },
              { id: 'running', label: 'شغالة' },
              { id: 'waiting', label: 'منتظرة' },
              { id: 'other_login', label: 'دخول آخر' },
              { id: 'reconnecting', label: 'إعادة اتصال' },
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id as any)}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-colors cursor-pointer',
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
          <div className="py-20 flex flex-col items-center justify-center gap-3 text-emerald-600 dark:text-emerald-400">
            <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
            <span className="text-xs font-mono">جاري فحص الـ Threads الحية في السيرفر...</span>
          </div>
        ) : filteredProcesses.length === 0 ? (
          <div className="py-16 text-center bg-white dark:bg-[#0c1410] border border-slate-200 dark:border-white/10 rounded-2xl p-8">
            <Activity size={36} className="mx-auto text-slate-300 dark:text-white/20 mb-3" />
            <h3 className="text-sm font-bold text-slate-800 dark:text-white">لا توجد عمليات تطابق البحث</h3>
            <p className="text-xs text-slate-500 dark:text-gray-400 mt-1">
              {data?.processes?.length === 0
                ? 'لا يوجد أي بوت يعمل في الذاكرة حالياً.'
                : 'جرّب تغيير كلمات البحث أو الفلتر المحدد.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-gray-400 px-1">
              <span>عرض {filteredProcesses.length} من أصل {data?.processes?.length || 0} عملية حية</span>
              <span className="font-mono text-[11px]">مصدر البيانات: الذاكرة المباشرة (Memory Pool)</span>
            </div>

            <div className="grid grid-cols-1 gap-3">
              {filteredProcesses.map((proc, idx) => {
                const isStopping = stoppingIds.has(proc.castle_id)
                const isOtherLogin = proc.live_category === 'other_login'
                const isWaiting = proc.live_category === 'waiting'
                const isRunning = proc.live_category === 'running'
                const isReconnecting = proc.live_category === 'reconnecting'

                return (
                  <div
                    key={proc.castle_id || idx}
                    className={clsx(
                      'p-4 rounded-xl border transition-all bg-white dark:bg-[#0c1410] shadow-xs',
                      isOtherLogin
                        ? 'border-rose-400/40 dark:border-rose-500/30'
                        : isWaiting
                        ? 'border-amber-400/30 dark:border-amber-500/20'
                        : isReconnecting
                        ? 'border-blue-400/30 dark:border-blue-500/20'
                        : 'border-emerald-500/25 dark:border-emerald-500/20'
                    )}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      {/* Left: Email, User, Status Badge */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {/* Status Indicator Dot */}
                          <span className="relative flex h-2.5 w-2.5">
                            {isRunning && (
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                            )}
                            <span
                              className={clsx(
                                'relative inline-flex rounded-full h-2.5 w-2.5',
                                isRunning
                                  ? 'bg-emerald-500'
                                  : isWaiting
                                  ? 'bg-amber-500'
                                  : isOtherLogin
                                  ? 'bg-rose-500'
                                  : isReconnecting
                                  ? 'bg-blue-500'
                                  : 'bg-slate-400'
                              )}
                            />
                          </span>

                          <span className="font-bold text-sm text-slate-900 dark:text-white select-all">
                            {proc.email || proc.castle_id}
                          </span>

                          {/* Live Category Badge */}
                          <span
                            className={clsx(
                              'text-[11px] font-bold px-2 py-0.5 rounded-md border',
                              isRunning
                                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                                : isWaiting
                                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30'
                                : isOtherLogin
                                ? 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30 animate-pulse'
                                : isReconnecting
                                ? 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30'
                                : 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-gray-400 border-slate-200 dark:border-white/10'
                            )}
                          >
                            {proc.category_label || proc.state}
                          </span>

                          {/* Iteration Badge */}
                          {proc.iteration > 0 && (
                            <span className="text-[11px] font-mono bg-slate-100 dark:bg-white/5 text-slate-700 dark:text-gray-300 px-2 py-0.5 rounded-md border border-slate-200 dark:border-white/10">
                              دورة #{proc.iteration}
                            </span>
                          )}

                          {/* Thread ID */}
                          {proc.thread_id && (
                            <span className="text-[10px] font-mono text-slate-400 dark:text-gray-500">
                              Thread #{proc.thread_id}
                            </span>
                          )}
                        </div>



                        {/* Owner / Account info */}
                        {(proc.user_email || proc.user_id) && (
                          <div className="mt-1.5 text-[11px] text-slate-500 dark:text-gray-400 flex items-center gap-1">
                            <User size={12} />
                            <span>المالك:</span>
                            <span className="font-mono text-slate-700 dark:text-gray-300 select-all">
                              {proc.user_email || proc.user_id}
                            </span>
                            <span className="mx-1">•</span>
                            <span>معرف القلعة:</span>
                            <span className="font-mono text-slate-500 dark:text-gray-400 text-[10px] select-all">
                              {proc.castle_id?.slice(0, 16)}...
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Right: Runtime Counters + Stop Action */}
                      <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100 dark:border-white/5">
                        <div className="text-start sm:text-end">
                          <div className="text-[10px] text-slate-400">مدة التشغيل الحية</div>
                          <div className="text-xs font-mono font-bold text-slate-800 dark:text-gray-200">
                            {formatUptime(proc.uptime_seconds)}
                          </div>
                        </div>

                        {/* Stop Action Button */}
                        <button
                          onClick={() => handleStopProcess(proc.castle_id, proc.email)}
                          disabled={isStopping}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold text-rose-600 hover:text-white bg-rose-50 hover:bg-rose-600 dark:bg-rose-500/10 dark:hover:bg-rose-600 border border-rose-200 dark:border-rose-500/30 transition-all cursor-pointer active:scale-95 disabled:opacity-50 shadow-xs"
                          title="إنهاء وإيقاف هذا الـ Thread فوراً"
                        >
                          <StopCircle size={14} className={isStopping ? 'animate-spin' : ''} />
                          <span>{isStopping ? 'جاري الإيقاف...' : 'إيقاف العملية'}</span>
                        </button>
                      </div>
                    </div>

                    {/* Prominent Alert Box for other device login */}
                    {isOtherLogin && (
                      <div className="mt-3 p-2.5 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 flex items-center justify-between gap-2 text-xs text-rose-800 dark:text-rose-300">
                        <div className="flex items-center gap-2">
                          <AlertTriangle size={15} className="shrink-0 text-rose-600 dark:text-rose-400" />
                          <span>
                            <strong>تنبيه:</strong> {proc.last_kick_reason ? `تم فصل الاتصال (${proc.last_kick_reason})` : 'تم تسجيل الدخول للحساب من جهاز آخر، البوت ينتظر لإعادة المحاولة.'}
                          </span>
                        </div>
                        {proc.reconnect_attempt > 0 && (
                          <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-rose-200/60 dark:bg-rose-500/20 text-rose-900 dark:text-rose-200 shrink-0">
                            محاولة {proc.reconnect_attempt} / {proc.max_reconnect_attempts}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
  )
}

export function AdminLiveProcessesPage() {
  return (
    <AdminLayout title="العمليات الحية بالذاكرة">
      <AdminLiveProcessesView isActive={true} />
    </AdminLayout>
  )
}
