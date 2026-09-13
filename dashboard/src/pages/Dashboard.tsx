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
import { Plus, Users, Shield, Zap, Bot } from 'lucide-react'

const chartData = Array.from({ length: 12 }, (_, i) => ({
  name: `${i + 1}:00`,
  active: Math.floor(Math.random() * 8) + 2,
  tasks: Math.floor(Math.random() * 50) + 20,
}))

export function DashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const castlesQuery = useCastles(user?.uid ?? '')
  const allCastles = castlesQuery.data?.pages.flatMap(p => p.items) ?? []
  const running = allCastles.filter(c => c.bot_status.state === 'running').length
  const idle    = allCastles.filter(c => c.bot_status.state === 'idle').length
  const errors  = allCastles.filter(c => c.bot_status.state === 'error').length
  const sub = user?.subscription

  const stats = [
    { label: t('dashboard.totalCastles'),  value: allCastles.length, icon: '🏰', color: 'text-blue-400',   bg: 'bg-blue-600/10 border-blue-600/20' },
    { label: t('dashboard.activeCastles'), value: running,            icon: '▶️', color: 'text-green-400',  bg: 'bg-green-600/10 border-green-600/20' },
    { label: t('dashboard.idleCastles'),   value: idle,               icon: '⏸️', color: 'text-gray-400',   bg: 'bg-gray-600/10 border-gray-600/20' },
    { label: t('dashboard.subscription'),  value: sub?.plan_name ?? '—', icon: '⭐', color: 'text-yellow-400', bg: 'bg-yellow-600/10 border-yellow-600/20' },
  ]

  return (
    <Layout title={t('dashboard.title')}>
      <div className="space-y-6">
        {/* Page header */}
        <div>
          <h1 className="text-2xl font-bold text-white">{t('dashboard.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">
            {user?.username ?? user?.email}
            {sub && <span className="ms-2 badge badge-green">{sub.plan_name}</span>}
          </p>
        </div>

        {/* ── Empty State ─────────────────────────────────── */}
        {!castlesQuery.isLoading && allCastles.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-8 text-center space-y-6"
          >
            <div className="w-20 h-20 rounded-2xl bg-primary-900/50 border border-primary-700/30 flex items-center justify-center mx-auto">
              <Bot size={40} className="text-primary-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white mb-2">مرحباً بك في OsmanliBot! 👋</h2>
              <p className="text-gray-500 text-sm max-w-sm mx-auto">
                لوحة التحكم فارغة حالياً. ابدأ بإضافة حسابات قلعتك لتشغيل البوت وإدارة جميع المهام تلقائياً.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-start">
              {[
                { icon: <Plus size={18} />, step: '١', title: 'أضف حسابك',   desc: 'اذهب لصفحة الحسابات وأضف حساب القلعة الأول',    clr: 'border-primary-700/30 text-primary-400 bg-primary-900/30' },
                { icon: <Zap  size={18} />, step: '٢', title: 'فعّل المهام', desc: 'اختر المهام التي تريد تشغيلها تلقائياً',          clr: 'border-blue-700/30 text-blue-400 bg-blue-900/30' },
                { icon: <Bot  size={18} />, step: '٣', title: 'شغّل البوت',  desc: 'اضغط تشغيل وسيبدأ البوت في العمل فوراً',         clr: 'border-emerald-700/30 text-emerald-400 bg-emerald-900/30' },
              ].map(s => (
                <div key={s.step} className={`p-4 rounded-xl border ${s.clr} space-y-2`}>
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center border ${s.clr}`}>{s.icon}</div>
                  <div className="text-xs text-gray-500">الخطوة {s.step}</div>
                  <div className="font-semibold text-white text-sm">{s.title}</div>
                  <div className="text-xs text-gray-500">{s.desc}</div>
                </div>
              ))}
            </div>
            <Link to="/accounts" className="btn-primary gap-2 inline-flex">
              <Plus size={16} />
              إضافة أول حساب
            </Link>
          </motion.div>
        )}

        {/* Stats cards */}
        {allCastles.length > 0 && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`glass-card p-5 border ${s.bg}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-2xl">{s.icon}</span>
                  {errors > 0 && s.label === t('dashboard.activeCastles') && (
                    <span className="badge badge-red">{errors} خطأ</span>
                  )}
                </div>
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-gray-500 mt-1">{s.label}</div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Subscription info */}
        {sub && (
          <div className="glass-card p-4 flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="text-sm font-medium text-white">{sub.plan_name}</div>
              <div className="text-xs text-gray-500">
                تنتهي: {new Date(sub.expires_at).toLocaleDateString('ar')} • متبقي {sub.days_remaining} يوم
              </div>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-gray-400">القلاع: <span className="text-white font-medium">{sub.current_castles_count}/{sub.max_castles_allowed}</span></span>
              <div className="w-32 h-2 rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-primary-500 transition-all"
                  style={{ width: `${(sub.current_castles_count / sub.max_castles_allowed) * 100}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Activity chart */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-white mb-4">{t('dashboard.botOverview')}</h2>
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
              <Area type="monotone" dataKey="active" stroke="#10b981" fill="url(#gradActive)" strokeWidth={2} name="القلاع النشطة" />
              <Area type="monotone" dataKey="tasks"  stroke="#6ee7b7" fill="url(#gradTasks)"  strokeWidth={1.5} name="المهام المنجزة" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Recent castles */}
        {allCastles.length > 0 && (
          <div className="glass-card overflow-hidden">
            <div className="px-5 py-3 border-b border-white/8">
              <h2 className="text-sm font-semibold text-white">{t('dashboard.recentActivity')}</h2>
            </div>
            <div className="divide-y divide-white/6">
              {allCastles.slice(0, 5).map(c => (
                <div key={c.id} className="flex items-center justify-between px-5 py-3 hover:bg-white/3 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary-900/60 border border-primary-700/30 flex items-center justify-center text-xs font-bold text-primary-400">
                      {c.castle_info.castle_level}
                    </div>
                    <div>
                      <div className="text-sm text-white font-medium">{c.castle_info.lord_name}</div>
                      <div className="text-xs text-gray-500">{c.email}</div>
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
