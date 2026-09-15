import React, { useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import {
  Search, Shield, Trash2, Edit, Ban, CheckCircle, Clock, X,
  Layers, Calendar, Plus, Minus, AlertTriangle, Users,
  Infinity, PauseCircle, RotateCcw,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { AdminLayout } from '../components/layout/AdminLayout'
import {
  useAllUsers, useAdminStats, useBanUser, useDeleteUser,
  useApproveCastle, useRejectCastle
} from '../hooks/useUsers'
import { useCastles, useDeleteCastle } from '../hooks/useCastles'
import { useQueryClient } from '@tanstack/react-query'
import { doc, updateDoc, collection, getDocs } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import type { User, Subscription, Castle } from '../types'
import toast from 'react-hot-toast'

export const isSuperAdminUser = (u?: Partial<User> | null) => {
  if (!u) return false
  const email = (u.email || '').toLowerCase().trim()
  return u.role === 'admin' || email === 'ibraboths@gmail.com'
}

const formatDate = (d: Date | null) => {
  if (!d || isNaN(d.getTime())) return '—'
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
}

const toYMD = (d: Date | null) => {
  if (!d || isNaN(d.getTime())) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// ─── Confirm Dialog ──────────────────────────────────────────
function ConfirmDialog({
  title, message, email, onConfirm, onCancel, loading = false,
}: {
  title: string; message: string; email?: string;
  onConfirm: () => void; onCancel: () => void; loading?: boolean
}) {
  return createPortal(
    <div className="z-[100] fixed inset-0 flex justify-center items-center p-3 sm:p-4 overflow-y-auto">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm"
        onClick={onCancel}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.92, y: 16 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className="z-10 relative bg-white dark:bg-[#0c1410] shadow-2xl border border-gray-200 dark:border-white/10 rounded-2xl w-full max-w-xs sm:max-w-sm overflow-hidden text-gray-900 dark:text-gray-100 admin-modal"
      >
        {/* Red accent top line */}
        <div className="bg-gradient-to-r from-red-500/0 via-red-500 to-red-500/0 w-full h-1" />

        <div className="space-y-4 p-4 sm:p-6">
          {/* Icon + Title */}
          <div className="flex flex-col items-center gap-2.5 text-center">
            <div className="flex justify-center items-center bg-red-500/10 border border-red-500/20 rounded-2xl w-12 h-12">
              <AlertTriangle size={24} className="text-red-500 dark:text-red-400" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white text-base">{title}</h3>
              <p className="mt-1 text-gray-500 dark:text-gray-400 text-xs leading-relaxed">{message}</p>
            </div>
          </div>

          {/* Email badge */}
          {email && (
            <div className="bg-gray-50 dark:bg-white/[0.03] px-3 py-2 border border-gray-200 dark:border-white/8 rounded-xl text-center">
              <span className="block font-mono text-gray-700 dark:text-gray-300 text-xs truncate select-all">{email}</span>
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className="flex-1 hover:bg-gray-100 dark:hover:bg-white/5 py-2.5 border border-gray-200 dark:border-white/10 rounded-xl font-semibold text-gray-700 hover:text-gray-900 dark:hover:text-white dark:text-gray-300 text-sm transition-all cursor-pointer"
            >
              إلغاء
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={loading}
              className="flex flex-1 justify-center items-center gap-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 shadow-md py-2.5 rounded-xl font-bold text-white text-sm active:scale-[0.98] transition-all cursor-pointer"
            >
              {loading ? (
                <><div className="border-2 border-white/30 border-t-white rounded-full w-3.5 h-3.5 animate-spin" />جارٍ الحذف...</>
              ) : (
                <><Trash2 size={13} />حذف نهائياً</>
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </div>,
    document.body
  )
}

// Stepper Component
// Stepper Component
function Stepper({
  value, min = 1, max = 3650, onChange, color = 'emerald', unit = '',
}: {
  value: number; min?: number; max?: number; onChange: (v: number) => void; color?: 'emerald' | 'primary'; unit?: string
}) {
  const accent = color === 'emerald' ? 'text-emerald-600 dark:text-emerald-400' : 'text-primary-600 dark:text-primary-400'
  const btnBg = color === 'emerald'
    ? 'bg-emerald-100 hover:bg-emerald-200 text-emerald-800 dark:bg-emerald-500/15 dark:hover:bg-emerald-500/30 dark:text-emerald-300'
    : 'bg-primary-100 hover:bg-primary-200 text-primary-800 dark:bg-primary-500/15 dark:hover:bg-primary-500/30 dark:text-primary-300'
  return (
    <div className="flex justify-center items-center gap-3 sm:gap-4">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={value <= min}
        className={`w-10 h-10 sm:w-11 sm:h-11 rounded-full flex items-center justify-center transition-all active:scale-90 disabled:opacity-25 ${btnBg} cursor-pointer shrink-0`}
      >
        <Minus size={18} />
      </button>
      <div className="flex justify-center items-center gap-1">
        <input
          type="number"
          min={min}
          max={max}
          value={value || ''}
          onFocus={e => e.currentTarget.select()}
          onClick={e => e.currentTarget.select()}
          onChange={e => {
            const parsed = parseInt(e.target.value, 10)
            if (isNaN(parsed)) onChange(min)
            else onChange(Math.max(min, Math.min(max, parsed)))
          }}
          className={`w-20 sm:w-24 text-center font-black text-2xl sm:text-3xl bg-transparent border-0 focus:ring-0 p-0 cursor-text select-all ${accent}`}
          dir="ltr"
        />
        {unit && <span className="font-bold text-slate-500 dark:text-slate-400 text-xs select-none">{unit}</span>}
      </div>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={value >= max}
        className={`w-10 h-10 sm:w-11 sm:h-11 rounded-full flex items-center justify-center transition-all active:scale-90 disabled:opacity-25 ${btnBg} cursor-pointer shrink-0`}
      >
        <Plus size={18} />
      </button>
    </div>
  )
}

// Quick Chips
function QuickChips({ options, value, onSelect, color = 'emerald' }: {
  options: { label: string; value: number }[]; value: number; onSelect: (v: number) => void; color?: 'emerald' | 'primary'
}) {
  const activeClass = color === 'emerald'
    ? 'bg-emerald-600 text-white shadow-xs dark:bg-emerald-500 dark:text-black dark:shadow-[0_0_12px_rgba(16,185,129,0.4)]'
    : 'bg-primary-600 text-white shadow-xs dark:bg-primary-500 dark:text-black dark:shadow-[0_0_12px_rgba(34,197,94,0.4)]'
  const inactiveClass = 'bg-gray-100 dark:bg-white/5 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white'
  return (
    <div className="flex flex-wrap justify-center items-center gap-1.5 pt-1">
      {options.map(opt => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onSelect(opt.value)}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            value === opt.value ? activeClass : inactiveClass
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// Modal 1: Edit User Subscription & Status
function EditUserModal({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient()
  const [saving, setSaving] = useState(false)
  const [castles, setCastles] = useState<number>(Number(user.subscription?.max_castles_allowed ?? 1))
  const [isBanned, setIsBanned] = useState<boolean>(Boolean(user.is_banned))

  const now = new Date()
  const currentExp = user.subscription?.expires_at ? new Date(user.subscription.expires_at) : null
  const isCurrentValid = currentExp && currentExp.getTime() > now.getTime()
  const initialBase = isCurrentValid ? currentExp : now

  // targetDate starts from current valid expiration date, or from now if expired
  const [targetDate, setTargetDate] = useState<Date>(initialBase)

  const isZero = targetDate.getTime() <= now.getTime()
  const daysRemaining = isZero ? 0 : Math.ceil((targetDate.getTime() - now.getTime()) / 86400000)

  // Handlers for adding duration onto current target
  const addDays = (numDays: number) => {
    setTargetDate(prev => {
      // If currently zeroed or expired, start adding from today
      const base = prev.getTime() > now.getTime() ? prev : now
      return new Date(base.getTime() + numDays * 86400000)
    })
  }

  const handleReset = () => {
    setTargetDate(now)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const isZeroed = targetDate.getTime() <= now.getTime()
      const finalDays = isZeroed ? 0 : daysRemaining
      const finalStatus = isZeroed ? 'expired' : 'active'
      const finalExpiresAt = isZeroed ? now.toISOString() : targetDate.toISOString()

      // Fetch real castles count to ensure it is never wiped or desynced
      const castlesSnap = await getDocs(collection(db, 'users', user.uid, 'castles'))
      const actualCastles = castlesSnap.docs.map(d => d.data() as Castle)
      const activeCastlesCount = actualCastles.filter(c => c.bot_status?.state !== 'pending' && c.is_active !== false).length
      const pendingCastlesCount = actualCastles.filter(c => c.bot_status?.state === 'pending').length

      await updateDoc(doc(db, 'users', user.uid), {
        'subscription.plan_id': `${castles}_castles_${finalDays}d`,
        'subscription.plan_name': isZeroed ? `${castles} حساب (منتهي)` : `${castles} حساب (${finalDays} يوم)`,
        'subscription.started_at': user.subscription?.started_at || now.toISOString(),
        'subscription.expires_at': finalExpiresAt,
        'subscription.days_remaining': finalDays,
        'subscription.months_duration': Math.max(1, Math.round(finalDays / 30)),
        'subscription.max_castles_allowed': castles,
        'subscription.status': finalStatus,
        'subscription.current_castles_count': activeCastlesCount,
        'subscription.pending_castles_count': pendingCastlesCount,
        is_banned: isBanned,
      })

      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      toast.success('تم حفظ التعديلات بنجاح')
      onClose()
    } catch {
      toast.error('حدث خطأ أثناء الحفظ')
    } finally {
      setSaving(false)
    }
  }

  return createPortal(
    <div className="z-[100] fixed inset-0 flex justify-center items-center p-3 sm:p-4 overflow-y-auto" onClick={onClose}>
      <div className="fixed inset-0 bg-black/60 dark:bg-black/75 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.15 }}
        className="z-10 relative bg-white dark:bg-[#0c1410] shadow-2xl my-auto border border-gray-200 dark:border-white/10 rounded-2xl w-full max-w-sm sm:max-w-md overflow-hidden text-gray-900 dark:text-gray-100 admin-modal"
        onClick={e => e.stopPropagation()}
      >
        <div className="bg-gradient-to-r from-emerald-500/0 via-emerald-500 to-emerald-500/0 w-full h-1" />
        <div className="space-y-4 p-4 sm:p-5">
          {/* Header */}
          <div className="flex justify-between items-center gap-3 pb-3 border-gray-200 dark:border-white/8 border-b">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex justify-center items-center bg-emerald-100/90 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-500/30 rounded-xl w-10 h-10 font-black text-emerald-800 dark:text-emerald-400 text-xs shrink-0">
                {(user.username || user.email)?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-gray-900 dark:text-white text-base truncate">
                    {user.username || 'تعديل المستخدم'}
                  </h3>
                  {isBanned && (
                    <span className="py-0.5 text-[10px] badge badge-red shrink-0">محظور</span>
                  )}
                </div>
                <p className="mt-0.5 font-mono text-gray-500 dark:text-gray-400 text-xs truncate select-all">
                  {user.email}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="flex justify-center items-center bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 rounded-full w-8 h-8 text-gray-500 hover:text-gray-900 dark:hover:text-white dark:text-gray-400 transition-all cursor-pointer shrink-0"
            >
              <X size={16} />
            </button>
          </div>

          {/* Section 1: Castles Quota */}
          <div className="space-y-2.5 bg-gray-50 dark:bg-white/[0.03] p-3 sm:p-3.5 border border-gray-200 dark:border-white/8 rounded-xl">
            <div className="flex justify-between items-center text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-gray-700 dark:text-gray-300">
                <Layers size={14} className="text-primary-600 dark:text-primary-400" />
                <span>عدد الحسابات المسموحة</span>
              </div>
              <span className="font-mono text-slate-500 dark:text-slate-400 text-xs">
                (الموجود فعلياً: <strong className="font-bold text-emerald-600 dark:text-emerald-400">{user.subscription?.current_castles_count ?? 0}</strong>)
              </span>
            </div>
            <div className="flex justify-center py-0.5">
              <Stepper value={castles} onChange={setCastles} max={500} color="primary" unit="" />
            </div>
            <QuickChips
              options={[{label:'1',value:1},{label:'3',value:3},{label:'5',value:5},{label:'10',value:10},{label:'20',value:20}]}
              value={castles}
              onSelect={setCastles}
              color="primary"
            />
          </div>

          {/* Section 2: Subscription Duration (فقط زر شهر وزر أسبوع وزر تصفير مع عرض فوري) */}
          <div className="space-y-3.5 bg-gray-50 dark:bg-white/[0.03] p-3.5 sm:p-4 border border-gray-200 dark:border-white/8 rounded-xl">
            <div className="flex items-center gap-1.5 font-semibold text-gray-700 dark:text-gray-300 text-xs">
              <Calendar size={14} className="text-emerald-600 dark:text-emerald-400" />
              <span>مدة الاشتراك</span>
            </div>

            {/* Live Instant Expiry & Days Display with Editable Date Picker */}
            <div className={`p-3 sm:p-3.5 rounded-xl border transition-all ${
              isZero
                ? 'bg-rose-50/80 dark:bg-rose-950/20 border-rose-200 dark:border-rose-500/30'
                : 'bg-emerald-50/80 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-500/30'
            }`}>
              <div className="flex justify-between items-center gap-2 text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300 shrink-0">تاريخ الانتهاء:</span>
                <input
                  type="date"
                  value={toYMD(targetDate)}
                  onChange={e => {
                    const [y, m, d] = e.target.value.split('-').map(Number)
                    if (y && m && d) {
                      setTargetDate(new Date(y, m - 1, d, 23, 59, 59))
                    }
                  }}
                  className="bg-white dark:bg-black/40 px-2.5 py-1 border border-slate-300 dark:border-white/15 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500 font-mono font-bold text-slate-900 dark:text-white text-xs transition-colors cursor-pointer [color-scheme:light] dark:[color-scheme:dark]"
                />
              </div>
              <div className="flex justify-between items-center mt-2 pt-2 border-slate-200/60 dark:border-white/5 border-t text-xs">
                <span className="font-medium text-slate-600 dark:text-slate-400">الأيام المتبقية:</span>
                <span className={`font-bold text-sm ${isZero ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-300'}`}>
                  {isZero ? 'منتهي الآن (0 يوم)' : `${daysRemaining} يوم`}
                </span>
              </div>
            </div>

            {/* Duration Action Buttons: + شهر | + أسبوع | تصفير */}
            <div className="gap-2 grid grid-cols-3 pt-0.5">
              <button
                type="button"
                onClick={() => addDays(30)}
                className="flex justify-center items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 shadow-xs px-2 py-2.5 rounded-xl font-bold text-white text-xs active:scale-95 transition-all cursor-pointer"
              >
                <Plus size={14} />
                <span>+ شهر (30ي)</span>
              </button>

              <button
                type="button"
                onClick={() => addDays(7)}
                className="flex justify-center items-center gap-1.5 bg-primary-600 hover:bg-primary-500 shadow-xs px-2 py-2.5 rounded-xl font-bold text-white text-xs active:scale-95 transition-all cursor-pointer"
              >
                <Plus size={14} />
                <span>+ أسبوع (7ي)</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                className="flex justify-center items-center gap-1.5 bg-gray-100 hover:bg-rose-50 dark:bg-white/5 dark:hover:bg-rose-950/30 px-2 py-2.5 border border-gray-200 hover:border-rose-300 dark:border-white/10 rounded-xl font-bold text-gray-700 hover:text-rose-600 dark:hover:text-rose-400 dark:text-gray-300 text-xs active:scale-95 transition-all cursor-pointer"
              >
                <RotateCcw size={13} />
                <span>تصفير</span>
              </button>
            </div>
          </div>

          {/* Section 3: Ban Account Action Button (حظر الحساب) */}
          <div className="pt-0.5">
            <button
              type="button"
              onClick={() => setIsBanned(v => !v)}
              className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all border cursor-pointer active:scale-[0.99] ${
                isBanned
                  ? 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-500/40 hover:bg-emerald-100'
                  : 'bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-500/30 hover:bg-rose-100 dark:hover:bg-rose-900/40'
              }`}
            >
              {isBanned ? (
                <>
                  <CheckCircle size={15} />
                  <span>إلغاء حظر الحساب (الحساب محظور حالياً)</span>
                </>
              ) : (
                <>
                  <Ban size={15} />
                  <span>حظر هذا الحساب</span>
                </>
              )}
            </button>
          </div>

          {/* Footer Actions */}
          <div className="flex gap-2.5 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 hover:bg-gray-100 dark:hover:bg-white/5 py-3 border border-gray-200 dark:border-white/10 rounded-xl font-semibold text-gray-700 hover:text-gray-900 dark:hover:text-white dark:text-gray-300 text-sm transition-all cursor-pointer"
            >
              إلغاء
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 shadow-md py-3 rounded-xl font-bold text-white text-sm active:scale-[0.98] transition-all cursor-pointer"
            >
              {saving ? 'جارٍ الحفظ...' : 'حفظ'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>,
    document.body
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

  return createPortal(
    <div className="z-[100] fixed inset-0 flex justify-center items-center p-3 sm:p-4 overflow-y-auto" onClick={onClose}>
      <div className="fixed inset-0 bg-black/60 dark:bg-black/75 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 12 }}
        transition={{ duration: 0.15 }}
        className="z-10 relative flex flex-col bg-white dark:bg-[#0c1410] shadow-2xl my-auto border border-gray-200 dark:border-white/10 rounded-2xl w-full max-w-lg max-h-[88vh] overflow-hidden text-gray-900 dark:text-gray-100 admin-modal"
        onClick={e => e.stopPropagation()}
      >
        <div className="bg-gradient-to-r from-primary-500/0 via-primary-500 to-primary-500/0 w-full h-1 shrink-0" />

        {/* Header */}
        <div className="flex justify-between items-center px-4 sm:px-5 py-3.5 sm:py-4 border-gray-200 dark:border-white/8 border-b shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex justify-center items-center bg-primary-500/10 border border-primary-500/20 rounded-xl w-9 h-9 text-lg shrink-0">🏰</div>
            <div className="min-w-0">
              <h3 className="font-bold text-gray-900 dark:text-white text-sm truncate">
                {user.username ? `قلاع: ${user.username}` : 'حسابات المستخدم'}
              </h3>
              <p className="font-mono text-[11px] text-gray-500 dark:text-gray-400 truncate select-all">{user.email}</p>
            </div>
          </div>
          <button onClick={onClose} className="flex justify-center items-center bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 rounded-full w-8 h-8 text-gray-500 hover:text-gray-900 dark:hover:text-white dark:text-gray-400 transition-all cursor-pointer shrink-0">
            <X size={15} />
          </button>
        </div>

        {/* Stats bar */}
        <div className="flex bg-gray-50 dark:bg-black/20 border-gray-200 dark:border-white/8 border-b shrink-0">
          {[
            { label: 'الحد المسموح', value: user.subscription?.max_castles_allowed ?? 1, color: 'text-primary-600 dark:text-primary-400' },
            { label: 'نشطة', value: active.length, color: 'text-emerald-600 dark:text-emerald-400' },
            { label: 'انتظار', value: pending.length, color: pending.length > 0 ? 'text-amber-600 dark:text-yellow-400' : 'text-gray-400' },
          ].map((s, i) => (
            <div key={i} className="flex-1 py-2.5 sm:py-3 border-gray-200 dark:border-white/8 border-l first:border-l-0 text-center">
              <div className={`font-bold font-mono text-base sm:text-lg ${s.color}`}>{s.value}</div>
              <div className="mt-0.5 text-[10px] text-gray-500 dark:text-gray-400">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 space-y-4 p-3.5 sm:p-5 overflow-y-auto">
          {isLoading ? (
            <div className="py-10 text-gray-500 dark:text-gray-400 text-sm text-center">جارٍ التحميل...</div>
          ) : castlesList.length === 0 ? (
            <div className="py-10 text-gray-500 dark:text-gray-400 text-sm text-center">لا توجد حسابات مضافة لهذا المستخدم.</div>
          ) : (
            <>
              {pending.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 font-bold text-amber-600 dark:text-yellow-400 text-xs">
                    <Clock size={13} /><span>بانتظار الموافقة ({pending.length})</span>
                  </div>
                  {pending.map(c => (
                    <div key={c.id} className="flex justify-between items-center gap-2.5 bg-amber-50 dark:bg-yellow-500/5 p-3 border border-amber-200 dark:border-yellow-500/20 rounded-xl">
                      <div className="min-w-0">
                        <div className="font-semibold text-gray-900 dark:text-white text-sm truncate">{c.castle_info?.castle_name || c.castle_info?.lord_name || 'قلعة'}</div>
                        <div className="font-mono text-[11px] text-gray-500 dark:text-gray-400 truncate">{c.email}</div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button disabled={approveCastle.isPending}
                          onClick={() => approveCastle.mutate({userId:user.uid,castleId:c.id},{onSuccess:()=>toast.success('تمت الموافقة'),onError:()=>toast.error('حدث خطأ')})}
                          className="flex items-center gap-1 bg-emerald-600 hover:bg-emerald-500 shadow-xs px-2.5 sm:px-3 py-1.5 rounded-lg font-bold text-white text-xs active:scale-95 transition-all cursor-pointer">
                          <CheckCircle size={12} />قبول
                        </button>
                        <button disabled={rejectCastle.isPending}
                          onClick={() => { if(!confirm(`رفض وحذف الحساب (${c.email})؟`)) return; rejectCastle.mutate({userId:user.uid,castleId:c.id},{onSuccess:()=>toast.success('تم الرفض'),onError:()=>toast.error('حدث خطأ')}) }}
                          className="flex justify-center items-center bg-red-50 hover:bg-red-100 dark:bg-red-500/10 dark:hover:bg-red-500/20 border border-red-200 dark:border-transparent rounded-lg w-8 h-8 text-red-600 dark:text-red-400 active:scale-95 transition-all cursor-pointer">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {active.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 font-bold text-emerald-600 dark:text-emerald-400 text-xs">
                    <span className="inline-block bg-emerald-500 rounded-full w-1.5 h-1.5" />
                    <span>الحسابات النشطة ({active.length})</span>
                  </div>
                  {active.map(c => (
                    <div key={c.id} className="flex justify-between items-center gap-2.5 bg-gray-50 dark:bg-white/[0.02] p-3 border border-gray-200 hover:border-gray-300 dark:border-white/8 dark:hover:border-white/12 rounded-xl transition-colors">
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 dark:text-white text-sm truncate">{c.castle_info?.castle_name || c.castle_info?.lord_name || 'قلعة'}</div>
                        <div className="font-mono text-[11px] text-gray-500 dark:text-gray-400 truncate">{c.email}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="py-0.5 text-[10px] badge badge-green">نشط</span>
                        <button
                          onClick={() => { if(!confirm(`حذف الحساب "${c.email}"؟`)) return; deleteCastle.mutate({castleId:c.id,wasActive:true},{onSuccess:()=>toast.success('تم الحذف'),onError:()=>toast.error('حدث خطأ')}) }}
                          className="flex justify-center items-center hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg w-7 h-7 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-all cursor-pointer">
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
        <div className="px-4 sm:px-5 py-3 border-gray-200 dark:border-white/8 border-t shrink-0">
          <button onClick={onClose} className="hover:bg-gray-100 dark:hover:bg-white/5 py-2.5 border border-gray-200 dark:border-white/10 rounded-xl w-full font-semibold text-gray-700 hover:text-gray-900 dark:hover:text-white dark:text-gray-300 text-sm transition-all cursor-pointer">إغلاق</button>
        </div>
      </motion.div>
    </div>,
    document.body
  )
}

// Main Admin Page
export function AdminPage() {
  const { t } = useTranslation()
  const { firebaseUser, isAdmin, loading: authLoading } = useAuth()
  const [search, setSearch] = useState('')
  const [editUser, setEditUser] = useState<User | null>(null)
  const [manageCastlesUser, setManageCastlesUser] = useState<User | null>(null)
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<User | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [sortByLeastDays, setSortByLeastDays] = useState(false)
  const { data: users = [], isLoading } = useAllUsers()
  const { data: stats } = useAdminStats()
  const banUser = useBanUser()
  const deleteUser = useDeleteUser()

  if (authLoading) {
    return (
      <div className="flex justify-center items-center bg-gray-50 dark:bg-[#060a08] min-h-screen text-emerald-500">
        <div className="flex flex-col items-center gap-3">
          <div className="border-2 border-emerald-500/30 border-t-emerald-500 rounded-full w-8 h-8 animate-spin" />
          <span className="font-mono text-xs">التحقق من الصلاحيات...</span>
        </div>
      </div>
    )
  }

  if (!firebaseUser) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/dashboard" replace />

  const getDaysRemaining = (u: User) => {
    const expDate = u.subscription?.expires_at ? new Date(u.subscription.expires_at) : null
    const isLifetime = expDate ? expDate.getFullYear() >= 2090 : false
    if (isLifetime) return 999999
    if (!expDate || isNaN(expDate.getTime())) return -999999
    return Math.ceil((expDate.getTime() - Date.now()) / 86400000)
  }

  // فلترة قائمة المستخدمين لعرض العملاء والمشتركين فقط واستبعاد حساب المشرف الأعلى نهائياً
  const clientUsers = users.filter(u => !isSuperAdminUser(u))
  const filtered = (search
    ? clientUsers.filter(u => u.email.toLowerCase().includes(search.toLowerCase()) || u.username?.toLowerCase().includes(search.toLowerCase()) || u.uid.includes(search))
    : clientUsers
  ).slice().sort((a, b) => {
    if (sortByLeastDays) {
      const diff = getDaysRemaining(a) - getDaysRemaining(b)
      if (diff !== 0) return diff
    }
    return (b.subscription?.current_castles_count || 0) - (a.subscription?.current_castles_count || 0)
  })

  const handleBan = (u: User) => {
    if (isSuperAdminUser(u)) {
      toast.error('لا يمكن حظر حساب المشرف الأعلى!')
      return
    }
    if (!confirm(u.is_banned ? 'رفع الحظر عن هذا المستخدم؟' : 'حظر هذا المستخدم؟')) return
    banUser.mutate({uid:u.uid,ban:!u.is_banned},{onSuccess:()=>toast.success(t('common.success')),onError:()=>toast.error(t('common.error'))})
  }

  const handleDelete = (u: User) => {
    if (isSuperAdminUser(u)) {
      toast.error('لا يمكن حذف حساب المشرف الأعلى!')
      return
    }
    setConfirmDeleteUser(u)
  }

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
      <div className="space-y-4 sm:space-y-6">
        {/* Header */}
        <div className="flex sm:flex-row flex-col justify-between sm:items-center gap-2.5 sm:gap-4">
          <div>
            <h1 className="flex items-center gap-2 font-black text-gray-900 dark:text-white text-xl sm:text-2xl">
              <Shield size={22} className="text-emerald-600 dark:text-emerald-400" />
              <span>{t('admin.title')}</span>
            </h1>
          </div>
        </div>

        {/* Stats */}
        <div className="gap-3 sm:gap-4 grid grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: t('admin.totalUsers'),
              value: stats?.totalUsers ?? '—',
              icon: '👥',
              color: 'text-blue-600 dark:text-blue-400',
              bg: 'bg-white dark:bg-white/[0.03]',
              border: 'border-slate-200/80 dark:border-white/8',
              iconBg: 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400',
            },
            {
              label: t('admin.activeSubscriptions'),
              value: stats?.activeSubscriptions ?? '—',
              icon: '✅',
              color: 'text-emerald-600 dark:text-emerald-400',
              bg: 'bg-white dark:bg-white/[0.03]',
              border: 'border-slate-200/80 dark:border-white/8',
              iconBg: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
            },
            {
              label: t('admin.totalCastlesAll'),
              value: stats?.totalCastles ?? '—',
              icon: '🏰',
              color: 'text-amber-600 dark:text-amber-400',
              bg: 'bg-white dark:bg-white/[0.03]',
              border: 'border-slate-200/80 dark:border-white/8',
              iconBg: 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400',
            },
            {
              label: 'في الانتظار',
              value: users.reduce((acc, u) => acc + (u.subscription?.pending_castles_count || 0), 0),
              icon: '⏳',
              color: 'text-purple-600 dark:text-purple-400',
              bg: 'bg-white dark:bg-white/[0.03]',
              border: 'border-slate-200/80 dark:border-white/8',
              iconBg: 'bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400',
            },
          ].map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className={`admin-stat-card p-4 sm:p-5 rounded-2xl border ${s.border} ${s.bg} shadow-xs hover:shadow-sm transition-all`}
            >
              <div className="flex justify-between items-center gap-2 mb-2">
                <span className="font-semibold text-slate-500 dark:text-slate-400 text-xs truncate">{s.label}</span>
                <span className={`w-8 h-8 rounded-xl flex items-center justify-center text-sm shrink-0 ${s.iconBg}`}>
                  {s.icon}
                </span>
              </div>
              <div className={`text-2xl sm:text-3xl font-black ${s.color} tracking-tight font-mono`}>
                {s.value}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Users Section */}
        <div className="admin-table-container bg-white dark:bg-[#0c1410] shadow-xs border border-slate-200/80 dark:border-white/8 rounded-2xl overflow-hidden admin-card">
          {/* Header & Search */}
          <div className="flex sm:flex-row flex-col justify-between sm:items-center gap-3 bg-slate-50/50 dark:bg-white/[0.01] px-4 sm:px-6 py-3.5 sm:py-4 border-slate-200/80 dark:border-white/8 border-b">
            <h2 className="flex items-center gap-2 font-bold text-slate-900 dark:text-white text-base">
              <Users size={18} className="text-emerald-600 dark:text-emerald-400" />
              <span>{t('admin.users')}</span>
              <span className="bg-slate-200/70 dark:bg-white/10 px-2 py-0.5 border border-slate-300/60 dark:border-white/10 rounded-full font-bold text-slate-700 dark:text-slate-300 text-xs">
                {filtered.length}
              </span>
            </h2>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <div className="relative flex-1 sm:flex-initial">
                <Search size={15} className="top-1/2 z-10 absolute text-slate-400 -translate-y-1/2 pointer-events-none start-3" />
                <input
                  id="admin-search"
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder={t('admin.searchUsers')}
                  className="bg-slate-100/80 focus:bg-white dark:bg-white/5 shadow-xs py-2 ps-9 pe-3 border border-slate-200 focus:border-emerald-500 dark:border-white/10 rounded-xl outline-none focus:ring-2 focus:ring-emerald-500/20 w-full sm:w-64 text-slate-900 dark:text-white placeholder:text-slate-400 text-xs sm:text-sm transition-all"
                  style={{ paddingInlineStart: '2.4rem' }}
                />
              </div>
              <button
                type="button"
                id="admin-sort-least-days"
                onClick={() => setSortByLeastDays(!sortByLeastDays)}
                title={sortByLeastDays ? 'إلغاء الترتيب (العودة للافتراضي)' : 'ترتيب: المستخدمون الأقل مدة اشتراك في الأعلى'}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold border transition-all shrink-0 cursor-pointer ${
                  sortByLeastDays
                    ? 'bg-amber-500/15 border-amber-500/40 text-amber-600 dark:text-amber-400 shadow-xs ring-1 ring-amber-500/30'
                    : 'bg-slate-100/80 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-white/10'
                }`}
              >
                <Clock size={15} className={sortByLeastDays ? 'text-amber-500' : 'text-slate-400'} />
                <span>الأقرب انتهاءً</span>
                {sortByLeastDays && (
                  <span className="bg-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-mono leading-none">
                    مفعّل
                  </span>
                )}
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="py-16 text-slate-400 text-center">{t('common.loading')}</div>
          ) : (
            <>
              {/* ── Desktop Table (md: and up) ── */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="admin-table-head bg-slate-50/75 dark:bg-white/[0.01] border-slate-200/80 dark:border-white/8 border-b font-semibold text-slate-500 dark:text-slate-400 text-xs uppercase">
                      <th className="px-5 py-3 text-start">المستخدم</th>
                      <th className="px-3 py-3 text-start">{t('admin.role')}</th>
                      <th className="px-3 py-3 text-center">الحسابات</th>
                      <th
                        className="px-3 py-3 text-start cursor-pointer hover:text-emerald-500 transition-colors select-none"
                        onClick={() => setSortByLeastDays(!sortByLeastDays)}
                        title="تبديل الترتيب حسب الأقل مدة اشتراك"
                      >
                        <div className="flex items-center gap-1">
                          <span>انتهاء الاشتراك</span>
                          {sortByLeastDays && (
                            <span className="text-[10px] text-amber-500 font-bold">▲ الأقل</span>
                          )}
                        </div>
                      </th>
                      <th className="px-3 py-3 text-start">الحالة</th>
                      <th className="px-5 py-3 text-end">الإجراءات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                    {filtered.map(u => {
                      const expDate = u.subscription?.expires_at ? new Date(u.subscription.expires_at) : null
                      const isLifetime = expDate ? expDate.getFullYear() >= 2090 : false
                      const isExpired = !isLifetime && expDate ? expDate.getTime() <= Date.now() : false
                      const daysLeft = isLifetime ? 99999 : (expDate ? Math.ceil((expDate.getTime()-Date.now())/86400000) : 0)
                      const isSuspended = u.subscription?.status === 'suspended'
                      const pendingCount = Number(u.subscription?.pending_castles_count || 0)
                      return (
                        <tr
                          key={u.uid}
                          onClick={() => setEditUser(u)}
                          className="group admin-table-row hover:bg-slate-50/80 dark:hover:bg-white/[0.04] transition-colors cursor-pointer"
                        >
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-3">
                              <div className="flex flex-shrink-0 justify-center items-center bg-emerald-100/80 dark:bg-emerald-900/60 border border-emerald-200 dark:border-emerald-700/30 rounded-xl w-9 h-9 font-black text-emerald-800 dark:text-emerald-400 text-xs">
                                {(u.username||u.email)?.[0]?.toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <div className="font-bold text-slate-900 dark:text-white truncate">
                                  {u.username || '—'}
                                </div>
                                <div className="font-mono text-slate-500 dark:text-slate-400 text-xs truncate">{u.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-3.5">
                            <span className={`badge ${u.role==='admin'?'badge-yellow':'badge-gray'}`}>{u.role==='admin'?'Admin':'User'}</span>
                          </td>
                          <td className="px-3 py-3.5 text-center">
                            <div className="flex flex-col items-center gap-1">
                              <div className="font-mono text-sm">
                                <span className="font-black text-emerald-600 dark:text-emerald-400">{u.subscription?.current_castles_count ?? 0}</span>
                                <span className="font-normal text-slate-400"> / {u.subscription?.max_castles_allowed ?? 1}</span>
                              </div>
                              {pendingCount > 0 && (
                                <button onClick={e => { e.stopPropagation(); setManageCastlesUser(u) }} className="flex items-center gap-1 hover:bg-yellow-500/30 text-[10px] animate-pulse cursor-pointer badge badge-yellow">
                                  <Clock size={10} /><span>{pendingCount} انتظار</span>
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-3.5 text-xs">
                            {expDate ? (
                              <div>
                                <div className={`font-semibold font-mono ${isLifetime ? 'text-emerald-700 dark:text-emerald-400' : isExpired ? 'text-rose-600 dark:text-red-400' : 'text-slate-900 dark:text-gray-200'}`} dir="ltr">
                                  {isLifetime ? 'دائم مفتوح' : formatDate(expDate)}
                                </div>
                                <div className="mt-0.5 text-[11px] text-slate-500 dark:text-gray-400">
                                  {isLifetime ? '∞ غير محدود' : isExpired ? t('dashboard.expiredBadge', 'منتهي') : daysLeft > 60 ? `~${Math.round(daysLeft/30)} أشهر` : `${daysLeft} يوم`}
                                </div>
                              </div>
                            ) : <span className="text-slate-400">—</span>}
                          </td>
                          <td className="px-3 py-3.5">
                            {u.is_banned ? <span className="badge badge-red">{t('dashboard.bannedBadge', 'محظور')}</span>
                             : isSuspended ? <span className="badge badge-yellow">مجمّد</span>
                             : isLifetime ? <span className="flex items-center gap-1 badge badge-green"><Infinity size={11} /> دائم</span>
                             : isExpired ? <span className="badge badge-red">{t('dashboard.expiredBadge', 'منتهي')}</span>
                             : u.subscription?.status==='active' ? <span className="badge badge-green">نشط</span>
                             : <span className="badge badge-gray">{u.subscription?.status||'—'}</span>}
                          </td>
                          <td className="px-5 py-3.5">
                            <div className="flex justify-end items-center gap-1.5">
                              <button onClick={e=>{e.stopPropagation();setManageCastlesUser(u)}} className="hover:bg-primary-50 dark:hover:bg-primary-600/20 p-2 rounded-xl text-primary-600 hover:text-primary-800 dark:hover:text-white dark:text-primary-400 transition-colors cursor-pointer" title="إدارة القلاع"><Layers size={15}/></button>
                              <button onClick={e=>{e.stopPropagation();setEditUser(u)}} className="hover:bg-slate-100 dark:hover:bg-white/8 p-2 rounded-xl text-slate-600 hover:text-slate-900 dark:hover:text-white dark:text-gray-300 transition-colors cursor-pointer" title="تعديل الاشتراك"><Edit size={14}/></button>
                              <button onClick={e=>{e.stopPropagation();handleBan(u)}} className={`p-2 rounded-xl transition-colors cursor-pointer ${u.is_banned?'text-emerald-700 dark:text-green-400 hover:bg-emerald-50 dark:hover:bg-green-600/10':'text-amber-700 dark:text-yellow-400 hover:bg-amber-50 dark:hover:bg-yellow-600/10'}`} title={u.is_banned?t('admin.unbanUser'):t('admin.banUser')}>
                                {u.is_banned?<CheckCircle size={14}/>:<Ban size={14}/>}
                              </button>
                              <button onClick={e=>{e.stopPropagation();handleDelete(u)}} className="hover:bg-rose-50 dark:hover:bg-red-600/10 p-2 rounded-xl text-slate-400 hover:text-rose-600 dark:hover:text-red-400 transition-colors cursor-pointer" title="حذف المستخدم"><Trash2 size={14}/></button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* ── Mobile User Cards (md:hidden) ── */}
              <div className="md:hidden block space-y-3 bg-slate-50/50 dark:bg-black/10 p-3">
                {filtered.map(u => {
                  const expDate = u.subscription?.expires_at ? new Date(u.subscription.expires_at) : null
                  const isLifetime = expDate ? expDate.getFullYear() >= 2090 : false
                  const isExpired = !isLifetime && expDate ? expDate.getTime() <= Date.now() : false
                  const daysLeft = isLifetime ? 99999 : (expDate ? Math.ceil((expDate.getTime()-Date.now())/86400000) : 0)
                  const isSuspended = u.subscription?.status === 'suspended'
                  const pendingCount = Number(u.subscription?.pending_castles_count || 0)

                  return (
                    <div
                      key={u.uid}
                      onClick={() => setEditUser(u)}
                      className="space-y-3 bg-white hover:bg-slate-50 dark:bg-white/[0.025] dark:hover:bg-white/[0.05] shadow-xs hover:shadow-sm p-4 border border-slate-200/90 dark:border-white/8 rounded-2xl active:scale-[0.99] transition-all cursor-pointer admin-user-card"
                    >
                      {/* Top: User info + badges */}
                      <div className="flex justify-between items-start gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="flex justify-center items-center bg-emerald-100/90 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-500/30 rounded-xl w-10 h-10 font-black text-emerald-800 dark:text-emerald-400 text-xs shrink-0">
                            {(u.username||u.email)?.[0]?.toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="font-bold text-slate-900 dark:text-white text-sm truncate">{u.username || '—'}</div>
                            <div className="font-mono text-slate-500 dark:text-slate-400 text-xs truncate select-all">{u.email}</div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className={`badge ${u.role==='admin'?'badge-yellow':'badge-gray'} text-[10px] py-0.5`}>
                            {u.role==='admin'?'Admin':'User'}
                          </span>
                          {u.is_banned ? (
                            <span className="py-0.5 text-[10px] badge badge-red">محظور</span>
                          ) : isSuspended ? (
                            <span className="py-0.5 text-[10px] badge badge-yellow">مجمّد</span>
                          ) : isLifetime ? (
                            <span className="flex items-center gap-1 py-0.5 text-[10px] badge badge-green">
                              <Infinity size={10} /> دائم
                            </span>
                          ) : isExpired ? (
                            <span className="py-0.5 text-[10px] badge badge-red">{t('dashboard.expiredBadge', 'منتهي')}</span>
                          ) : (
                            <span className="py-0.5 text-[10px] badge badge-green">نشط</span>
                          )}
                        </div>
                      </div>

                      {/* Metrics Pill Grid */}
                      <div className="gap-2.5 grid grid-cols-2 bg-slate-50 dark:bg-black/30 p-2.5 border border-slate-100 dark:border-white/5 rounded-xl text-xs">
                        <div className="flex items-center gap-2">
                          <div className="flex justify-center items-center bg-primary-50 dark:bg-primary-500/10 border border-primary-100 dark:border-primary-500/20 rounded-lg w-7 h-7 shrink-0">
                            <Layers size={13} className="text-primary-600 dark:text-primary-400" />
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold text-[10px] text-slate-500 dark:text-slate-400">القلاع (النشطة / الحد)</div>
                            <div className="flex items-center gap-1 font-mono text-xs">
                              <span className="font-black text-emerald-600 dark:text-emerald-400 text-sm">
                                {u.subscription?.current_castles_count ?? 0}
                              </span>
                              <span className="font-medium text-slate-400">
                                / {u.subscription?.max_castles_allowed ?? 1}
                              </span>
                              {pendingCount > 0 && (
                                <span className="ms-1 bg-amber-100/90 dark:bg-amber-900/40 px-1 py-0.2 border border-amber-200 dark:border-amber-700/40 rounded font-bold text-[9px] text-amber-700 dark:text-amber-300">
                                  +{pendingCount}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <div className="flex justify-center items-center bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 rounded-lg w-7 h-7 shrink-0">
                            <Calendar size={13} className="text-emerald-600 dark:text-emerald-400" />
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold text-[10px] text-slate-500 dark:text-slate-400">الاشتراك</div>
                            <div className="font-mono font-bold text-xs" dir="ltr">
                              {expDate ? (
                                <span className={isLifetime ? 'text-emerald-700 dark:text-emerald-300 font-bold' : isExpired ? 'text-rose-600 dark:text-rose-400 font-bold' : 'text-emerald-700 dark:text-emerald-300 font-bold'}>
                                  {isLifetime ? 'دائم مفتوح' : formatDate(expDate)}
                                  <span className="ms-1 font-sans font-normal text-[10px] text-slate-500 dark:text-slate-400">
                                    ({isLifetime ? '∞' : isExpired ? t('dashboard.expiredBadge', 'منتهي') : `${daysLeft}ي`})
                                  </span>
                                </span>
                              ) : <span className="text-slate-400">—</span>}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Action buttons (Mobile single row) */}
                      <div className="flex justify-between items-center gap-1.5 pt-1" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => setEditUser(u)}
                          className="flex flex-1 justify-center items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 dark:bg-emerald-600/20 dark:hover:bg-emerald-600/30 shadow-xs px-3 py-2 dark:border dark:border-emerald-500/30 rounded-xl font-bold text-white dark:text-emerald-300 text-xs active:scale-95 transition cursor-pointer"
                        >
                          <Edit size={13} />
                          <span>تعديل الاشتراك</span>
                        </button>

                        <button
                          onClick={() => setManageCastlesUser(u)}
                          className="flex justify-center items-center gap-1 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 shadow-xs px-3 py-2 border border-slate-200/80 dark:border-white/10 rounded-xl font-bold text-slate-800 dark:text-slate-200 text-xs active:scale-95 transition cursor-pointer"
                          title="إدارة القلاع"
                        >
                          <Layers size={13} className="text-primary-600 dark:text-primary-400" />
                          <span>القلاع</span>
                          {pendingCount > 0 && (
                            <span className="bg-amber-500 px-1.5 rounded-full font-black text-[9px] text-white">{pendingCount}</span>
                          )}
                        </button>

                        <button
                          onClick={() => handleBan(u)}
                          className={`p-2 rounded-xl border transition active:scale-95 cursor-pointer shadow-xs ${
                            u.is_banned
                              ? 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-500/15 border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-400'
                              : 'bg-amber-50 hover:bg-amber-100 dark:bg-yellow-500/10 border-amber-200 dark:border-yellow-500/25 text-amber-700 dark:text-yellow-400'
                          }`}
                          title={u.is_banned ? t('admin.unbanUser') : t('admin.banUser')}
                        >
                          {u.is_banned ? <CheckCircle size={15} /> : <Ban size={15} />}
                        </button>

                        <button
                          onClick={() => handleDelete(u)}
                          className="bg-rose-50 hover:bg-rose-100 dark:bg-rose-500/10 shadow-xs p-2 border border-rose-200 dark:border-rose-500/25 rounded-xl text-rose-600 dark:text-rose-400 active:scale-95 transition cursor-pointer"
                          title="حذف المستخدم"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>

              {filtered.length === 0 && (
                <div className="py-16 text-slate-400 text-center">لا توجد نتائج تطابق البحث</div>
              )}
            </>
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