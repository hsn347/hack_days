import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Search, Shield, Trash2, Edit, Ban, CheckCircle, Clock, X,
  Layers, Calendar, Plus, Minus, AlertTriangle
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { AdminLayout } from '../components/layout/AdminLayout'
import {
  useAllUsers, useAdminStats, useBanUser, useDeleteUser,
  useApproveCastle, useRejectCastle
} from '../hooks/useUsers'
import { useCastles, useDeleteCastle } from '../hooks/useCastles'
import { useQueryClient } from '@tanstack/react-query'
import { doc, updateDoc } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { Navigate } from 'react-router-dom'
import { useAdminAuth } from '../hooks/useAdminAuth'
import type { User, Subscription, Castle } from '../types'
import toast from 'react-hot-toast'

// ─── Confirm Dialog ──────────────────────────────────────────
function ConfirmDialog({
  title, message, email, onConfirm, onCancel, loading = false,
}: {
  title: string; message: string; email?: string;
  onConfirm: () => void; onCancel: () => void; loading?: boolean
}) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onCancel}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.92, y: 16 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-xs bg-[#0c1410] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Red accent top line */}
        <div className="h-0.5 w-full bg-gradient-to-r from-red-500/0 via-red-500 to-red-500/0" />

        <div className="p-6 space-y-4">
          {/* Icon + Title */}
          <div className="flex flex-col items-center text-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <AlertTriangle size={26} className="text-red-400" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">{title}</h3>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">{message}</p>
            </div>
          </div>

          {/* Email badge */}
          {email && (
            <div className="bg-white/[0.03] border border-white/8 rounded-xl px-3 py-2 text-center">
              <span className="text-xs font-mono text-gray-300 truncate block">{email}</span>
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className="flex-1 py-2.5 rounded-xl border border-white/10 text-gray-400 hover:text-white hover:border-white/20 text-sm font-medium transition-all"
            >
              إلغاء
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={loading}
              className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-semibold transition-all disabled:opacity-50 active:scale-[0.98] flex items-center justify-center gap-1.5"
            >
              {loading ? (
                <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />جارٍ الحذف...</>
              ) : (
                <><Trash2 size={13} />حذف نهائياً</>
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// Stepper Component
function Stepper({
  value, min = 1, max = 999, onChange, color = 'emerald',
}: {
  value: number; min?: number; max?: number; onChange: (v: number) => void; color?: 'emerald' | 'primary'
}) {
  const accent = color === 'emerald' ? 'text-emerald-400' : 'text-primary-400'
  const btnBg = color === 'emerald'
    ? 'bg-emerald-500/15 hover:bg-emerald-500/30 text-emerald-300'
    : 'bg-primary-500/15 hover:bg-primary-500/30 text-primary-300'
  return (
    <div className="flex items-center gap-3">
      <button type="button" onClick={() => onChange(Math.max(min, value - 1))} disabled={value <= min}
        className={`w-9 h-9 rounded-full flex items-center justify-center transition-all active:scale-90 disabled:opacity-25 ${btnBg}`}>
        <Minus size={15} />
      </button>
      <input type="number" min={min} max={max} value={value}
        onChange={e => onChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))}
        className={`w-14 text-center font-extrabold text-3xl bg-transparent border-0 focus:ring-0 p-0 ${accent}`} />
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max}
        className={`w-9 h-9 rounded-full flex items-center justify-center transition-all active:scale-90 disabled:opacity-25 ${btnBg}`}>
        <Plus size={15} />
      </button>
    </div>
  )
}

// Quick Chips
function QuickChips({ options, value, onSelect, color = 'emerald' }: {
  options: { label: string; value: number }[]; value: number; onSelect: (v: number) => void; color?: 'emerald' | 'primary'
}) {
  const activeClass = color === 'emerald' ? 'bg-emerald-500 text-black' : 'bg-primary-500 text-black'
  return (
    <div className="flex items-center gap-1.5 flex-wrap justify-center">
      {options.map(opt => (
        <button key={opt.value} type="button" onClick={() => onSelect(opt.value)}
          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
            value === opt.value ? activeClass : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}>
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// Modal 1: Edit User Subscription
function EditUserModal({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient()
  const [saving, setSaving] = useState(false)
  const [castles, setCastles] = useState(Number(user.subscription?.max_castles_allowed ?? 1))
  const [months, setMonths] = useState(Number(user.subscription?.months_duration ?? 1) || 1)
  const [extendFromCurrent, setExtendFromCurrent] = useState(true)
  const now = new Date()
  const currentExp = user.subscription?.expires_at ? new Date(user.subscription.expires_at) : null
  const isCurrentValid = currentExp && currentExp.getTime() > now.getTime()
  const baseDate = extendFromCurrent && isCurrentValid ? currentExp : now
  const newExp = new Date(baseDate.getTime())
  newExp.setMonth(newExp.getMonth() + months)
  const daysLeft = Math.max(0, Math.ceil((newExp.getTime() - now.getTime()) / 86400000))

  const handleSave = async () => {
    setSaving(true)
    try {
      const sub: Partial<Subscription> = {
        plan_id: `${castles}_castles`,
        plan_name: `${castles} حساب`,
        started_at: user.subscription?.started_at || now.toISOString(),
        expires_at: newExp.toISOString(),
        days_remaining: daysLeft,
        months_duration: months,
        max_castles_allowed: castles,
      }
      await updateDoc(doc(db, 'users', user.uid), { subscription: sub })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      toast.success('تم حفظ التعديلات بنجاح')
      onClose()
    } catch { toast.error('حدث خطأ أثناء الحفظ') }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 12 }} transition={{ duration: 0.18, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-sm bg-[#0c1410] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}>
        <div className="h-0.5 w-full bg-gradient-to-r from-emerald-500/0 via-emerald-500 to-emerald-500/0" />
        <div className="p-6 space-y-5">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-white text-base">تعديل الاشتراك</h3>
              <p className="text-xs text-gray-500 mt-0.5 font-mono truncate max-w-[220px]">{user.email}</p>
            </div>
            <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-all">
              <X size={15} />
            </button>
          </div>

          {/* Castles */}
          <div className="bg-white/[0.03] rounded-xl p-4 border border-white/8 space-y-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <Layers size={13} className="text-primary-400" />
              <span>عدد الحسابات المسموحة</span>
            </div>
            <div className="flex justify-center"><Stepper value={castles} onChange={setCastles} max={500} color="primary" /></div>
            <QuickChips options={[{label:'1',value:1},{label:'3',value:3},{label:'5',value:5},{label:'10',value:10},{label:'20',value:20}]} value={castles} onSelect={setCastles} color="primary" />
          </div>

          {/* Months */}
          <div className="bg-white/[0.03] rounded-xl p-4 border border-white/8 space-y-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <Calendar size={13} className="text-emerald-400" />
              <span>مدة الاشتراك (بالأشهر)</span>
            </div>
            <div className="flex justify-center"><Stepper value={months} onChange={setMonths} max={60} color="emerald" /></div>
            <QuickChips options={[{label:'1ش',value:1},{label:'3ش',value:3},{label:'6ش',value:6},{label:'سنة',value:12},{label:'سنتان',value:24}]} value={months} onSelect={setMonths} color="emerald" />
            {isCurrentValid && (
              <button
                type="button"
                onClick={() => setExtendFromCurrent(v => !v)}
                className={`w-full flex items-center justify-between gap-3 mt-1 pt-2.5 border-t border-white/5 transition-all`}
              >
                <span className={`text-[11px] transition-colors ${extendFromCurrent ? 'text-emerald-400' : 'text-gray-500'}`}>
                  إضافة الأشهر بعد الانتهاء الحالي
                  <span className="block text-[10px] font-mono text-gray-600 mt-0.5">{currentExp.toLocaleDateString('ar')}</span>
                </span>
                {/* Toggle switch */}
                <div className={`relative w-9 h-5 rounded-full transition-all duration-200 shrink-0 ${extendFromCurrent ? 'bg-emerald-500' : 'bg-white/10'}`}>
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full shadow transition-all duration-200 ${extendFromCurrent ? 'bg-white translate-x-4' : 'bg-white/40 translate-x-0.5'}`} />
                </div>
              </button>
            )}
          </div>

          {/* Expiry preview */}
          <div className="flex items-center justify-between px-1 text-xs">
            <span className="text-gray-500">تاريخ الانتهاء:</span>
            <span className="font-mono text-white font-semibold">{newExp.toLocaleDateString('ar')} <span className="text-emerald-400">({daysLeft} يوم)</span></span>
          </div>



          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-white/10 text-gray-400 hover:text-white hover:border-white/20 text-sm font-medium transition-all">إلغاء</button>
            <button type="button" onClick={handleSave} disabled={saving} className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all disabled:opacity-50 active:scale-[0.98]">
              {saving ? 'جارٍ الحفظ...' : 'حفظ'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// Modal 2: Manage User Castles
function UserCastlesModal({ user, onClose }: { user: User; onClose: () => void }) {
  const { data, isLoading } = useCastles(user.uid)
  const castlesList: Castle[] = data?.pages.flatMap(p => p.items) ?? []
  const approveCastle = useApproveCastle()
  const rejectCastle = useRejectCastle()
  const deleteCastle = useDeleteCastle(user.uid)
  const pending = castlesList.filter((c: Castle) => c.bot_status?.state === 'pending')
  const active = castlesList.filter((c: Castle) => c.bot_status?.state !== 'pending')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 12 }} transition={{ duration: 0.18, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-lg bg-[#0c1410] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]"
        onClick={e => e.stopPropagation()}>
        <div className="h-0.5 w-full bg-gradient-to-r from-primary-500/0 via-primary-500 to-primary-500/0 shrink-0" />

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/8 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center text-lg">🏰</div>
            <div>
              <h3 className="font-semibold text-white text-sm">حسابات المستخدم</h3>
              <p className="text-[11px] text-gray-500 font-mono truncate max-w-[200px]">{user.email}</p>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-all">
            <X size={15} />
          </button>
        </div>

        {/* Stats bar */}
        <div className="flex border-b border-white/8 shrink-0">
          {[
            { label: 'الحد المسموح', value: user.subscription?.max_castles_allowed ?? 1, color: 'text-primary-400' },
            { label: 'نشطة', value: active.length, color: 'text-emerald-400' },
            { label: 'انتظار', value: pending.length, color: pending.length > 0 ? 'text-yellow-400' : 'text-gray-500' },
          ].map((s, i) => (
            <div key={i} className="flex-1 py-3 text-center border-l border-white/8 first:border-l-0">
              <div className={`font-bold font-mono text-lg ${s.color}`}>{s.value}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 p-5 space-y-4">
          {isLoading ? (
            <div className="py-10 text-center text-gray-500 text-sm">جارٍ التحميل...</div>
          ) : castlesList.length === 0 ? (
            <div className="py-10 text-center text-gray-500 text-sm">لا توجد حسابات مضافة لهذا المستخدم.</div>
          ) : (
            <>
              {pending.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-yellow-400 font-semibold">
                    <Clock size={13} /><span>بانتظار الموافقة ({pending.length})</span>
                  </div>
                  {pending.map(c => (
                    <div key={c.id} className="flex items-center justify-between gap-3 p-3 rounded-xl bg-yellow-500/5 border border-yellow-500/20">
                      <div className="min-w-0">
                        <div className="text-sm text-white font-medium truncate">{c.castle_info?.castle_name || c.castle_info?.lord_name || 'قلعة'}</div>
                        <div className="text-[11px] text-gray-500 font-mono truncate">{c.email}</div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button disabled={approveCastle.isPending}
                          onClick={() => approveCastle.mutate({userId:user.uid,castleId:c.id},{onSuccess:()=>toast.success('تمت الموافقة'),onError:()=>toast.error('حدث خطأ')})}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all">
                          <CheckCircle size={12} />قبول
                        </button>
                        <button disabled={rejectCastle.isPending}
                          onClick={() => { if(!confirm(`رفض وحذف الحساب (${c.email})؟`)) return; rejectCastle.mutate({userId:user.uid,castleId:c.id},{onSuccess:()=>toast.success('تم الرفض'),onError:()=>toast.error('حدث خطأ')}) }}
                          className="w-8 h-8 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 flex items-center justify-center transition-all">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {active.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-emerald-400 font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                    <span>الحسابات النشطة ({active.length})</span>
                  </div>
                  {active.map(c => (
                    <div key={c.id} className="flex items-center justify-between gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/8 hover:border-white/12 transition-colors">
                      <div className="min-w-0">
                        <div className="text-sm text-white font-medium truncate">{c.castle_info?.castle_name || c.castle_info?.lord_name || 'قلعة'}</div>
                        <div className="text-[11px] text-gray-500 font-mono truncate">{c.email}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="badge badge-green text-[10px] py-0.5">نشط</span>
                        <button
                          onClick={() => { if(!confirm(`حذف الحساب "${c.email}"؟`)) return; deleteCastle.mutate({castleId:c.id,wasActive:true},{onSuccess:()=>toast.success('تم الحذف'),onError:()=>toast.error('حدث خطأ')}) }}
                          className="w-7 h-7 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 flex items-center justify-center transition-all">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/8 shrink-0">
          <button onClick={onClose} className="w-full py-2 rounded-xl border border-white/10 text-gray-400 hover:text-white hover:border-white/20 text-sm font-medium transition-all">إغلاق</button>
        </div>
      </motion.div>
    </div>
  )
}

// Main Admin Page
export function AdminPage() {
  const { t } = useTranslation()
  const { isAuthenticated, loading: authLoading } = useAdminAuth()
  const [search, setSearch] = useState('')
  const [editUser, setEditUser] = useState<User | null>(null)
  const [manageCastlesUser, setManageCastlesUser] = useState<User | null>(null)
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<User | null>(null)
  const [deleting, setDeleting] = useState(false)
  const { data: users = [], isLoading } = useAllUsers()
  const { data: stats } = useAdminStats()
  const banUser = useBanUser()
  const deleteUser = useDeleteUser()

  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#060a08] flex items-center justify-center text-emerald-400">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
          <span className="text-xs font-mono">التحقق من الصلاحيات...</span>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/admin/login" replace />

  const filtered = search
    ? users.filter(u => u.email.toLowerCase().includes(search.toLowerCase()) || u.username?.toLowerCase().includes(search.toLowerCase()) || u.uid.includes(search))
    : users

  const handleBan = (u: User) => {
    if (!confirm(u.is_banned ? 'رفع الحظر عن هذا المستخدم؟' : 'حظر هذا المستخدم؟')) return
    banUser.mutate({uid:u.uid,ban:!u.is_banned},{onSuccess:()=>toast.success(t('common.success')),onError:()=>toast.error(t('common.error'))})
  }

  const handleDelete = (u: User) => setConfirmDeleteUser(u)

  const doDelete = () => {
    if (!confirmDeleteUser) return
    setDeleting(true)
    deleteUser.mutate(confirmDeleteUser.uid, {
      onSuccess: () => {
        toast.success('تم حذف المستخدم بنجاح')
        setConfirmDeleteUser(null)
        setDeleting(false)
      },
      onError: () => {
        toast.error('حدث خطأ أثناء الحذف')
        setDeleting(false)
      },
    })
  }

  return (
    <AdminLayout title={t('admin.title')}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Shield size={24} className="text-primary-400" />
              <span>{t('admin.title')}</span>
            </h1>
            <p className="text-xs text-gray-500 mt-1">إدارة المستخدمين، الحسابات المسموحة، مدة الاشتراك، وقبول الطلبات</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {label:t('admin.totalUsers'),value:stats?.totalUsers??'—',icon:'👥',color:'text-blue-400',bg:'bg-blue-600/10 border-blue-600/20'},
            {label:t('admin.activeSubscriptions'),value:stats?.activeSubscriptions??'—',icon:'✅',color:'text-green-400',bg:'bg-green-600/10 border-green-600/20'},
            {label:t('admin.totalCastlesAll'),value:stats?.totalCastles??'—',icon:'🏰',color:'text-yellow-400',bg:'bg-yellow-600/10 border-yellow-600/20'},
            {label:'في الانتظار',value:users.reduce((acc,u)=>acc+(u.subscription?.pending_castles_count||0),0),icon:'⏳',color:'text-primary-400',bg:'bg-primary-600/10 border-primary-600/20'},
          ].map((s,i)=>(
            <motion.div key={s.label} initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{delay:i*0.07}} className={`glass-card p-5 border ${s.bg}`}>
              <div className="text-2xl mb-2">{s.icon}</div>
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-gray-500 mt-1">{s.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Users Table */}
        <div className="glass-card overflow-hidden">
          <div className="px-5 py-4 border-b border-white/8 flex items-center justify-between gap-3 flex-wrap">
            <h2 className="font-semibold text-white flex items-center gap-2">
              <span>{t('admin.users')}</span>
              <span className="text-xs font-normal text-gray-500">({filtered.length})</span>
            </h2>
            <div className="relative flex items-center">
              <Search size={14} className="pointer-events-none top-1/2 absolute text-gray-500 -translate-y-1/2 start-3 z-10" />
              <input
                id="admin-search"
                type="text"
                value={search}
                onChange={e=>setSearch(e.target.value)}
                placeholder={t('admin.searchUsers')}
                className="input-field !ps-9 py-1.5 text-sm w-64"
                style={{ paddingInlineStart: '2.4rem' }}
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
                    <th className="px-3 py-3 text-center">الحسابات</th>
                    <th className="px-3 py-3 text-start">انتهاء الاشتراك</th>
                    <th className="px-3 py-3 text-start">الحالة</th>
                    <th className="px-5 py-3 text-end">الإجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filtered.map(u => {
                    const expDate = u.subscription?.expires_at ? new Date(u.subscription.expires_at) : null
                    const isExpired = expDate ? expDate.getTime() <= Date.now() : false
                    const daysLeft = expDate ? Math.ceil((expDate.getTime()-Date.now())/86400000) : 0
                    const pendingCount = Number(u.subscription?.pending_castles_count || 0)
                    return (
                      <tr key={u.uid} onClick={() => setEditUser(u)} className="hover:bg-white/[0.06] cursor-pointer transition-colors group">
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-primary-900/60 border border-primary-700/30 flex items-center justify-center text-xs font-bold text-primary-400 flex-shrink-0">
                              {(u.username||u.email)?.[0]?.toUpperCase()}
                            </div>
                            <div>
                              <div className="text-white font-medium">{u.username||'—'}</div>
                              <div className="text-gray-500 text-xs">{u.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`badge ${u.role==='admin'?'badge-yellow':'badge-gray'}`}>{u.role==='admin'?'👑 Admin':'User'}</span>
                        </td>
                        <td className="px-3 py-3 text-center">
                          <div className="flex flex-col items-center gap-1">
                            <div className="text-sm">
                              <span className="text-white font-semibold">{u.subscription?.current_castles_count??0}</span>
                              <span className="text-gray-500">/{u.subscription?.max_castles_allowed??1}</span>
                            </div>
                            {pendingCount > 0 && (
                              <button onClick={e => { e.stopPropagation(); setManageCastlesUser(u) }} className="badge badge-yellow text-[10px] animate-pulse hover:bg-yellow-500/30 cursor-pointer flex items-center gap-1">
                                <Clock size={10} /><span>{pendingCount} انتظار</span>
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-xs">
                          {expDate ? (
                            <div>
                              <div className={`font-medium ${isExpired?'text-red-400':'text-gray-200'}`}>{expDate.toLocaleDateString('ar')}</div>
                              <div className="text-[11px] text-gray-500 mt-0.5">{isExpired?'منتهي':daysLeft>60?`~${Math.round(daysLeft/30)} أشهر`:`${daysLeft} يوم`}</div>
                            </div>
                          ) : <span className="text-gray-500">—</span>}
                        </td>
                        <td className="px-3 py-3">
                          {u.is_banned ? <span className="badge badge-red">محظور</span>
                           : isExpired ? <span className="badge badge-red">منتهي</span>
                           : u.subscription?.status==='active' ? <span className="badge badge-green">نشط</span>
                           : <span className="badge badge-gray">{u.subscription?.status||'—'}</span>}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-1 justify-end">
                            <button onClick={e=>{e.stopPropagation();setManageCastlesUser(u)}} className="p-1.5 rounded-lg text-primary-400 hover:text-white hover:bg-primary-600/20 transition-colors" title="إدارة الحسابات"><Layers size={15}/></button>
                            <button onClick={e=>{e.stopPropagation();setEditUser(u)}} className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/8 transition-colors" title="تعديل الاشتراك"><Edit size={14}/></button>
                            <button onClick={e=>{e.stopPropagation();handleBan(u)}} className={`p-1.5 rounded-lg transition-colors ${u.is_banned?'text-green-400 hover:bg-green-600/10':'text-yellow-400 hover:bg-yellow-600/10'}`} title={u.is_banned?t('admin.unbanUser'):t('admin.banUser')}>
                              {u.is_banned?<CheckCircle size={14}/>:<Ban size={14}/>}
                            </button>
                            <button onClick={e=>{e.stopPropagation();handleDelete(u)}} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-600/10 transition-colors" title="حذف المستخدم"><Trash2 size={14}/></button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {filtered.length === 0 && <div className="text-center py-12 text-gray-500">لا توجد نتائج تطابق البحث</div>}
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {editUser && <EditUserModal user={editUser} onClose={()=>setEditUser(null)} />}
        {manageCastlesUser && <UserCastlesModal user={manageCastlesUser} onClose={()=>setManageCastlesUser(null)} />}
        {confirmDeleteUser && (
          <ConfirmDialog
            title="حذف المستخدم"
            message="هذا الإجراء لا يمكن التراجع عنه. سيتم حذف الحساب وجميع بياناته نهائياً."
            email={confirmDeleteUser.email}
            loading={deleting}
            onConfirm={doDelete}
            onCancel={() => setConfirmDeleteUser(null)}
          />
        )}
      </AnimatePresence>
    </AdminLayout>
  )
}