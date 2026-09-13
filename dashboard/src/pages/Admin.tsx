import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Shield, Trash2, Edit, Ban, CheckCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { Layout } from '../components/layout/Layout'
import { useAllUsers, useAdminStats, useBanUser, useDeleteUser, useUpdateSubscription } from '../hooks/useUsers'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import type { User, Subscription } from '../types'
import toast from 'react-hot-toast'

const PLAN_OPTIONS = [
  { id: 'free',       name: 'مجاني',        max: 1,  color: 'badge-gray'   },
  { id: 'basic',      name: 'أساسية',        max: 3,  color: 'badge-blue'   },
  { id: 'pro',        name: 'احترافية',       max: 10, color: 'badge-green'  },
  { id: 'vip_pro',    name: 'VIP',           max: 25, color: 'badge-yellow' },
  { id: 'enterprise', name: 'Enterprise',    max: 100,color: 'badge-blue'   },
]

function PlanBadge({ plan }: { plan: string }) {
  const p = PLAN_OPTIONS.find(o => o.id === plan)
  return <span className={`badge ${p?.color ?? 'badge-gray'}`}>{p?.name ?? plan}</span>
}

function SubscriptionModal({ user, onClose }: { user: User; onClose: () => void }) {
  const updateSub = useUpdateSubscription()
  const [form, setForm] = useState({
    plan_id: user.subscription.plan_id,
    days: 30,
  })

  const handleSave = () => {
    const plan = PLAN_OPTIONS.find(p => p.id === form.plan_id)!
    const now  = new Date()
    const exp  = new Date(now.getTime() + form.days * 86400000)
    const sub: Partial<Subscription> = {
      plan_id: form.plan_id as Subscription['plan_id'],
      plan_name: plan.name,
      status: 'active',
      started_at: now.toISOString(),
      expires_at: exp.toISOString(),
      days_remaining: form.days,
      max_castles_allowed: plan.max,
    }
    updateSub.mutate({ uid: user.uid, sub }, {
      onSuccess: () => { toast.success('تم تحديث الاشتراك'); onClose() },
      onError: () => toast.error('حدث خطأ'),
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="glass-card w-full max-w-md p-6 relative z-10 space-y-4"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="font-bold text-white text-lg">تعديل الاشتراك — {user.username || user.email}</h3>

        <div>
          <label className="text-xs text-gray-500 mb-1.5 block">الخطة:</label>
          <div className="grid grid-cols-2 gap-2">
            {PLAN_OPTIONS.map(plan => (
              <button
                key={plan.id}
                onClick={() => setForm(f => ({ ...f, plan_id: plan.id as Subscription['plan_id'] }))}
                className={`p-3 rounded-xl border text-sm font-medium transition-all text-start ${
                  form.plan_id === plan.id
                    ? 'border-primary-500 bg-primary-900/40 text-white'
                    : 'border-white/10 text-gray-400 hover:border-white/25'
                }`}
              >
                <div className="font-medium">{plan.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">حتى {plan.max} قلعة</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 mb-1.5 block">مدة الاشتراك (أيام):</label>
          <div className="flex gap-2">
            {[7, 15, 30, 90, 365].map(d => (
              <button key={d} onClick={() => setForm(f => ({ ...f, days: d }))}
                className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${form.days === d ? 'border-primary-500 bg-primary-900/40 text-primary-300' : 'border-white/10 text-gray-400 hover:border-white/20'}`}>
                {d}د
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={handleSave} disabled={updateSub.isPending} className="btn-primary flex-1">
            {updateSub.isPending ? 'جارٍ الحفظ...' : 'حفظ'}
          </button>
          <button onClick={onClose} className="btn-secondary flex-1">إلغاء</button>
        </div>
      </motion.div>
    </div>
  )
}

export function AdminPage() {
  const { t } = useTranslation()
  const { isAdmin } = useAuth()
  const [search, setSearch] = useState('')
  const [editUser, setEditUser] = useState<User | null>(null)

  const { data: users = [], isLoading } = useAllUsers()
  const { data: stats } = useAdminStats()
  const banUser    = useBanUser()
  const deleteUser = useDeleteUser()

  if (!isAdmin) return <Navigate to="/dashboard" replace />

  const filtered = search
    ? users.filter(u =>
        u.email.includes(search) ||
        u.username?.includes(search) ||
        u.uid.includes(search)
      )
    : users

  const handleBan = (u: User) => {
    if (!confirm(u.is_banned ? 'رفع الحظر؟' : t('admin.confirmBan'))) return
    banUser.mutate({ uid: u.uid, ban: !u.is_banned }, {
      onSuccess: () => toast.success(t('common.success')),
      onError: () => toast.error(t('common.error')),
    })
  }

  const handleDelete = (u: User) => {
    if (!confirm(t('admin.confirmDelete'))) return
    deleteUser.mutate(u.uid, {
      onSuccess: () => toast.success(t('common.success')),
      onError: () => toast.error(t('common.error')),
    })
  }

  return (
    <Layout title={t('admin.title')}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Shield size={24} className="text-primary-400" />
              {t('admin.title')}
            </h1>
            <p className="text-xs text-gray-500 mt-1">إدارة شاملة للمستخدمين والاشتراكات</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: t('admin.totalUsers'),          value: stats?.totalUsers ?? '—',           icon: '👥', color: 'text-blue-400',   bg: 'bg-blue-600/10 border-blue-600/20' },
            { label: t('admin.activeSubscriptions'), value: stats?.activeSubscriptions ?? '—',  icon: '✅', color: 'text-green-400',  bg: 'bg-green-600/10 border-green-600/20' },
            { label: t('admin.totalCastlesAll'),     value: stats?.totalCastles ?? '—',         icon: '🏰', color: 'text-yellow-400', bg: 'bg-yellow-600/10 border-yellow-600/20' },
            { label: t('admin.monthlyRevenue'),      value: '—',                                icon: '💰', color: 'text-primary-400', bg: 'bg-primary-600/10 border-primary-600/20' },
          ].map((s, i) => (
            <motion.div key={s.label} initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }} transition={{ delay: i*0.07 }}
              className={`glass-card p-5 border ${s.bg}`}>
              <div className="text-2xl mb-2">{s.icon}</div>
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-gray-500 mt-1">{s.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Users table */}
        <div className="glass-card overflow-hidden">
          <div className="px-5 py-4 border-b border-white/8 flex items-center justify-between gap-3 flex-wrap">
            <h2 className="font-semibold text-white">{t('admin.users')}</h2>
            <div className="relative">
              <Search size={14} className="absolute start-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                id="admin-search"
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder={t('admin.searchUsers')}
                className="input-field ps-8 py-1.5 text-sm w-56"
              />
            </div>
          </div>

          {isLoading ? (
            <div className="text-center py-12 text-gray-500">{t('common.loading')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/8 text-gray-500 text-xs">
                    <th className="px-5 py-3 text-start">المستخدم</th>
                    <th className="px-3 py-3 text-start">{t('admin.role')}</th>
                    <th className="px-3 py-3 text-start">{t('admin.plan')}</th>
                    <th className="px-3 py-3 text-center">{t('admin.castles')}</th>
                    <th className="px-3 py-3 text-start">{t('admin.expires')}</th>
                    <th className="px-3 py-3 text-start">الحالة</th>
                    <th className="px-5 py-3 text-end">الإجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filtered.map(u => (
                    <tr key={u.uid} className="hover:bg-white/3 transition-colors">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-primary-900/60 border border-primary-700/30 flex items-center justify-center text-xs font-bold text-primary-400 flex-shrink-0">
                            {(u.username || u.email)?.[0]?.toUpperCase()}
                          </div>
                          <div>
                            <div className="text-white font-medium">{u.username || '—'}</div>
                            <div className="text-gray-500 text-xs">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`badge ${u.role === 'admin' ? 'badge-yellow' : 'badge-gray'}`}>
                          {u.role === 'admin' ? '👑 Admin' : 'User'}
                        </span>
                      </td>
                      <td className="px-3 py-3"><PlanBadge plan={u.subscription.plan_id} /></td>
                      <td className="px-3 py-3 text-center">
                        <span className="text-white font-medium">{u.subscription.current_castles_count}</span>
                        <span className="text-gray-500">/{u.subscription.max_castles_allowed}</span>
                      </td>
                      <td className="px-3 py-3 text-gray-400 text-xs">
                        {u.subscription.expires_at ? new Date(u.subscription.expires_at).toLocaleDateString('ar') : '—'}
                      </td>
                      <td className="px-3 py-3">
                        {u.is_banned ? (
                          <span className="badge badge-red">محظور</span>
                        ) : u.subscription.status === 'active' ? (
                          <span className="badge badge-green">نشط</span>
                        ) : (
                          <span className="badge badge-gray">{u.subscription.status}</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => setEditUser(u)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/8 transition-colors"
                            title={t('admin.editSubscription')}
                          >
                            <Edit size={14} />
                          </button>
                          <button
                            onClick={() => handleBan(u)}
                            className={`p-1.5 rounded-lg transition-colors ${
                              u.is_banned
                                ? 'text-green-400 hover:bg-green-600/10'
                                : 'text-yellow-400 hover:bg-yellow-600/10'
                            }`}
                            title={u.is_banned ? t('admin.unbanUser') : t('admin.banUser')}
                          >
                            {u.is_banned ? <CheckCircle size={14} /> : <Ban size={14} />}
                          </button>
                          <button
                            onClick={() => handleDelete(u)}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-600/10 transition-colors"
                            title={t('admin.deleteUser')}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {filtered.length === 0 && (
                <div className="text-center py-12 text-gray-500">لا توجد نتائج</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Subscription modal */}
      {editUser && <SubscriptionModal user={editUser} onClose={() => setEditUser(null)} />}
    </Layout>
  )
}
