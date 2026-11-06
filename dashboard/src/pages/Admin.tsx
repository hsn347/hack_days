import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import {
  Search, Shield, Trash2, Edit, Ban, CheckCircle, Clock, X,
  Layers, Calendar, Plus, Minus, AlertTriangle, Users,
  Infinity, PauseCircle, RotateCcw, UserCheck, CheckCheck,
  ChevronLeft, ChevronRight,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { AdminLayout } from '../components/layout/AdminLayout'
import {
  useAllUsers, useAdminStats, useBanUser, useDeleteUser,
  useApproveCastle, useRejectCastle
} from '../hooks/useUsers'
import { useCastles, useDeleteCastle } from '../hooks/useCastles'
import { useQueryClient } from '@tanstack/react-query'
import { updateAdminSubscription, banAdminUser, approveAdminUser, approveAllPendingAdminUsers } from '../lib/botApi'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useDebounce } from '../hooks/useDebounce'
import { AdminLiveProcessesView } from './AdminLiveProcesses'
import type { User, Subscription, Castle } from '../types'
import toast from 'react-hot-toast'
import { ActionConfirmModal } from '../components/common/ActionConfirmModal'

export const isSuperAdminUser = (u?: Partial<User> | null) => {
  if (!u) return false
  const email = (u.email || '').toLowerCase().trim()
  return email === 'ibraboths@gmail.com'
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
  const { t } = useTranslation()
  return (
    <ActionConfirmModal
      isOpen={true}
      onClose={onCancel}
      onConfirm={onConfirm}
      title={title}
      message={message}
      detail={email}
      confirmText={t('admin.modals.deletePermanent')}
      cancelText={t('common.cancel')}
      variant="danger"
      isPending={loading}
    />
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
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [saving, setSaving] = useState(false)
  const isPendingApproval = user.subscription?.status === 'pending_approval'
  const [castles, setCastles] = useState<number>(
    isPendingApproval ? 10 : Number(user.subscription?.max_castles_allowed ?? 1)
  )
  const [isBanned, setIsBanned] = useState<boolean>(Boolean(user.is_banned))

  const now = new Date()
  const currentExp = user.subscription?.expires_at ? new Date(user.subscription.expires_at) : null
  const isCurrentValid = currentExp && currentExp.getTime() > now.getTime()
  const initialBase = isCurrentValid ? currentExp : (isPendingApproval ? new Date(now.getTime() + 3 * 86400000) : now)

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

  const handleDirectApprove = async () => {
    setSaving(true)
    try {
      await approveAdminUser(user.uid, 3, 10)
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      toast.success(t('admin.quickApproveSuccess', { name: user.username || user.email }))
      onClose()
    } catch {
      toast.error(t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const isZeroed = targetDate.getTime() <= now.getTime()
      const finalDays = isZeroed ? 0 : daysRemaining
      const finalStatus = isZeroed ? 'expired' : 'active'
      const finalExpiresAt = isZeroed ? now.toISOString() : targetDate.toISOString()

      await updateAdminSubscription(user.uid, {
        plan_id: `${castles}_castles_${finalDays}d`,
        plan_name: isZeroed ? `${castles} حساب (منتهي)` : `${castles} حساب (${finalDays} يوم)`,
        subscription_status: finalStatus,
        expires_at: finalExpiresAt,
        max_castles_allowed: castles,
      })

      if (isBanned !== user.is_banned) {
        await banAdminUser(user.uid, { is_banned: isBanned })
      }

      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      toast.success(t('admin.modals.saveSuccess'))
      onClose()
    } catch {
      toast.error(t('admin.modals.saveError'))
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
                    {user.username || t('admin.modals.editUserTitle')}
                  </h3>
                  {isBanned && (
                    <span className="py-0.5 text-[10px] badge badge-red shrink-0">{t('dashboard.bannedBadge', 'محظور')}</span>
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

          {/* Pending Approval Banner */}
          {isPendingApproval && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Clock className="text-amber-500 shrink-0 animate-pulse" size={16} />
                <span className="text-xs font-semibold text-amber-800 dark:text-amber-300 truncate">
                  {t('admin.modalPendingNotice')}
                </span>
              </div>
              <button
                type="button"
                onClick={handleDirectApprove}
                disabled={saving}
                className="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-xs flex items-center gap-1 shadow-xs transition shrink-0 cursor-pointer"
              >
                <UserCheck size={13} />
                <span>{t('admin.modalActivateBtn')}</span>
              </button>
            </div>
          )}

          {/* Section 1: Castles Quota */}
          <div className="space-y-2.5 bg-gray-50 dark:bg-white/[0.03] p-3 sm:p-3.5 border border-gray-200 dark:border-white/8 rounded-xl">
            <div className="flex justify-between items-center text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-gray-700 dark:text-gray-300">
                <Layers size={14} className="text-primary-600 dark:text-primary-400" />
                <span>{t('admin.modals.allowedQuota')}</span>
              </div>
              <span className="font-mono text-slate-500 dark:text-slate-400 text-xs">
                ({t('admin.modals.actualExisting', { count: user.subscription?.current_castles_count ?? 0 })})
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
              <span>{t('admin.modals.subDuration')}</span>
            </div>

            {/* Live Instant Expiry & Days Display with Editable Date Picker */}
            <div className={`p-3 sm:p-3.5 rounded-xl border transition-all ${
              isZero
                ? 'bg-rose-50/80 dark:bg-rose-950/20 border-rose-200 dark:border-rose-500/30'
                : 'bg-emerald-50/80 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-500/30'
            }`}>
              <div className="flex justify-between items-center gap-2 text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300 shrink-0">{t('admin.modals.expiryDate')}</span>
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
                <span className="font-medium text-slate-600 dark:text-slate-400">{t('admin.modals.daysRemaining')}</span>
                <span className={`font-bold text-sm ${isZero ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-300'}`}>
                  {isZero ? t('admin.modals.expiredNow') : `${daysRemaining} ${t('common.days')}`}
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
                <span>{t('admin.modals.addMonth')}</span>
              </button>

              <button
                type="button"
                onClick={() => addDays(7)}
                className="flex justify-center items-center gap-1.5 bg-primary-600 hover:bg-primary-500 shadow-xs px-2 py-2.5 rounded-xl font-bold text-white text-xs active:scale-95 transition-all cursor-pointer"
              >
                <Plus size={14} />
                <span>{t('admin.modals.addWeek')}</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                className="flex justify-center items-center gap-1.5 bg-gray-100 hover:bg-rose-50 dark:bg-white/5 dark:hover:bg-rose-950/30 px-2 py-2.5 border border-gray-200 hover:border-rose-300 dark:border-white/10 rounded-xl font-bold text-gray-700 hover:text-rose-600 dark:hover:text-rose-400 dark:text-gray-300 text-xs active:scale-95 transition-all cursor-pointer"
              >
                <RotateCcw size={13} />
                <span>{t('admin.modals.reset')}</span>
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
                  <span>{t('admin.modals.unbanAccount')}</span>
                </>
              ) : (
                <>
                  <Ban size={15} />
                  <span>{t('admin.modals.banAccount')}</span>
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
              {t('common.cancel')}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 shadow-md py-3 rounded-xl font-bold text-white text-sm active:scale-[0.98] transition-all cursor-pointer"
            >
              {saving ? t('common.loading') : t('common.save')}
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
  const { t } = useTranslation()
  const { data, isLoading } = useCastles(user.uid)
  const castlesList: Castle[] = data?.pages.flatMap(p => p.items) ?? []
  const approveCastle = useApproveCastle()
  const rejectCastle = useRejectCastle()
  const deleteCastle = useDeleteCastle(user.uid)
  const pending = castlesList.filter((c: Castle) => !c.is_active || c.bot_status?.state === 'pending')
  const active = castlesList.filter((c: Castle) => c.is_active && c.bot_status?.state !== 'pending')

  const [confirmAction, setConfirmAction] = useState<{
    title: string
    message: string
    confirmText?: string
    variant?: 'danger' | 'warning' | 'primary'
    detail?: string
    action: () => void
  } | null>(null)

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
                {user.username ? t('admin.modals.castlesTitle', { name: user.username }) : t('admin.modals.castlesTitleGeneric')}
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
            { label: t('admin.modals.quotaLimit'), value: user.subscription?.max_castles_allowed ?? 1, color: 'text-primary-600 dark:text-primary-400' },
            { label: t('admin.modals.activeCastles'), value: active.length, color: 'text-emerald-600 dark:text-emerald-400' },
            { label: t('admin.modals.waitingCastles'), value: pending.length, color: pending.length > 0 ? 'text-amber-600 dark:text-yellow-400' : 'text-gray-400' },
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
            <div className="py-10 text-gray-500 dark:text-gray-400 text-sm text-center">{t('common.loading')}</div>
          ) : castlesList.length === 0 ? (
            <div className="py-10 text-gray-500 dark:text-gray-400 text-sm text-center">{t('admin.modals.noCastlesFound')}</div>
          ) : (
            <>
              {pending.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 font-bold text-amber-600 dark:text-yellow-400 text-xs">
                    <Clock size={13} /><span>{t('admin.modals.pendingApprovalCount', { count: pending.length })}</span>
                  </div>
                  {pending.map(c => (
                    <div key={c.id} className="flex justify-between items-center gap-2.5 bg-amber-50 dark:bg-yellow-500/5 p-3 border border-amber-200 dark:border-yellow-500/20 rounded-xl">
                      <div className="min-w-0">
                        <div className="font-semibold text-gray-900 dark:text-white text-sm truncate">{c.castle_info?.castle_name || c.castle_info?.lord_name || t('admin.modals.castleFallback')}</div>
                        <div className="font-mono text-[11px] text-gray-500 dark:text-gray-400 truncate">{c.email}</div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button disabled={approveCastle.isPending}
                          onClick={() => approveCastle.mutate({userId:user.uid,castleId:c.id},{onSuccess:()=>toast.success(t('admin.modals.approveSuccess')),onError:()=>toast.error(t('common.error'))})}
                          className="flex items-center gap-1 bg-emerald-600 hover:bg-emerald-500 shadow-xs px-2.5 sm:px-3 py-1.5 rounded-lg font-bold text-white text-xs active:scale-95 transition-all cursor-pointer">
                          <CheckCircle size={12} />{t('admin.modals.acceptBtn')}
                        </button>
                        <button disabled={rejectCastle.isPending}
                          onClick={() => {
                            setConfirmAction({
                              title: t('admin.modals.confirmRejectTitle', t('admin.modals.rejectSuccess')),
                              message: t('admin.modals.confirmReject', { email: c.email }),
                              confirmText: t('common.delete', 'Delete'),
                              variant: 'danger',
                              detail: c.email,
                              action: () => {
                                rejectCastle.mutate(
                                  { userId: user.uid, castleId: c.id },
                                  {
                                    onSuccess: () => {
                                      toast.success(t('admin.modals.rejectSuccess'))
                                      setConfirmAction(null)
                                    },
                                    onError: () => toast.error(t('common.error')),
                                  }
                                )
                              },
                            })
                          }}
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
                    <span>{t('admin.modals.activeCastlesCount', { count: active.length })}</span>
                  </div>
                  {active.map(c => (
                    <div key={c.id} className="flex justify-between items-center gap-2.5 bg-gray-50 dark:bg-white/[0.02] p-3 border border-gray-200 hover:border-gray-300 dark:border-white/8 dark:hover:border-white/12 rounded-xl transition-colors">
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 dark:text-white text-sm truncate">{c.castle_info?.castle_name || c.castle_info?.lord_name || t('admin.modals.castleFallback')}</div>
                        <div className="font-mono text-[11px] text-gray-500 dark:text-gray-400 truncate">{c.email}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="py-0.5 text-[10px] badge badge-green">{t('admin.modals.activeBadge')}</span>
                        <button
                          onClick={() => {
                            setConfirmAction({
                              title: t('admin.modals.confirmDeleteCastleTitle', t('common.delete')),
                              message: t('admin.modals.confirmDeleteCastle', { email: c.email }),
                              confirmText: t('common.delete', 'Delete'),
                              variant: 'danger',
                              detail: c.email,
                              action: () => {
                                deleteCastle.mutate(
                                  { castleId: c.id, wasActive: true },
                                  {
                                    onSuccess: () => {
                                      toast.success(t('admin.modals.deleteCastleSuccess'))
                                      setConfirmAction(null)
                                    },
                                    onError: () => toast.error(t('common.error')),
                                  }
                                )
                              },
                            })
                          }}
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
          <button onClick={onClose} className="hover:bg-gray-100 dark:hover:bg-white/5 py-2.5 border border-gray-200 dark:border-white/10 rounded-xl w-full font-semibold text-gray-700 hover:text-gray-900 dark:hover:text-white dark:text-gray-300 text-sm transition-all cursor-pointer">{t('common.close')}</button>
        </div>

        {/* Confirmation Modal */}
        <ActionConfirmModal
          isOpen={!!confirmAction}
          onClose={() => setConfirmAction(null)}
          onConfirm={() => confirmAction?.action()}
          title={confirmAction?.title || ''}
          message={confirmAction?.message || ''}
          confirmText={confirmAction?.confirmText}
          variant={confirmAction?.variant || 'danger'}
          detail={confirmAction?.detail}
          isPending={rejectCastle.isPending || deleteCastle.isPending}
        />
      </motion.div>
    </div>,
    document.body
  )
}

// Main Admin Page
export function AdminPage() {
  const { t } = useTranslation()
  const { firebaseUser, user, isAdmin, isSuperAdmin, loading: authLoading } = useAuth()
  const location = useLocation()
  const isLiveTab = location.pathname.startsWith('/admin/live-processes')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [manageCastlesUser, setManageCastlesUser] = useState<User | null>(null)
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<User | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [sortByLeastDays, setSortByLeastDays] = useState(false)
  const [filterPending, setFilterPending] = useState(false)
  const [approvingAll, setApprovingAll] = useState(false)
  const qc = useQueryClient()
  const { data: users = [], isLoading } = useAllUsers()
  const { data: stats } = useAdminStats()
  const banUser = useBanUser()
  const deleteUser = useDeleteUser()

  if (authLoading) {
    return (
      <div className="flex justify-center items-center bg-gray-50 dark:bg-[#060a08] min-h-screen text-emerald-500">
        <div className="flex flex-col items-center gap-3">
          <div className="border-2 border-emerald-500/30 border-t-emerald-500 rounded-full w-8 h-8 animate-spin" />
          <span className="font-mono text-xs">{t('admin.checkingAuth')}</span>
        </div>
      </div>
    )
  }

  const adminEmail = (firebaseUser?.email || user?.email || '').trim().toLowerCase()
  if ((!firebaseUser && !user) || !isAdmin) {
    return <Navigate to="/login" replace />
  }

  const getDaysRemaining = (u: User) => {
    const expDate = u.subscription?.expires_at ? new Date(u.subscription.expires_at) : null
    const isLifetime = expDate ? expDate.getFullYear() >= 2090 : false
    if (isLifetime) return 999999
    if (!expDate || isNaN(expDate.getTime())) return -999999
    return Math.ceil((expDate.getTime() - Date.now()) / 86400000)
  }

  // فلترة قائمة المستخدمين لعرض العملاء والمشتركين فقط واستبعاد حساب المشرف الأعلى وحساب المشرف نفسه نهائياً
  const clientUsers = users.filter(u => !isSuperAdminUser(u) && u.email?.toLowerCase().trim() !== adminEmail)
  const pendingUsersCount = clientUsers.filter(u => u.subscription?.status === 'pending_approval').length

  let baseList = debouncedSearch
    ? clientUsers.filter(u => u.email.toLowerCase().includes(debouncedSearch.toLowerCase()) || u.username?.toLowerCase().includes(debouncedSearch.toLowerCase()) || u.uid.includes(debouncedSearch))
    : clientUsers

  if (filterPending) {
    baseList = baseList.filter(u => u.subscription?.status === 'pending_approval')
  }

  const filtered = baseList.slice().sort((a, b) => {
    if (!sortByLeastDays) {
      const aPending = a.subscription?.status === 'pending_approval' ? 1 : 0
      const bPending = b.subscription?.status === 'pending_approval' ? 1 : 0
      if (aPending !== bPending) return bPending - aPending
    }
    if (sortByLeastDays) {
      const diff = getDaysRemaining(a) - getDaysRemaining(b)
      if (diff !== 0) return diff
    }
    return (b.subscription?.current_castles_count || 0) - (a.subscription?.current_castles_count || 0)
  })

  // ─── Client-side Pagination State (Default: 25) ──────────────
  const [pageSize, setPageSize] = useState<number>(25)
  const [currentPage, setCurrentPage] = useState<number>(1)

  // Reset to page 1 whenever search, filters, sorting or page size changes
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearch, filterPending, sortByLeastDays, pageSize])

  const totalItems = filtered.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const validPage = Math.min(Math.max(1, currentPage), totalPages)
  const startIndex = (validPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, totalItems)
  const paginatedUsers = filtered.slice(startIndex, endIndex)

  const [confirmActionModal, setConfirmActionModal] = useState<{
    isOpen: boolean
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    variant?: 'danger' | 'warning' | 'primary'
    detail?: string
    isPending?: boolean
    onConfirm: () => void | Promise<void>
  } | null>(null)

  const handleQuickApprove = (u: User) => {
    setConfirmActionModal({
      isOpen: true,
      title: t('admin.modals.acceptBtn'),
      message: t('admin.quickApproveConfirm', { name: u.username || u.email }),
      confirmText: t('admin.modals.acceptBtn'),
      variant: 'primary',
      detail: u.username || u.email,
      onConfirm: async () => {
        try {
          await approveAdminUser(u.uid, 3, 10)
          qc.invalidateQueries({ queryKey: ['admin_users'] })
          qc.invalidateQueries({ queryKey: ['admin_stats'] })
          toast.success(t('admin.quickApproveSuccess', { name: u.username || u.email }))
          setConfirmActionModal(null)
        } catch {
          toast.error(t('common.error'))
        }
      },
    })
  }

  const handleApproveAllPending = () => {
    if (pendingUsersCount === 0) return
    setConfirmActionModal({
      isOpen: true,
      title: t('admin.modals.acceptBtn'),
      message: t('admin.approveAllConfirm', { count: pendingUsersCount }),
      confirmText: t('admin.modals.acceptBtn'),
      variant: 'primary',
      onConfirm: async () => {
        setApprovingAll(true)
        try {
          const res = await approveAllPendingAdminUsers(3, 10)
          qc.invalidateQueries({ queryKey: ['admin_users'] })
          qc.invalidateQueries({ queryKey: ['admin_stats'] })
          toast.success(t('admin.approveAllSuccess', { count: res.approved_count ?? pendingUsersCount }))
          setConfirmActionModal(null)
        } catch (err: any) {
          toast.error(err?.message || t('common.error'))
        } finally {
          setApprovingAll(false)
        }
      },
    })
  }

  const handleBan = (u: User) => {
    if (isSuperAdminUser(u) || u.email?.toLowerCase().trim() === adminEmail) {
      toast.error(t('admin.cannotBanAdmin'))
      return
    }
    setConfirmActionModal({
      isOpen: true,
      title: u.is_banned ? t('admin.modals.unbanAccount') : t('admin.modals.banAccount'),
      message: u.is_banned ? t('admin.unbanConfirm') : t('admin.banConfirm'),
      confirmText: u.is_banned ? t('admin.modals.unbanAccount') : t('admin.modals.banAccount'),
      variant: u.is_banned ? 'primary' : 'warning',
      detail: u.email,
      onConfirm: () => {
        banUser.mutate(
          { uid: u.uid, ban: !u.is_banned },
          {
            onSuccess: () => {
              toast.success(t('common.success'))
              setConfirmActionModal(null)
            },
            onError: () => toast.error(t('common.error')),
          }
        )
      },
    })
  }

  const handleDelete = (u: User) => {
    if (isSuperAdminUser(u) || u.email?.toLowerCase().trim() === adminEmail) {
      toast.error(t('admin.cannotDeleteAdmin'))
      return
    }
    setConfirmDeleteUser(u)
  }

  const doDelete = () => {
    if (!confirmDeleteUser) return
    setDeleting(true)
    deleteUser.mutate(confirmDeleteUser.uid, {
      onSuccess: () => {
        toast.success(t('admin.deleteUserSuccess'))
        setConfirmDeleteUser(null)
        setDeleting(false)
      },
      onError: () => {
        toast.error(t('admin.deleteUserError'))
        setDeleting(false)
      },
    })
  }

  return (
    <AdminLayout title={isLiveTab ? t('admin.live.title') : t('admin.title')}>
      {/* ── Users Management Tab View ── */}
      <div style={{ display: isLiveTab ? 'none' : 'block' }}>
        <div className="space-y-4 sm:space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center gap-3">
          <div className="flex items-center gap-2.5">
            <h1 className="flex items-center gap-2 font-black text-gray-900 dark:text-white text-xl sm:text-2xl">
              <Shield size={22} className="text-emerald-600 dark:text-emerald-400" />
              <span>{t('admin.title')}</span>
            </h1>
            {stats?.totalUsers !== undefined && (
              <span className="bg-emerald-500/10 px-2 py-0.5 border border-emerald-500/20 rounded-md font-mono font-semibold text-[11px] text-emerald-600 dark:text-emerald-400">
                {stats.totalUsers} مستخدم
              </span>
            )}
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
              label: t('admin.pendingUsersStat'),
              value: pendingUsersCount,
              icon: '⏳',
              color: 'text-amber-600 dark:text-amber-400',
              bg: 'bg-white dark:bg-white/[0.03]',
              border: 'border-slate-200/80 dark:border-white/8',
              iconBg: 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400',
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
            <div className="flex flex-wrap sm:flex-nowrap items-center gap-2 w-full sm:w-auto">
              <div className="relative flex-1 sm:flex-initial min-w-[140px]">
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
              {pendingUsersCount > 0 && (
                <>
                  <button
                    type="button"
                    id="admin-approve-all-pending"
                    onClick={handleApproveAllPending}
                    disabled={approvingAll}
                    title={t('admin.approveAllBtn', { count: pendingUsersCount })}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs sm:text-sm font-bold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-xs border border-emerald-600/80 transition-all shrink-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <CheckCheck size={16} className={approvingAll ? 'animate-spin' : ''} />
                    <span>{approvingAll ? t('admin.approvingAll') : t('admin.approveAllBtn', { count: pendingUsersCount })}</span>
                  </button>
                  <button
                    type="button"
                    id="admin-filter-pending"
                    onClick={() => setFilterPending(!filterPending)}
                    title={filterPending ? t('common.all') : t('admin.pendingApproval')}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold border transition-all shrink-0 cursor-pointer ${
                      filterPending
                        ? 'bg-amber-500 border-amber-600 text-white shadow-xs ring-1 ring-amber-500/40'
                        : 'bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-400 hover:bg-amber-500/25 animate-pulse'
                    }`}
                  >
                    <Clock size={15} />
                    <span>{t('admin.pendingApproval')} ({pendingUsersCount})</span>
                  </button>
                </>
              )}
              <button
                type="button"
                id="admin-sort-least-days"
                onClick={() => setSortByLeastDays(!sortByLeastDays)}
                title={sortByLeastDays ? t('admin.resetSort') : t('admin.sortLeastDaysTooltip')}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold border transition-all shrink-0 cursor-pointer ${
                  sortByLeastDays
                    ? 'bg-amber-500/15 border-amber-500/40 text-amber-600 dark:text-amber-400 shadow-xs ring-1 ring-amber-500/30'
                    : 'bg-slate-100/80 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-white/10'
                }`}
              >
                <Clock size={15} className={sortByLeastDays ? 'text-amber-500' : 'text-slate-400'} />
                <span>{t('admin.closestToExpire')}</span>
                {sortByLeastDays && (
                  <span className="bg-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-mono leading-none">
                    {t('common.enabled')}
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
                      <th className="px-5 py-3 text-start">{t('admin.table.user')}</th>
                      <th className="px-3 py-3 text-start">{t('admin.role')}</th>
                      <th className="px-3 py-3 text-center">{t('admin.table.castles')}</th>
                      <th
                        className="px-3 py-3 text-start cursor-pointer hover:text-emerald-500 transition-colors select-none"
                        onClick={() => setSortByLeastDays(!sortByLeastDays)}
                        title={t('admin.sortLeastDaysTooltip')}
                      >
                        <div className="flex items-center gap-1">
                          <span>{t('admin.table.subscriptionEnd')}</span>
                          {sortByLeastDays && (
                            <span className="text-[10px] text-amber-500 font-bold">{t('admin.table.least')}</span>
                          )}
                        </div>
                      </th>
                      <th className="px-3 py-3 text-start">{t('admin.table.status')}</th>
                      <th className="px-5 py-3 text-end">{t('admin.table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                    {paginatedUsers.map(u => {
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
                            <span className={`badge ${u.role==='admin'?'badge-yellow':'badge-gray'}`}>{u.role==='admin'?t('roles.admin'):t('roles.user')}</span>
                          </td>
                          <td className="px-3 py-3.5 text-center">
                            <div className="flex flex-col items-center gap-1">
                              {u.is_banned ? (
                                <div className="flex flex-col items-center gap-0.5">
                                  <div className="font-mono text-sm flex items-center justify-center gap-1 text-red-500">
                                    <Ban size={13} />
                                    <span className="font-black">0</span>
                                    <span className="font-normal text-slate-400"> / {u.subscription?.max_castles_allowed ?? 1}</span>
                                  </div>
                                  <span className="text-[10px] text-red-500 font-semibold leading-none">{t('admin.table.bannedPill')}</span>
                                </div>
                              ) : (
                                <div className="font-mono text-sm">
                                  <span className="font-black text-emerald-600 dark:text-emerald-400">{u.subscription?.current_castles_count ?? 0}</span>
                                  <span className="font-normal text-slate-400"> / {u.subscription?.max_castles_allowed ?? 1}</span>
                                </div>
                              )}
                              {!u.is_banned && pendingCount > 0 && (
                                <button onClick={e => { e.stopPropagation(); setManageCastlesUser(u) }} className="flex items-center gap-1 hover:bg-yellow-500/30 text-[10px] animate-pulse cursor-pointer badge badge-yellow">
                                  <Clock size={10} /><span>{t('admin.table.waitingCount', { count: pendingCount })}</span>
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-3.5 text-xs">
                            {expDate ? (
                              <div>
                                <div className={`font-semibold font-mono ${isLifetime ? 'text-emerald-700 dark:text-emerald-400' : isExpired ? 'text-rose-600 dark:text-red-400' : 'text-slate-900 dark:text-gray-200'}`} dir="ltr">
                                  {isLifetime ? t('admin.table.lifetime') : formatDate(expDate)}
                                </div>
                                <div className="mt-0.5 text-[11px] text-slate-500 dark:text-gray-400">
                                  {isLifetime ? t('admin.table.unlimited') : isExpired ? t('dashboard.expiredBadge', 'منتهي') : daysLeft > 60 ? `~${Math.round(daysLeft/30)} ${t('admin.table.months')}` : `${daysLeft} ${t('common.days')}`}
                                </div>
                              </div>
                            ) : <span className="text-slate-400">—</span>}
                          </td>
                          <td className="px-3 py-3.5">
                            {u.is_banned ? <span className="badge badge-red">{t('dashboard.bannedBadge', 'محظور')}</span>
                             : isSuspended ? <span className="badge badge-yellow">{t('admin.table.suspended')}</span>
                             : u.subscription?.status === 'pending_approval' ? (
                               <span className="badge badge-yellow animate-pulse flex items-center gap-1 font-bold">
                                 <Clock size={11} /> {t('admin.pendingApproval')}
                               </span>
                             )
                             : isLifetime ? <span className="flex items-center gap-1 badge badge-green"><Infinity size={11} /> {t('admin.table.lifetimeShort')}</span>
                             : isExpired ? <span className="badge badge-red">{t('dashboard.expiredBadge', 'منتهي')}</span>
                             : u.subscription?.status==='active' ? <span className="badge badge-green">{t('admin.table.active')}</span>
                             : <span className="badge badge-gray">{u.subscription?.status||'—'}</span>}
                          </td>
                          <td className="px-5 py-3.5">
                            <div className="flex justify-end items-center gap-1.5">
                              {u.subscription?.status === 'pending_approval' && (
                                <button
                                  onClick={e => { e.stopPropagation(); handleQuickApprove(u) }}
                                  className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs shadow-xs hover:shadow transition-all cursor-pointer"
                                  title={t('admin.quickApproveBtn')}
                                >
                                  <UserCheck size={14} />
                                  <span>{t('admin.quickApproveBtn')}</span>
                                </button>
                              )}
                              <button onClick={e=>{e.stopPropagation();setManageCastlesUser(u)}} className="hover:bg-primary-50 dark:hover:bg-primary-600/20 p-2 rounded-xl text-primary-600 hover:text-primary-800 dark:hover:text-white dark:text-primary-400 transition-colors cursor-pointer" title={t('admin.table.manageCastlesTooltip')}><Layers size={15}/></button>
                              <button onClick={e=>{e.stopPropagation();setEditUser(u)}} className="hover:bg-slate-100 dark:hover:bg-white/8 p-2 rounded-xl text-slate-600 hover:text-slate-900 dark:hover:text-white dark:text-gray-300 transition-colors cursor-pointer" title={t('admin.editSubscription')}><Edit size={14}/></button>
                              <button onClick={e=>{e.stopPropagation();handleBan(u)}} className={`p-2 rounded-xl transition-colors cursor-pointer ${u.is_banned?'text-emerald-700 dark:text-green-400 hover:bg-emerald-50 dark:hover:bg-green-600/10':'text-amber-700 dark:text-yellow-400 hover:bg-amber-50 dark:hover:bg-yellow-600/10'}`} title={u.is_banned?t('admin.unbanUser'):t('admin.banUser')}>
                                {u.is_banned?<CheckCircle size={14}/>:<Ban size={14}/>}
                              </button>
                              <button onClick={e=>{e.stopPropagation();handleDelete(u)}} className="hover:bg-rose-50 dark:hover:bg-red-600/10 p-2 rounded-xl text-slate-400 hover:text-rose-600 dark:hover:text-red-400 transition-colors cursor-pointer" title={t('admin.deleteUser')}><Trash2 size={14}/></button>
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
                {paginatedUsers.map(u => {
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
                            {u.role==='admin'?t('roles.admin'):t('roles.user')}
                          </span>
                          {u.is_banned ? (
                            <span className="py-0.5 text-[10px] badge badge-red">{t('dashboard.bannedBadge', 'محظور')}</span>
                          ) : isSuspended ? (
                            <span className="py-0.5 text-[10px] badge badge-yellow">{t('admin.table.suspended')}</span>
                          ) : u.subscription?.status === 'pending_approval' ? (
                            <span className="py-0.5 text-[10px] badge badge-yellow animate-pulse font-bold flex items-center gap-1">
                              <Clock size={10} /> {t('admin.pendingApproval')}
                            </span>
                          ) : isLifetime ? (
                            <span className="flex items-center gap-1 py-0.5 text-[10px] badge badge-green">
                              <Infinity size={10} /> {t('admin.table.lifetimeShort')}
                            </span>
                          ) : isExpired ? (
                            <span className="py-0.5 text-[10px] badge badge-red">{t('dashboard.expiredBadge', 'منتهي')}</span>
                          ) : (
                            <span className="py-0.5 text-[10px] badge badge-green">{t('admin.table.active')}</span>
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
                            <div className="font-semibold text-[10px] text-slate-500 dark:text-slate-400">{t('admin.mobile.castlesRatio')}</div>
                            {u.is_banned ? (
                              <div className="flex items-center gap-1 font-mono text-xs text-red-500">
                                <Ban size={12} />
                                <span className="font-black text-red-500 text-sm">0</span>
                                <span className="font-medium text-slate-400">
                                  / {u.subscription?.max_castles_allowed ?? 1}
                                </span>
                                <span className="text-[10px] text-red-500 font-semibold ms-1">{t('admin.table.bannedPill')}</span>
                              </div>
                            ) : (
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
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <div className="flex justify-center items-center bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 rounded-lg w-7 h-7 shrink-0">
                            <Calendar size={13} className="text-emerald-600 dark:text-emerald-400" />
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold text-[10px] text-slate-500 dark:text-slate-400">{t('admin.mobile.subscription')}</div>
                            <div className="font-mono font-bold text-xs" dir="ltr">
                              {expDate ? (
                                <span className={isLifetime ? 'text-emerald-700 dark:text-emerald-300 font-bold' : isExpired ? 'text-rose-600 dark:text-rose-400 font-bold' : 'text-emerald-700 dark:text-emerald-300 font-bold'}>
                                  {isLifetime ? t('admin.table.lifetime') : formatDate(expDate)}
                                  <span className="ms-1 font-sans font-normal text-[10px] text-slate-500 dark:text-slate-400">
                                    ({isLifetime ? '∞' : isExpired ? t('dashboard.expiredBadge', 'منتهي') : `${daysLeft}${t('admin.table.d')}`})
                                  </span>
                                </span>
                              ) : <span className="text-slate-400">—</span>}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Quick Approve Button for Pending Users (Mobile) */}
                      {u.subscription?.status === 'pending_approval' && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); handleQuickApprove(u); }}
                          className="w-full flex items-center justify-center gap-1.5 py-2.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl shadow-xs transition cursor-pointer"
                        >
                          <UserCheck size={14} />
                          <span>{t('admin.quickApproveBtn')}</span>
                        </button>
                      )}

                      {/* Action buttons (Mobile single row) */}
                      <div className="flex justify-between items-center gap-1.5 pt-1" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => setEditUser(u)}
                          className="flex flex-1 justify-center items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 dark:bg-emerald-600/20 dark:hover:bg-emerald-600/30 shadow-xs px-3 py-2 dark:border dark:border-emerald-500/30 rounded-xl font-bold text-white dark:text-emerald-300 text-xs active:scale-95 transition cursor-pointer"
                        >
                          <Edit size={13} />
                          <span>{t('admin.editSubscription')}</span>
                        </button>

                        <button
                          onClick={() => setManageCastlesUser(u)}
                          className="flex justify-center items-center gap-1 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 shadow-xs px-3 py-2 border border-slate-200/80 dark:border-white/10 rounded-xl font-bold text-slate-800 dark:text-slate-200 text-xs active:scale-95 transition cursor-pointer"
                          title={t('admin.table.manageCastlesTooltip')}
                        >
                          <Layers size={13} className="text-primary-600 dark:text-primary-400" />
                          <span>{t('admin.castles')}</span>
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
                          title={t('admin.deleteUser')}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* ── Pagination Controls ── */}
              {totalItems > 0 && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 bg-slate-50/75 dark:bg-white/[0.01] border-t border-slate-200/80 dark:border-white/8 text-xs select-none">
                  {/* Left: Range and total count */}
                  <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-mono">
                    <span className="font-semibold text-slate-700 dark:text-slate-300">
                      {startIndex + 1}–{endIndex}
                    </span>
                    <span>/</span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      {totalItems}
                    </span>
                    <span>{t('admin.table.usersCount', 'مستخدم')}</span>
                  </div>

                  {/* Center: Prev / Next / Page Numbers */}
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      id="admin-pagination-prev"
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
                      id="admin-pagination-next"
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
                        onClick={() => setPageSize(sz)}
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

              {totalItems === 0 && (
                <div className="py-16 text-slate-400 text-center">{t('admin.table.noSearchResults')}</div>
              )}
            </>
          )}
        </div>
      </div>
      </div>

      {/* ── Live Processes Tab View (Always hot in memory, instant display for SuperAdmin) ── */}
      {isSuperAdmin && (
        <div style={{ display: isLiveTab ? 'block' : 'none' }}>
          <AdminLiveProcessesView isActive={isLiveTab} />
        </div>
      )}

      <AnimatePresence>
        {editUser && <EditUserModal user={editUser} onClose={()=>setEditUser(null)} />}
        {manageCastlesUser && <UserCastlesModal user={manageCastlesUser} onClose={()=>setManageCastlesUser(null)} />}
        {confirmDeleteUser && (
          <ConfirmDialog
            title={t('admin.modals.confirmDeleteTitle')}
            message={t('admin.modals.confirmDeleteMsg')}
            email={confirmDeleteUser.email}
            loading={deleting}
            onConfirm={doDelete}
            onCancel={() => setConfirmDeleteUser(null)}
          />
        )}
        {confirmActionModal && (
          <ActionConfirmModal
            isOpen={confirmActionModal.isOpen}
            onClose={() => setConfirmActionModal(null)}
            onConfirm={confirmActionModal.onConfirm}
            title={confirmActionModal.title}
            message={confirmActionModal.message}
            confirmText={confirmActionModal.confirmText}
            cancelText={confirmActionModal.cancelText}
            variant={confirmActionModal.variant}
            detail={confirmActionModal.detail}
            isPending={confirmActionModal.isPending || approvingAll || banUser.isPending}
          />
        )}
      </AnimatePresence>
    </AdminLayout>
  )
}