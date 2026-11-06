import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Store,
  Users,
  Castle,
  Zap,
  Globe,
  Mail,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
} from 'lucide-react'
import { AdminLayout } from '../components/layout/AdminLayout'
import { getMerchantsOverview, MerchantStats } from '../lib/botApi'

export function AdminMerchantsPage() {
  const { t } = useTranslation()
  const {
    data,
    isLoading,
    isRefetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin-merchants-overview'],
    queryFn: getMerchantsOverview,
    refetchInterval: 15000, // تحديث دوري كل 15 ثانية لمراقبة القلاع الشغالة لحظياً
  })

  const merchants: MerchantStats[] = data?.merchants || []

  // حساب الإجماليات عبر جميع التجار
  const totalMerchants = merchants.length
  const totalUsers = merchants.reduce((sum, m) => sum + (m.total_users || 0), 0)
  const totalCastles = merchants.reduce((sum, m) => sum + (m.total_castles || 0), 0)
  const totalRunningCastles = merchants.reduce((sum, m) => sum + (m.running_castles || 0), 0)

  return (
    <AdminLayout title={t('admin.merchants.title')}>
      <div className="space-y-6">
        {/* ── Page Header ── */}
        <div className="flex justify-between items-center gap-3 bg-white dark:bg-[#0c120f] p-4 sm:p-5 border border-slate-200/80 dark:border-emerald-500/20 rounded-2xl shadow-xs">
          <div className="flex items-center gap-3">
            <div className="flex justify-center items-center bg-emerald-500/10 dark:bg-emerald-500/20 border border-emerald-500/20 rounded-xl w-10 h-10 text-emerald-600 dark:text-emerald-400 shrink-0">
              <Store size={22} />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-slate-900 dark:text-white text-lg sm:text-xl">
                التجار والنطاقات
              </h1>
              <span className="bg-emerald-500/10 px-2 py-0.5 border border-emerald-500/20 rounded-md font-mono font-semibold text-[11px] text-emerald-600 dark:text-emerald-400">
                {totalMerchants} تاجر
              </span>
            </div>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isLoading || isRefetching}
            className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 disabled:opacity-50 shadow-xs px-3 py-1.5 border border-slate-200 dark:border-white/10 rounded-xl font-bold text-slate-700 dark:text-slate-200 text-xs active:scale-95 transition cursor-pointer"
          >
            <RefreshCw size={14} className={isRefetching ? 'animate-spin text-emerald-500' : ''} />
            <span>تحديث</span>
          </button>
        </div>

        {/* ── Summary KPI Cards ── */}
        <div className="gap-3 sm:gap-4 grid grid-cols-2 lg:grid-cols-4">
          {/* 1. إجمالي التجار */}
          <div className="bg-white dark:bg-[#0c120f] shadow-xs p-4 border border-slate-200/80 dark:border-white/8 rounded-2xl">
            <div className="flex justify-between items-center mb-2 text-slate-500 dark:text-slate-400">
              <span className="font-semibold text-xs">التجار</span>
              <Store size={18} className="text-emerald-500" />
            </div>
            <div className="font-black font-mono text-2xl text-slate-900 dark:text-white">
              {totalMerchants}
            </div>
          </div>

          {/* 2. إجمالي المستخدمين */}
          <div className="bg-white dark:bg-[#0c120f] shadow-xs p-4 border border-slate-200/80 dark:border-white/8 rounded-2xl">
            <div className="flex justify-between items-center mb-2 text-slate-500 dark:text-slate-400">
              <span className="font-semibold text-xs">المستخدمين</span>
              <Users size={18} className="text-blue-500" />
            </div>
            <div className="font-black font-mono text-2xl text-slate-900 dark:text-white">
              {totalUsers}
            </div>
          </div>

          {/* 3. إجمالي القلاع */}
          <div className="bg-white dark:bg-[#0c120f] shadow-xs p-4 border border-slate-200/80 dark:border-white/8 rounded-2xl">
            <div className="flex justify-between items-center mb-2 text-slate-500 dark:text-slate-400">
              <span className="font-semibold text-xs">القلاع</span>
              <Castle size={18} className="text-amber-500" />
            </div>
            <div className="font-black font-mono text-2xl text-slate-900 dark:text-white">
              {totalCastles}
            </div>
          </div>

          {/* 4. القلاع الشغالة الآن */}
          <div className="bg-emerald-500/5 dark:bg-[#0c120f] shadow-xs p-4 border border-emerald-500/30 rounded-2xl">
            <div className="flex justify-between items-center mb-2 text-emerald-700 dark:text-emerald-400">
              <span className="font-bold text-xs">الشغالة الآن</span>
              <div className="relative flex justify-center items-center">
                <span className="absolute bg-emerald-500 opacity-75 rounded-full w-3 h-3 animate-ping" />
                <Zap size={18} className="z-10 relative text-emerald-500" />
              </div>
            </div>
            <div className="font-black font-mono text-2xl text-emerald-600 dark:text-emerald-400">
              {totalRunningCastles}
            </div>
          </div>
        </div>

        {/* ── Error Banner ── */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-sm">
            <AlertCircle size={18} className="shrink-0" />
            <span>{t('admin.merchants.loadError')}</span>
          </div>
        )}

        {/* ── Loading Skeleton ── */}
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-56 bg-slate-200/50 dark:bg-white/5 rounded-2xl animate-pulse"
              />
            ))}
          </div>
        )}

        {/* ── Merchants Cards List ── */}
        {!isLoading && merchants.length === 0 && (
          <div className="text-center py-16 bg-white dark:bg-[#0c120f] rounded-2xl border border-slate-200/80 dark:border-white/8">
            <Store size={48} className="mx-auto text-slate-400 mb-3" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
              {t('admin.merchants.noMerchants')}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
              {t('admin.merchants.addMerchantHint')}
            </p>
          </div>
        )}

        {!isLoading && merchants.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {merchants.map((m) => {
              const primaryDomain = m.domains?.[0] || ''
              const domainUrl = primaryDomain.startsWith('http')
                ? primaryDomain
                : `https://${primaryDomain}`

              return (
                <div
                  key={m.id}
                  className="bg-white dark:bg-[#0c120f] rounded-2xl border border-slate-200/80 dark:border-white/8 p-5 shadow-xs hover:border-slate-300 dark:hover:border-white/15 transition-all flex flex-col justify-between gap-5"
                >
                  {/* Top Bar: Brand, Badge, Color Swatch */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-12 h-12 rounded-2xl flex items-center justify-center text-white font-black text-lg shadow-sm shrink-0"
                        style={{ backgroundColor: m.primary_color || '#2563eb' }}
                      >
                        {m.brand_name?.[0] || 'M'}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h2 className="text-base sm:text-lg font-black text-slate-900 dark:text-white">
                            {m.brand_name}
                          </h2>
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-slate-300 font-mono">
                            {m.id}
                          </span>
                        </div>
                        {m.tagline && (
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            {m.tagline}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Color Swatch Indicator */}
                    <div
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11px] font-mono border"
                      style={{
                        backgroundColor: `${m.primary_color}15`,
                        borderColor: `${m.primary_color}40`,
                        color: m.primary_color,
                      }}
                      title={t('admin.merchants.colorTooltip')}
                    >
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: m.primary_color }}
                      />
                      <span>{m.primary_color}</span>
                    </div>
                  </div>

                  {/* Domain & Admin Email Info */}
                  <div className="space-y-2 bg-slate-50 dark:bg-white/4 p-3 rounded-xl border border-slate-200/60 dark:border-white/6 text-xs">
                    {/* Domains */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400 shrink-0">
                        <Globe size={14} className="text-emerald-500" />
                        <span className="font-semibold">{t('admin.merchants.domains')}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 justify-end">
                        {m.domains?.map((d) => (
                          <a
                            key={d}
                            href={d.startsWith('http') ? d : `https://${d}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-600 dark:text-emerald-400 bg-white dark:bg-black/40 px-2 py-0.5 rounded-lg border border-slate-200 dark:border-emerald-500/20 hover:underline"
                          >
                            <span>{d}</span>
                            <ExternalLink size={10} />
                          </a>
                        ))}
                      </div>
                    </div>

                    {/* Admin Email */}
                    <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-200/60 dark:border-white/6">
                      <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400 shrink-0">
                        <Mail size={14} className="text-blue-500" />
                        <span className="font-semibold">{t('admin.merchants.adminEmail')}</span>
                      </div>
                      <span className="font-mono text-[11px] text-slate-800 dark:text-slate-200 bg-white dark:bg-black/40 px-2 py-0.5 rounded-lg border border-slate-200 dark:border-white/10">
                        {m.admin_email}
                      </span>
                    </div>
                  </div>

                  {/* Stats Metrics (3 Pillars) */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    {/* 1. عدد المستخدمين */}
                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-white/4 border border-slate-200/60 dark:border-white/6">
                      <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 flex items-center justify-center gap-1">
                        <Users size={12} className="text-blue-500" />
                        <span>{t('admin.users')}</span>
                      </div>
                      <div className="text-xl font-black text-slate-900 dark:text-white font-mono mt-1">
                        {m.total_users || 0}
                      </div>
                    </div>

                    {/* 2. إجمالي القلاع */}
                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-white/4 border border-slate-200/60 dark:border-white/6">
                      <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 flex items-center justify-center gap-1">
                        <Castle size={12} className="text-amber-500" />
                        <span>{t('admin.totalCastlesAll')}</span>
                      </div>
                      <div className="text-xl font-black text-slate-900 dark:text-white font-mono mt-1">
                        {m.total_castles || 0}
                      </div>
                    </div>

                    {/* 3. قلاع شغالة حالياً */}
                    <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25">
                      <div className="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 flex items-center justify-center gap-1">
                        <Zap size={12} className="text-emerald-500" />
                        <span>{t('admin.merchants.runningNow')}</span>
                      </div>
                      <div className="text-xl font-black text-emerald-600 dark:text-emerald-400 font-mono mt-1">
                        {m.running_castles || 0}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </AdminLayout>
  )
}
