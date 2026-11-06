import React, { useState, useEffect } from 'react'
import { AdminLayout } from '../components/layout/AdminLayout'
import {
  ShieldCheck, Globe, RefreshCw, Zap, CheckCircle2,
  XCircle, Users, Copy, Server, ChevronDown, ChevronUp, Lock,
  ArrowRightLeft, Check
} from 'lucide-react'
import { clsx } from 'clsx'
import { getAdminProxies, testAdminProxy, toggleAdminNetworkMode, type ProxyCardInfo } from '../lib/botApi'
import toast from 'react-hot-toast'

export function AdminProxiesPage() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [proxies, setProxies] = useState<ProxyCardInfo[]>([])
  const [totalCastles, setTotalCastles] = useState(0)
  const [totalUsers, setTotalUsers] = useState(0)
  const [networkMode, setNetworkMode] = useState<'socks5' | 'direct'>('socks5')
  const [testingIp, setTestingIp] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; ping?: number; msg: string }>>({})
  const [expandedIps, setExpandedIps] = useState<Set<string>>(new Set())

  // Toggle Modal State
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [targetMode, setTargetMode] = useState<'socks5' | 'direct' | null>(null)
  const [serverIp, setServerIp] = useState<string>('')
  const [isToggling, setIsToggling] = useState(false)

  const fetchProxies = async (isManual = false) => {
    if (isManual) setRefreshing(true)
    try {
      const data = await getAdminProxies()
      setProxies(data.proxies_list || [])
      setTotalCastles(data.total_bound_castles || 0)
      setTotalUsers(data.total_bound_users || 0)
      if (data.server_ip) setServerIp(data.server_ip)
      if (data.network_mode) {
        setNetworkMode(data.network_mode)
      } else if (data.enabled !== undefined) {
        setNetworkMode(data.enabled ? 'socks5' : 'direct')
      }
    } catch (e: any) {
      toast.error('تعذر جلب بيانات البروكسيات من السيرفر')
    } finally {
      setLoading(false)
      if (isManual) setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchProxies()
  }, [])

  const handleTestProxy = async (proxyUrl: string, ip: string) => {
    setTestingIp(ip)
    try {
      const result = await testAdminProxy(proxyUrl)
      setTestResults(prev => ({ ...prev, [ip]: result }))
      if (result.ok) {
        toast.success(`✓ الـ IP (${ip}) متصل ومؤمن بنجاح (${result.ping}ms)`)
      } else {
        toast.error(`❌ تعذر الاتصال بالـ IP: ${result.msg}`)
      }
    } catch (err: any) {
      setTestResults(prev => ({ ...prev, [ip]: { ok: false, msg: 'فشل الفحص' } }))
      toast.error('حدث خطأ أثناء فحص البروكسي')
    } finally {
      setTestingIp(null)
    }
  }

  const handleConfirmToggle = async () => {
    if (!targetMode) return
    setIsToggling(true)
    try {
      const res = await toggleAdminNetworkMode(targetMode)
      setNetworkMode(targetMode)
      setShowConfirmModal(false)
      toast.success(res.message || 'تم تحديث نمط الشبكة بنجاح')
      fetchProxies()
    } catch (err: any) {
      toast.error(err.message || 'فشل تحديث نمط الشبكة')
    } finally {
      setIsToggling(false)
    }
  }

  const toggleExpand = (ip: string) => {
    setExpandedIps(prev => {
      const next = new Set(prev)
      if (next.has(ip)) next.delete(ip)
      else next.add(ip)
      return next
    })
  }

  return (
    <AdminLayout title="البروكسيات والشبكة">
      <div className="space-y-4 max-w-7xl mx-auto px-2 sm:px-4 py-4" dir="rtl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white dark:bg-[#0c140f] p-4 sm:p-5 rounded-2xl border border-slate-200/80 dark:border-emerald-500/20 shadow-xs">
          <div className="flex items-center gap-3">
            <div className={clsx(
              "p-2.5 rounded-xl border shrink-0 transition-colors",
              networkMode === 'socks5'
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                : "bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400"
            )}>
              {networkMode === 'socks5' ? <ShieldCheck size={22} /> : <Server size={22} />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white">
                  البروكسيات والشبكة
                </h1>
                <span className={clsx(
                  "text-[11px] px-2 py-0.5 rounded-md font-mono font-bold border",
                  networkMode === 'socks5'
                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                )}>
                  {networkMode === 'socks5' ? 'بروكسيات (SOCKS5)' : (serverIp ? `سيرفر مباشر (${serverIp})` : 'سيرفر مباشر')}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            {/* Mode Switcher */}
            <div className="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 text-xs">
              <button
                onClick={() => {
                  if (networkMode !== 'socks5') {
                    setTargetMode('socks5')
                    setShowConfirmModal(true)
                  }
                }}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer",
                  networkMode === 'socks5'
                    ? "bg-white dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 shadow-xs border border-slate-200/60 dark:border-emerald-500/30"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                )}
              >
                <ShieldCheck size={14} />
                <span>بروكسيات</span>
              </button>

              <button
                onClick={() => {
                  if (networkMode !== 'direct') {
                    setTargetMode('direct')
                    setShowConfirmModal(true)
                  }
                }}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer",
                  networkMode === 'direct'
                    ? "bg-white dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 shadow-xs border border-slate-200/60 dark:border-amber-500/30"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                )}
              >
                <Globe size={14} />
                <span>سيرفر مباشر</span>
              </button>
            </div>

            <button
              onClick={() => fetchProxies(true)}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-white/10 transition cursor-pointer shadow-xs"
            >
              <RefreshCw size={13} className={refreshing ? 'animate-spin text-emerald-500' : ''} />
              <span>تحديث</span>
            </button>
          </div>
        </div>

        {/* Top Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl bg-white dark:bg-[#0c140f] border border-slate-200/80 dark:border-white/10 shadow-xs">
            <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">عناوين IP</div>
            <div className="mt-1 text-xl font-bold text-slate-900 dark:text-white font-mono">{proxies.length}</div>
          </div>

          <div className="p-4 rounded-xl bg-white dark:bg-[#0c140f] border border-slate-200/80 dark:border-white/10 shadow-xs">
            <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">القلاع المربوطة</div>
            <div className="mt-1 text-xl font-bold text-slate-900 dark:text-white font-mono">{totalCastles}</div>
          </div>

          <div className="p-4 rounded-xl bg-white dark:bg-[#0c140f] border border-slate-200/80 dark:border-white/10 shadow-xs">
            <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">المستخدمين</div>
            <div className="mt-1 text-xl font-bold text-slate-900 dark:text-white font-mono">{totalUsers}</div>
          </div>

          <div className="p-4 rounded-xl bg-white dark:bg-[#0c140f] border border-slate-200/80 dark:border-white/10 shadow-xs">
            <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">نمط الشبكة الحالية</div>
            <div className={clsx(
              "mt-1 text-sm font-bold",
              networkMode === 'socks5'
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-amber-600 dark:text-amber-400"
            )}>
              {networkMode === 'socks5' ? 'عزل تام (SOCKS5)' : 'مباشر (IP السيرفر)'}
            </div>
          </div>
        </div>

        {/* Direct Mode Notice */}
        {networkMode === 'direct' && (
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-300 flex items-center gap-2 text-xs font-medium">
            <Globe size={16} className="shrink-0 text-amber-500" />
            <span>اتصالات البوتات تخرج حالياً من IP السيرفر مباشرة. بيانات البروكسيات محفوظة وجاهزة للعودة بأي وقت.</span>
          </div>
        )}

        {/* Confirmation Modal */}
        {showConfirmModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <div className="bg-white dark:bg-[#0c140f] border border-slate-200 dark:border-emerald-500/30 rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4" dir="rtl">
              <div className="flex items-center gap-3">
                <div className={clsx(
                  "p-2.5 rounded-xl border shrink-0",
                  targetMode === 'direct'
                    ? "bg-amber-500/10 border-amber-500/20 text-amber-600"
                    : "bg-emerald-500/10 border-emerald-500/20 text-emerald-600"
                )}>
                  <ArrowRightLeft size={20} />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white text-base">
                    تأكيد تغيير نمط الاتصال
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    التحويل إلى: <span className="font-bold text-slate-800 dark:text-white">
                      {targetMode === 'direct' ? (serverIp ? `🌐 IP السيرفر المباشر (${serverIp})` : '🌐 IP السيرفر المباشر') : '🛡️ بروكسيات SOCKS5'}
                    </span>
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200/60 dark:border-white/5 text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {targetMode === 'direct'
                  ? 'ستتصل البوتات عبر IP السيرفر مباشرة. سيتم تطبيق التغيير تلقائياً مع بدء الدورة القادمة لكل قلعة.'
                  : 'ستتصل البوتات عبر بروكسيات SOCKS5 الموزعة. سيتم تطبيق التغيير تلقائياً مع بدء الدورة القادمة لكل قلعة.'}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowConfirmModal(false)}
                  disabled={isToggling}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 cursor-pointer"
                >
                  إلغاء
                </button>
                <button
                  onClick={handleConfirmToggle}
                  disabled={isToggling}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs cursor-pointer disabled:opacity-50"
                >
                  {isToggling ? <RefreshCw size={13} className="animate-spin" /> : <Check size={14} />}
                  <span>تأكيد التبديل</span>
                </button>
              </div>
            </div>
          </div>
        )}


        {/* Loading Indicator */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-emerald-500">
            <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
            <span className="text-xs font-medium">جاري التحميل...</span>
          </div>
        )}

        {/* Proxy Cards Grid */}
        {!loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {proxies.map((p) => {
              const test = testResults[p.ip]
              const isTesting = testingIp === p.ip
              const isExpanded = expandedIps.has(p.ip)
              const count = p.assigned_castles?.length || 0

              return (
                <div
                  key={p.ip}
                  className="rounded-2xl p-4 sm:p-5 bg-white dark:bg-[#0a110d] border border-slate-200/80 dark:border-white/10 hover:border-emerald-500/30 transition-all shadow-xs flex flex-col justify-between"
                >
                  <div>
                    {/* Top IP Header */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-1.5 font-mono font-bold text-sm text-slate-900 dark:text-white truncate">
                        <span>🌐 {p.ip}</span>
                        <span className="text-xs text-slate-400 font-normal">:{p.port}</span>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded-md bg-slate-100 dark:bg-white/5 border border-slate-200/60 dark:border-white/10 text-slate-600 dark:text-slate-300 shrink-0">
                        {p.country}
                      </span>
                    </div>

                    {/* Castles count badge & progress bar */}
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200/60 dark:border-white/5 mb-3">
                      <div className="flex items-center justify-between mb-1.5 text-xs">
                        <span className="text-slate-500 dark:text-slate-400 font-medium">القلاع:</span>
                        <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                          {count}
                        </span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-200 dark:bg-white/10 overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 transition-all rounded-full"
                          style={{ width: `${Math.min(100, (count / 50) * 100)}%` }}
                        />
                      </div>
                    </div>

                    {/* Test Result Indicator */}
                    {test && (
                      <div
                        className={`p-2.5 rounded-xl text-xs mb-3 flex items-center gap-2 ${
                          test.ok
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
                        }`}
                      >
                        {test.ok ? <CheckCircle2 size={15} className="shrink-0" /> : <XCircle size={15} className="shrink-0" />}
                        <span className="truncate">{test.msg} {test.ping ? `(${test.ping}ms)` : ''}</span>
                      </div>
                    )}

                    {/* Expandable Castles List */}
                    {count > 0 && (
                      <div className="mb-3">
                        <button
                          onClick={() => toggleExpand(p.ip)}
                          className="w-full flex items-center justify-between text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white py-1 cursor-pointer transition-colors"
                        >
                          <span>القلاع ({count})</span>
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                        {isExpanded && (
                          <div className="mt-1.5 max-h-36 overflow-y-auto space-y-1 p-2 rounded-xl bg-slate-50 dark:bg-black/20 border border-slate-200/50 dark:border-white/5 text-[11px] font-mono text-slate-600 dark:text-slate-300">
                            {p.assigned_castles.map((em, i) => (
                              <div key={i} className="truncate py-0.5 border-b border-slate-200/30 dark:border-white/5 last:border-none">
                                • {em}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Card Action Button: Test IP */}
                  <button
                    onClick={() => handleTestProxy(p.full_url, p.ip)}
                    disabled={isTesting}
                    className="w-full flex items-center justify-center gap-1.5 py-2 text-xs font-bold rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 transition-all cursor-pointer shadow-xs active:scale-98 disabled:opacity-50"
                  >
                    {isTesting ? (
                      <>
                        <RefreshCw size={13} className="animate-spin text-emerald-500" />
                        <span>جاري الفحص...</span>
                      </>
                    ) : (
                      <>
                        <Zap size={13} />
                        <span>فحص الاتصال</span>
                      </>
                    )}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </AdminLayout>
  )
}
export default AdminProxiesPage
