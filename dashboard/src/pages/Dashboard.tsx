import React from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { Layout } from '../components/layout/Layout'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useAuth } from '../hooks/useAuth'
import { useCastles } from '../hooks/useCastles'
import { motion } from 'framer-motion'
import { Plus, Users, Shield, Zap, Bot, Crown, AlertTriangle, AlertCircle, ShieldAlert } from 'lucide-react'

const chartData = Array.from({ length: 12 }, (_, i) => ({
  name: `${i + 1}:00`,
  active: Math.floor(Math.random() * 8) + 2,
  tasks: Math.floor(Math.random() * 50) + 20,
}))

import { localizePlanName, localizeUsername } from '../lib/localize'

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const { user, isAdmin } = useAuth()
  const castlesQuery = useCastles(user?.uid ?? '')
  const allCastles = castlesQuery.data?.pages.flatMap(p => p.items) ?? []
  const running = allCastles.filter(c => c.bot_status.state === 'running').length
  const idle    = allCastles.filter(c => c.bot_status.state === 'idle').length
  const errors  = allCastles.filter(c => c.bot_status.state === 'error').length
  const sub = user?.subscription

  const planDisplayName = localizePlanName(sub?.plan_name, t)
  const usernameDisplay = localizeUsername(user?.username, t) || user?.email

  // Expiration & countdown checks
  const now = Date.now()
  const expDate = sub?.expires_at ? new Date(sub.expires_at) : null
  const isLifetime = expDate ? expDate.getFullYear() >= 2090 : false
  const isExpired = !isLifetime && (sub?.status === 'expired' || (expDate ? expDate.getTime() < now : false))
  const daysRemaining = isLifetime ? 99999 : (expDate ? Math.ceil((expDate.getTime() - now) / 86400000) : (sub?.days_remaining ?? 0))
  const isExpiringSoon = !isAdmin && !isExpired && daysRemaining <= 3 && daysRemaining >= 0
  const isBanned = !isAdmin && Boolean(user?.is_banned)

  const stats = [
    { label: t('dashboard.totalCastles'),  value: allCastles.length, icon: '🏰', color: 'text-blue-400',   bg: 'bg-blue-600/10 border-blue-600/20' },
    { label: t('dashboard.activeCastles'), value: running,            icon: '▶️', color: 'text-green-400',  bg: 'bg-green-600/10 border-green-600/20' },
    { label: t('dashboard.idleCastles'),   value: idle,               icon: '⏸️', color: 'text-gray-400',   bg: 'bg-gray-600/10 border-gray-600/20' },
    {
      label: t('dashboard.subscription'),
      value: isAdmin ? t('dashboard.superAdminUnlimited') : isBanned ? t('dashboard.bannedBadge') : (planDisplayName || '—'),
      icon: isAdmin ? '👑' : isBanned ? '🚫' : isExpired ? '⚠️' : isExpiringSoon ? '⏳' : '⭐',
      color: isAdmin
        ? 'text-amber-400'
        : isBanned || isExpired
        ? 'text-rose-500 dark:text-rose-400'
        : isExpiringSoon
        ? 'text-amber-500 dark:text-amber-400'
        : 'text-yellow-400',
      bg: isAdmin
        ? 'bg-amber-600/10 border-amber-600/20'
        : isBanned || isExpired
        ? 'bg-rose-500/15 border-rose-500/40 ring-1 ring-rose-500/30'
        : isExpiringSoon
        ? 'bg-amber-500/15 border-amber-500/40 ring-1 ring-amber-500/30'
        : 'bg-yellow-600/10 border-yellow-600/20',
      badge: isBanned ? t('dashboard.bannedBadge') : isExpired ? t('dashboard.expiredBadge') : isExpiringSoon ? t('dashboard.daysRemainingShort', { count: daysRemaining }) : undefined,
    },
  ]

  return (
    <Layout title={t('dashboard.title')}>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex flex-wrap justify-between items-center gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h1 className="font-bold text-2xl brand-title">{t('dashboard.title')}</h1>
              <span className="inline-flex items-center gap-1.5 bg-emerald-500/10 px-2.5 py-0.5 border border-emerald-500/20 rounded-full font-bold text-xs brand-tagline">
                <span className="bg-emerald-500 rounded-full w-1.5 h-1.5" />
                IBRA BOT — {t('tagline')}
              </span>
            </div>
          </div>
        </div>

        {/* ── Banned Alert ── */}
        {isBanned && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3.5 bg-rose-500/15 shadow-xs p-3.5 sm:p-4 border border-rose-500/40 rounded-2xl text-rose-950 dark:text-rose-100 dashboard-banner-banned"
          >
            <div className="flex justify-center items-center bg-rose-500/20 border border-rose-500/40 rounded-xl w-10 h-10 text-rose-400 banner-icon-box shrink-0">
              <ShieldAlert size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-bold text-rose-950 dark:text-rose-100 text-sm banner-title">
                  {t('dashboard.bannedTitle')}
                </h3>
                <span className="py-0.5 text-[10px] badge badge-red">{t('dashboard.bannedBadge')}</span>
              </div>
              <p className="mt-0.5 text-rose-800 dark:text-rose-300/90 text-xs banner-desc">
                {t('dashboard.bannedDesc')}
              </p>
            </div>
          </motion.div>
        )}

        {/* ── Expiry Alert: Expired ── */}
        {isExpired && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3.5 bg-rose-500/10 dark:bg-rose-500/15 shadow-xs p-3.5 sm:p-4 border border-rose-500/30 rounded-2xl text-rose-900 dark:text-rose-100"
          >
            <div className="flex justify-center items-center bg-rose-500/20 border border-rose-500/30 rounded-xl w-10 h-10 text-rose-600 dark:text-rose-400 shrink-0">
              <AlertCircle size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-bold text-rose-900 dark:text-rose-100 text-sm">
                  {t('dashboard.expiredTitle')}
                </h3>

              </div>
              <p className="mt-0.5 text-rose-700 dark:text-rose-300/90 text-xs">
                {t('dashboard.expiredDesc')}
              </p>
            </div>
          </motion.div>
        )}

        {/* ── Expiry Alert: Expiring Soon (3 days or less) ── */}
        {isExpiringSoon && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3.5 bg-amber-500/10 dark:bg-amber-500/15 shadow-xs p-3.5 sm:p-4 border border-amber-500/35 rounded-2xl text-amber-900 dark:text-amber-100"
          >
            <div className="flex justify-center items-center bg-amber-500/20 border border-amber-500/30 rounded-xl w-10 h-10 text-amber-600 dark:text-amber-400 shrink-0">
              <AlertTriangle size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-bold text-amber-900 dark:text-amber-100 text-sm">
                  {daysRemaining === 0
                    ? t('dashboard.expiringTodayTitle')
                    : daysRemaining === 1
                    ? t('dashboard.expiringOneDayTitle')
                    : t('dashboard.expiringSoonTitle', { days: daysRemaining })}
                </h3>
                <span className="py-0.5 text-[10px] animate-pulse badge badge-yellow">
                  {daysRemaining === 0 ? t('dashboard.lastDay') : t('dashboard.daysRemainingBadge', { count: daysRemaining })}
                </span>
              </div>
              <p className="mt-0.5 text-amber-700 dark:text-amber-300/90 text-xs">
                {t('dashboard.expiringSoonDesc')}
              </p>
            </div>
          </motion.div>
        )}

        {/* ── Empty State ─────────────────────────────────── */}
        {!castlesQuery.isLoading && allCastles.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6 p-8 text-center glass-card"
          >
            <div className="flex justify-center items-center bg-white shadow-md mx-auto p-1.5 border border-gray-200 dark:border-emerald-500/30 rounded-2xl w-20 h-20 overflow-hidden">
              <img src="/logo.png?v=2" alt="IBRA BOT" className="w-full h-full object-contain" />
            </div>
            <div>
              <div className="inline-block bg-emerald-500/10 mb-2 px-2.5 py-0.5 border border-emerald-500/20 rounded-full font-bold text-xs brand-tagline">
                {t('tagline')}
              </div>
              <h2 className="mb-2 font-bold text-xl brand-title">{t('dashboard.welcomeTitle')}</h2>
              <p className="mx-auto max-w-sm text-gray-500 dark:text-gray-400 text-sm">
                {t('dashboard.welcomeDesc')}
              </p>
            </div>
            <div className="gap-4 grid grid-cols-1 sm:grid-cols-3 text-start">
              {[
                { icon: <Plus size={18} />, step: '1', title: t('dashboard.step1Title'), desc: t('dashboard.step1Desc'), clr: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10' },
                { icon: <Zap  size={18} />, step: '2', title: t('dashboard.step2Title'), desc: t('dashboard.step2Desc'), clr: 'border-blue-500/30 text-blue-600 dark:text-blue-400 bg-blue-500/10' },
                { icon: <Bot  size={18} />, step: '3', title: t('dashboard.step3Title'), desc: t('dashboard.step3Desc'), clr: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10' },
              ].map(s => (
                <div key={s.step} className={`p-4 rounded-xl border ${s.clr} space-y-2`}>
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center border ${s.clr}`}>{s.icon}</div>
                  <div className="text-gray-500 text-xs">{t('dashboard.stepPrefix')} {s.step}</div>
                  <div className="font-semibold text-sm brand-title">{s.title}</div>
                  <div className="text-gray-500 text-xs">{s.desc}</div>
                </div>
              ))}
            </div>
            <Link to="/accounts" className="inline-flex gap-2 btn-primary">
              <Plus size={16} />
              {t('dashboard.addFirstCastle')}
            </Link>
          </motion.div>
        )}

        {/* Stats cards */}
        {allCastles.length > 0 && (
          <div className="gap-4 grid grid-cols-2 lg:grid-cols-4">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`glass-card p-5 border ${s.bg}`}
              >
                <div className="flex justify-between items-center mb-3">
                  <span className="text-2xl">{s.icon}</span>
                  {errors > 0 && s.label === t('dashboard.activeCastles') && (
                    <span className="badge badge-red">{t('dashboard.errorCount', { count: errors })}</span>
                  )}
                  {s.badge && (
                    <span className={`badge ${isExpired ? 'badge-red' : 'badge-yellow animate-pulse'} text-[10px]`}>
                      {s.badge}
                    </span>
                  )}
                </div>
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="mt-1 text-gray-500 text-xs">{s.label}</div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Subscription info */}
        {sub && (
          <div className={`glass-card p-4 flex items-center justify-between flex-wrap gap-3 transition-all ${
            isExpired
              ? 'border-rose-500/40 bg-rose-50/50 dark:bg-rose-950/20 shadow-xs'
              : isExpiringSoon
              ? 'border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20 shadow-xs'
              : ''
          }`}>
            <div>
              <div className="flex flex-wrap items-center gap-2 font-medium text-sm brand-title">
                {isAdmin && <Crown size={15} className="inline text-amber-500" />}
                <span>{isAdmin ? t('dashboard.superAdminFull') : planDisplayName}</span>
                {isExpired && <span className="text-[10px] badge badge-red">{t('dashboard.expiredBadge')}</span>}
                {isExpiringSoon && <span className="text-[10px] animate-pulse badge badge-yellow">{t('dashboard.expiringSoonBadge')}</span>}
              </div>
              <div className="mt-0.5 text-gray-500 text-xs">
                {isAdmin ? (
                  <span className="font-medium text-emerald-500 dark:text-emerald-400">{t('dashboard.superAdminLifetime')}</span>
                ) : (
                  <>
                    {t('dashboard.expiresOn')}: <span dir="ltr" className="font-mono font-medium">{expDate ? `${expDate.getFullYear()}/${String(expDate.getMonth() + 1).padStart(2, '0')}/${String(expDate.getDate()).padStart(2, '0')}` : '—'}</span>
                    {!isExpired && (
                      <> •{' '}
                        <span className={isExpiringSoon ? 'text-amber-600 dark:text-amber-400 font-bold' : ''}>
                          {t('dashboard.daysRemaining', { count: daysRemaining })}
                        </span>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-gray-400">
                {t('dashboard.castlesCount')}:{' '}
                <span className="font-medium brand-title">
                  {isAdmin ? `${sub.current_castles_count} / ${t('dashboard.unlimited')}` : `${sub.current_castles_count}/${sub.max_castles_allowed}`}
                </span>
              </span>
              {!isAdmin && (
                <div className="bg-slate-200 dark:bg-white/10 rounded-full w-32 h-2 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      isExpired ? 'bg-rose-500' : isExpiringSoon ? 'bg-amber-500' : 'bg-primary-500'
                    }`}
                    style={{ width: `${Math.min(100, ((sub.current_castles_count ?? 0) / (sub.max_castles_allowed || 1)) * 100)}%` }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Activity chart */}
        <div className="p-5 glass-card">
          <h2 className="mb-4 font-semibold text-sm brand-title">{t('dashboard.botOverview')}</h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="gradActive" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradTasks" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#6ee7b7" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#6ee7b7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" stroke="#4b5563" tick={{ fontSize: 11 }} />
              <YAxis stroke="#4b5563" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#111a11', border: '1px solid rgba(34,197,94,0.2)', borderRadius: '12px' }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Area type="monotone" dataKey="active" stroke="#10b981" fill="url(#gradActive)" strokeWidth={2} name={t('dashboard.chartActiveCastles')} />
              <Area type="monotone" dataKey="tasks"  stroke="#6ee7b7" fill="url(#gradTasks)"  strokeWidth={1.5} name={t('dashboard.chartCompletedTasks')} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Recent castles */}
        {allCastles.length > 0 && (
          <div className="overflow-hidden glass-card">
            <div className="px-5 py-3 border-gray-100 dark:border-white/8 border-b">
              <h2 className="font-semibold text-sm brand-title">{t('dashboard.recentActivity')}</h2>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-white/6">
              {allCastles.slice(0, 5).map(c => (
                <div key={c.id} className="flex justify-between items-center hover:bg-black/2 dark:hover:bg-white/3 px-5 py-3 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="flex justify-center items-center bg-primary-900/60 border border-primary-700/30 rounded-lg w-8 h-8 font-bold text-primary-400 text-xs">
                      {c.castle_info.castle_level}
                    </div>
                    <div>
                      <div className="font-medium text-sm brand-title">{c.castle_info.lord_name}</div>
                      <div className="text-gray-500 text-xs">{c.email}</div>
                    </div>
                  </div>
                  <StatusBadge state={c.bot_status.state} label={t(`status.${c.bot_status.state}`)} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
