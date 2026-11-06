import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { User, Lock, Eye, EyeOff, Check, Sparkles, ShieldCheck, Clock, Plus, Minus, Trash2, Dices, X, Search, CheckSquare, Square } from 'lucide-react'
import { updatePassword, EmailAuthProvider, reauthenticateWithCredential, updateProfile } from 'firebase/auth'
import { motion, AnimatePresence } from 'framer-motion'
import { useQueryClient } from '@tanstack/react-query'
import { Layout } from '../components/layout/Layout'
import { useAuth } from '../hooks/useAuth'
import { useCastles } from '../hooks/useCastles'
import { updateCastlesLoopIntervals } from '../lib/botApi'
import { auth } from '../lib/firebase'
import type { Castle } from '../types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export function SettingsPage() {
  const { t } = useTranslation()
  const { user, firebaseUser, updateUserProfile, isAdmin } = useAuth()

  const [username, setUsername] = useState(user?.username ?? '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [savedSuccess, setSavedSuccess] = useState(false)

  const [currentPw, setCurrentPw]   = useState('')
  const [newPw, setNewPw]           = useState('')
  const [confirmPw, setConfirmPw]   = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew]         = useState(false)
  const [savingPw, setSavingPw]       = useState(false)

  // مزامنة الاسم تلقائياً عند تحديث كائن المستخدم
  useEffect(() => {
    if (user?.username) {
      setUsername(user.username)
    }
  }, [user?.username])

  const handleSaveProfile = async () => {
    if (!user) return
    const trimmed = username.trim()
    if (!trimmed) {
      toast.error(t('settings.usernameRequired'))
      return
    }

    setSavingProfile(true)

    // 1. تحديث محلي وفوري في الذاكرة ليظهر في السايدبار والواجهة فوراً بـ 0 تأخير
    updateUserProfile({ username: trimmed })
    setSavedSuccess(true)

    try {
      // 2. تحديث الاسم التعريفي في Firebase Auth
      if (firebaseUser) {
        try {
          await updateProfile(firebaseUser, { displayName: trimmed })
        } catch {
          // non-critical
        }
      }

      toast.success(t('settings.profileSaved', { name: trimmed }), {
        icon: '✨',
        duration: 2500,
      })
    } catch {
      toast.error(t('common.error'))
      // إعادة الاسم السابق في حال فشل الاتصال
      if (user?.username) {
        updateUserProfile({ username: user.username })
      }
    } finally {
      setSavingProfile(false)
      setTimeout(() => setSavedSuccess(false), 2500)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPw !== confirmPw) { toast.error(t('settings.passwordsNotMatching')); return }
    if (newPw.length < 6)    { toast.error(t('settings.passwordMinLength')); return }
    if (!firebaseUser?.email) return
    setSavingPw(true)
    try {
      const cred = EmailAuthProvider.credential(firebaseUser.email, currentPw)
      await reauthenticateWithCredential(firebaseUser, cred)
      await updatePassword(firebaseUser, newPw)
      toast.success(t('common.success'))
      setCurrentPw(''); setNewPw(''); setConfirmPw('')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      toast.error(msg.includes('wrong-password') ? t('settings.wrongCurrentPassword') : t('common.error'))
    } finally {
      setSavingPw(false)
    }
  }

  return (
    <Layout title={t('settings.title')}>
      <div className="space-y-6 mx-auto max-w-2xl">
        {/* Header */}
        <div>
          <h1 className="font-bold text-white text-2xl settings-page-title">{t('settings.title')}</h1>
          <p className="mt-1 text-gray-500 text-sm settings-page-desc">{t('settings.profileDesc')}</p>
        </div>

        {/* Profile section */}
        <div className="space-y-6 p-6 settings-profile-card glass-card">
          {/* Live Profile Header Banner */}
          <div className="flex flex-wrap justify-between items-center gap-4 bg-gradient-to-r from-primary-950/50 via-primary-900/30 to-black/40 shadow-inner p-4 border border-primary-500/30 rounded-2xl settings-profile-banner">
            <div className="flex items-center gap-3.5 min-w-0">
              {/* Avatar Circle with Ring */}
              <div className="relative shrink-0">
                <div className="flex justify-center items-center bg-gradient-to-br from-primary-600 via-primary-700 to-primary-900 shadow-[0_0_20px_rgba(var(--theme-primary-rgb),0.35)] border border-primary-400/40 rounded-2xl w-13 h-13 font-black text-white text-2xl settings-avatar">
                  {(user?.username || username || user?.email || '?')[0].toUpperCase()}
                </div>
              </div>

              {/* Dynamic Live Name Display */}
              <div className="space-y-0.5 min-w-0">
                <div className="flex items-center gap-2">
                  <AnimatePresence mode="wait">
                    <motion.h3
                      key={user?.username || username}
                      initial={{ opacity: 0, y: -4, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4 }}
                      transition={{ duration: 0.2 }}
                      className="font-bold text-white text-lg sm:text-xl truncate settings-username-display"
                    >
                      {user?.username || username || t('settings.newUser')}
                    </motion.h3>
                  </AnimatePresence>
                </div>
                <p className="font-mono text-gray-400 text-xs truncate select-all settings-email-display">{user?.email}</p>
              </div>
            </div>

            {savedSuccess && (
              <motion.div
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                className="flex items-center gap-1.5 bg-primary-500/20 shadow-sm px-3 py-1.5 border border-primary-500/40 rounded-xl font-bold text-primary-300 text-xs settings-success-badge"
              >
                <Check size={14} />
                <span>{t('settings.saved')}</span>
              </motion.div>
            )}
          </div>

          <div className="space-y-4">
            <div>
              <label className="block mb-1.5 text-gray-400 text-sm settings-label">{t('settings.email')}</label>
              <input
                id="settings-email"
                type="email"
                value={user?.email ?? ''}
                readOnly
                className="opacity-60 cursor-not-allowed settings-readonly-input input-field"
                dir="ltr"
              />
            </div>

            <div>
              <label className="block mb-1.5 text-gray-400 text-sm settings-label">{t('settings.username')}</label>
              <div className="relative flex items-center">
                <input
                  id="settings-username"
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSaveProfile(); } }}
                  className="pe-10 input-field"
                  placeholder={t('settings.username')}
                />
                <div className="absolute text-gray-500 pointer-events-none end-3">
                  <User size={16} />
                </div>
              </div>
            </div>

            <div>
              <label className="block mb-1.5 text-gray-400 text-sm settings-label">{t('settings.castleCount')}</label>
              <div className="flex items-center gap-2 opacity-60 cursor-not-allowed settings-stat-input input-field">
                <span className="text-primary-400">🏰</span>
                <span className="flex items-center gap-1.5 font-bold font-mono" dir="ltr">
                  <span>{user?.subscription?.current_castles_count ?? 0}</span>
                  <span className="text-gray-400 font-sans font-normal">{t('common.of', 'من')}</span>
                  <span>{isAdmin || user?.role === 'admin' ? '∞' : (user?.subscription?.max_castles_allowed ?? 0)}</span>
                </span>
              </div>
            </div>

            <button
              id="save-profile-btn"
              onClick={handleSaveProfile}
              disabled={savingProfile}
              className={clsx(
                'flex items-center gap-2 transition-all duration-200 cursor-pointer btn-primary',
                savedSuccess && 'bg-primary-600 border-primary-400 shadow-[0_0_20px_rgba(var(--theme-primary-rgb),0.5)]'
              )}
            >
              {savingProfile ? (
                <>
                  <span className="border-2 border-white/30 border-t-white rounded-full w-4 h-4 animate-spin" />
                  <span>{t('settings.savingProfile')}</span>
                </>
              ) : savedSuccess ? (
                <>
                  <Check size={16} className="text-white" />
                  <span>{t('settings.profileUpdated')}</span>
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  <span>{t('settings.saveProfile')}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Bot Cycle Intervals */}
        <BotCycleIntervalsSection userId={user?.uid} />

        {/* Change password */}
        <div className="space-y-5 p-6 settings-password-card glass-card">
          <div className="flex items-center gap-2">
            <div className="flex justify-center items-center bg-primary-700 rounded-lg w-7 h-7 settings-lock-icon">
              <Lock size={15} className="text-white" />
            </div>
            <h2 className="font-semibold text-white settings-section-title">{t('settings.changePassword')}</h2>
          </div>

          <form onSubmit={handleChangePassword} className="space-y-4">
            {/* Current password */}
            <div>
              <label className="block mb-1.5 text-gray-400 text-sm settings-label">{t('settings.currentPassword')}</label>
              <div className="relative">
                <input
                  id="current-password"
                  type={showCurrent ? 'text' : 'password'}
                  required
                  value={currentPw}
                  onChange={e => setCurrentPw(e.target.value)}
                  className="pe-10 input-field"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowCurrent(v => !v)}
                  className="absolute inset-y-0 flex items-center text-gray-500 hover:text-gray-300 settings-eye-btn end-3">
                  {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* New password */}
            <div>
              <label className="block mb-1.5 text-gray-400 text-sm settings-label">{t('settings.newPassword')}</label>
              <div className="relative">
                <input
                  id="new-password"
                  type={showNew ? 'text' : 'password'}
                  required
                  minLength={6}
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  className="pe-10 input-field"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowNew(v => !v)}
                  className="absolute inset-y-0 flex items-center text-gray-500 hover:text-gray-300 settings-eye-btn end-3">
                  {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <p className="mt-1 text-gray-600 text-xs settings-hint-text">{t('settings.minChars')}</p>
            </div>

            {/* Confirm password */}
            <div>
              <label className="block mb-1.5 text-gray-400 text-sm settings-label">{t('settings.confirmPassword')}</label>
              <input
                id="confirm-password"
                type="password"
                required
                minLength={6}
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                className="input-field"
                placeholder="••••••••"
              />
            </div>

            <button
              id="update-password-btn"
              type="submit"
              disabled={savingPw}
              className="btn-primary"
            >
              {savingPw ? t('common.loading') : t('settings.updatePassword')}
            </button>
          </form>
        </div>
      </div>
    </Layout>
  )
}

interface IntervalGroup {
  id: string
  minutes: number
  castleIds: string[]
}

interface CastleSelectorModalProps {
  isOpen: boolean
  onClose: () => void
  durationMinutes: number
  allCastles: Castle[]
  currentGroupId: string
  allGroups: IntervalGroup[]
  onConfirm: (selectedIds: string[]) => void
}

function CastleSelectorModal({
  isOpen,
  onClose,
  durationMinutes,
  allCastles,
  currentGroupId,
  allGroups,
  onConfirm,
}: CastleSelectorModalProps) {
  const { t } = useTranslation()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (isOpen) {
      const currentGroup = allGroups.find(g => g.id === currentGroupId)
      setSelectedIds(currentGroup ? [...currentGroup.castleIds] : [])
      setSearchQuery('')
    }
  }, [isOpen, currentGroupId, allGroups])

  if (!isOpen) return null

  // خريطة لمعرفة القلاع المعينة في مدد أخرى
  const otherAssignments = new Map<string, number>()
  allGroups.forEach(g => {
    if (g.id !== currentGroupId) {
      g.castleIds.forEach(cid => otherAssignments.set(cid, g.minutes))
    }
  })

  const filteredCastles = allCastles.filter(c => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return true
    const lord = (c.castle_info?.lord_name || '').toLowerCase()
    const name = (c.castle_info?.castle_name || '').toLowerCase()
    const email = (c.email || '').toLowerCase()
    const sId = String(c.castle_info?.server_id || '')
    return lord.includes(q) || name.includes(q) || email.includes(q) || sId.includes(q)
  })

  const handleToggle = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleSelectAll = () => {
    const allFilteredIds = filteredCastles.map(c => c.id)
    setSelectedIds(prev => Array.from(new Set([...prev, ...allFilteredIds])))
  }

  const handleDeselectAll = () => {
    const filteredSet = new Set(filteredCastles.map(c => c.id))
    setSelectedIds(prev => prev.filter(id => !filteredSet.has(id)))
  }

  const handleSaveAndClose = () => {
    onConfirm(selectedIds)
    onClose()
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center p-0 sm:p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div className="fixed inset-0 bg-black/75 dark:bg-black/85 backdrop-blur-sm pointer-events-auto" />
      <div
        className="relative z-10 w-full sm:max-w-2xl bg-white dark:bg-[#0c1310] text-gray-900 dark:text-gray-100 border-t sm:border border-gray-200 dark:border-white/10 rounded-t-3xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[88vh] sm:max-h-[82vh] overflow-hidden my-auto pointer-events-auto"
        style={{
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 45px -5px rgba(var(--theme-primary-rgb), 0.25)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Mobile drag handle */}
        <div className="w-12 h-1.5 bg-gray-300 dark:bg-gray-700 rounded-full mx-auto my-2.5 sm:hidden shrink-0" />

        {/* Top Accent Gradient Line */}
        <div className="w-full h-1 bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600 shrink-0" />

        {/* Header */}
        <div className="flex justify-between items-center px-5 py-3.5 border-b border-gray-100 dark:border-white/10 bg-gray-50/50 dark:bg-black/20 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-primary-500/15 border border-primary-500/30 text-primary-500 shrink-0">
              <Clock size={18} />
            </div>
            <div className="min-w-0">
              <h3 className="font-bold text-gray-900 dark:text-white text-base truncate">
                {t('settings.selectCastlesTitle', { mins: durationMinutes })}
              </h3>
              <p className="text-gray-500 dark:text-gray-400 text-xs">
                {t('settings.assignedCount', { count: selectedIds.length })}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-white/10 dark:hover:bg-white/15 text-gray-500 dark:text-gray-300 transition-colors cursor-pointer shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        {/* Search & Actions Bar */}
        <div className="p-3.5 space-y-2.5 border-b border-gray-100 dark:border-white/5 bg-gray-50/40 dark:bg-black/15 shrink-0">
          <div className="relative flex items-center">
            <Search size={15} className="absolute text-gray-400 start-3 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder={t('settings.searchCastlesPlaceholder')}
              className="w-full ps-9 pe-8 py-2 bg-white dark:bg-black/40 border border-gray-200 dark:border-white/10 rounded-xl text-gray-900 dark:text-white text-xs placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute end-2.5 text-gray-400 hover:text-gray-600 dark:hover:text-white"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="flex items-center justify-between text-xs pt-0.5">
            <span className="text-gray-500 dark:text-gray-400 font-mono text-[11px]">
              {filteredCastles.length} / {allCastles.length}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSelectAll}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-primary-50 dark:bg-primary-500/15 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-500/30 active:scale-95 transition-all cursor-pointer"
              >
                {t('settings.selectAll', 'تحديد الكل')}
              </button>
              <button
                type="button"
                onClick={handleDeselectAll}
                className="px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-white/10 active:scale-95 transition-all cursor-pointer"
              >
                {t('settings.deselectAll', 'إلغاء الكل')}
              </button>
            </div>
          </div>
        </div>

        {/* Castles Checklist */}
        <div className="p-3 sm:p-4 overflow-y-auto flex-1 overscroll-contain">
          {filteredCastles.length === 0 ? (
            <div className="py-12 text-center text-gray-400 text-xs">
              {t('common.noResults', 'لا توجد قلاع مطابقة')}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {filteredCastles.map(c => {
                const isChecked = selectedIds.includes(c.id)
                const otherMins = otherAssignments.get(c.id)
                const cName = c.castle_info?.lord_name || c.castle_info?.castle_name || c.email?.split('@')[0] || c.id.slice(0, 8)

                return (
                  <div
                    key={c.id}
                    onClick={() => handleToggle(c.id)}
                    className={clsx(
                      'flex items-center justify-between p-3 rounded-2xl cursor-pointer transition-all active:scale-[0.99] select-none min-h-[56px]',
                      isChecked
                        ? 'bg-primary-50 dark:bg-primary-500/15 border-2 border-primary-500/60 shadow-sm'
                        : 'bg-gray-50/70 dark:bg-white/5 hover:bg-gray-100 dark:hover:bg-white/10 border border-gray-200/80 dark:border-white/10'
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {/* Big Checkbox */}
                      <div
                        className={clsx(
                          'w-5 h-5 rounded-md flex items-center justify-center transition-all shrink-0',
                          isChecked
                            ? 'bg-primary-600 text-white shadow-sm'
                            : 'border-2 border-gray-300 dark:border-gray-600 bg-transparent'
                        )}
                      >
                        {isChecked && <Check size={13} strokeWidth={3} />}
                      </div>

                      {/* Avatar Icon */}
                      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary-600 to-primary-800 text-white font-bold flex items-center justify-center text-xs shadow-sm shrink-0">
                        {cName[0].toUpperCase()}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-gray-900 dark:text-white text-xs truncate">
                            {cName}
                          </span>
                          {c.castle_info?.server_id ? (
                            <span className="font-mono text-primary-700 dark:text-primary-300 bg-primary-100 dark:bg-primary-500/20 px-1.5 py-0.2 rounded text-[10px] font-semibold">
                              s{c.castle_info.server_id}
                            </span>
                          ) : null}
                        </div>
                        <p className="font-mono text-[11px] text-gray-400 dark:text-gray-500 truncate">
                          {c.email}
                        </p>
                      </div>
                    </div>

                    {otherMins && !isChecked && (
                      <span className="shrink-0 text-[10px] bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/30 px-2 py-0.5 rounded-full font-medium">
                        {t('settings.assignedToOther', { mins: otherMins })}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Modal Sticky Bottom Actions */}
        <div className="p-3.5 sm:p-4 border-t border-gray-100 dark:border-white/10 bg-white/95 dark:bg-[#0c1310]/95 backdrop-blur-md shrink-0">
          <button
            type="button"
            onClick={handleSaveAndClose}
            className="w-full btn-primary py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-primary-500/20 active:scale-[0.98] transition-transform cursor-pointer"
          >
            <Check size={18} />
            <span>{t('settings.confirm', 'حفظ')} ({selectedIds.length})</span>
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

function BotCycleIntervalsSection({ userId }: { userId?: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: castlesData, isLoading: castlesLoading } = useCastles(userId || '')
  const castles: Castle[] = castlesData?.pages ? castlesData.pages.flatMap((p: any) => p.items || []) : []

  const [groups, setGroups] = useState<IntervalGroup[]>([])
  const [initialized, setInitialized] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedSuccess, setSavedSuccess] = useState(false)
  const [activeModalGroupId, setActiveModalGroupId] = useState<string | null>(null)

  useEffect(() => {
    if (!castles.length || initialized) return
    const map = new Map<number, string[]>()
    castles.forEach(c => {
      const interval = c.loop_interval ? Number(c.loop_interval) : 40
      if (!map.has(interval)) map.set(interval, [])
      map.get(interval)!.push(c.id)
    })

    const initialGroups: IntervalGroup[] = []
    map.forEach((cIds, mins) => {
      initialGroups.push({
        id: `group_${mins}_${Math.random().toString(36).substring(2, 6)}`,
        minutes: mins,
        castleIds: cIds,
      })
    })

    if (initialGroups.length === 0) {
      initialGroups.push({
        id: 'group_default',
        minutes: 40,
        castleIds: castles.map(c => c.id),
      })
    }
    initialGroups.sort((a, b) => a.minutes - b.minutes)
    setGroups(initialGroups)
    setInitialized(true)
  }, [castles, initialized])

  const handleUpdateMinutes = (groupId: string, delta: number) => {
    setGroups(prev => prev.map(g => {
      if (g.id !== groupId) return g
      const next = Math.max(30, Math.min(180, g.minutes + delta))
      return { ...g, minutes: next }
    }))
  }

  const handleDirectMinutes = (groupId: string, val: number) => {
    setGroups(prev => prev.map(g => {
      if (g.id !== groupId) return g
      return { ...g, minutes: Math.max(30, Math.min(180, isNaN(val) ? 30 : val)) }
    }))
  }

  const handleModalConfirm = (groupId: string, newCastleIds: string[]) => {
    setGroups(prev => prev.map(g => {
      if (g.id === groupId) {
        return { ...g, castleIds: newCastleIds }
      }
      // إزالة القلاع المحددة من أي مجموعة أخرى لمنع التكرار
      const newIdsSet = new Set(newCastleIds)
      return {
        ...g,
        castleIds: g.castleIds.filter(id => !newIdsSet.has(id))
      }
    }))
  }

  const handleRemoveCastleFromGroup = (groupId: string, castleId: string) => {
    setGroups(prev => prev.map(g => {
      if (g.id !== groupId) return g
      return {
        ...g,
        castleIds: g.castleIds.filter(id => id !== castleId)
      }
    }))
  }

  const handleAddGroup = () => {
    const existingMins = groups.map(g => g.minutes)
    let candidate = 60
    if (existingMins.includes(60)) candidate = 45
    if (existingMins.includes(45)) candidate = 90
    if (existingMins.includes(candidate)) candidate = Math.min(180, Math.max(...existingMins, 30) + 15)

    setGroups(prev => [
      ...prev,
      {
        id: `group_${Date.now()}`,
        minutes: candidate,
        castleIds: [],
      }
    ])
  }

  const handleRemoveGroup = (groupId: string) => {
    setGroups(prev => prev.filter(g => g.id !== groupId))
  }

  const handleSave = async () => {
    if (!castles.length) return
    setSaving(true)
    try {
      const payload: Record<string, number> = {}
      groups.forEach(g => {
        g.castleIds.forEach(cid => {
          payload[cid] = g.minutes
        })
      })
      castles.forEach(c => {
        if (!payload[c.id]) {
          payload[c.id] = 40
        }
      })

      await updateCastlesLoopIntervals(payload)
      await queryClient.invalidateQueries({ queryKey: ['castles', userId] })
      setSavedSuccess(true)
      toast.success(t('settings.intervalsSaved'))
      setTimeout(() => setSavedSuccess(false), 2500)
    } catch (err: any) {
      toast.error(err.message || t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  const castlesById = new Map<string, Castle>(castles.map(c => [c.id, c]))
  const activeModalGroup = groups.find(g => g.id === activeModalGroupId)

  return (
    <div className="space-y-5 p-6 settings-intervals-card glass-card border border-gray-200 dark:border-white/10 bg-white/70 dark:bg-gray-900/40 backdrop-blur-md rounded-2xl shadow-sm">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex justify-center items-center bg-primary-50 dark:bg-primary-600/20 border border-primary-200 dark:border-primary-500/40 rounded-xl w-8 h-8 text-primary-600 dark:text-primary-400">
            <Clock size={17} />
          </div>
          <div>
            <h2 className="font-bold text-gray-900 dark:text-white text-base settings-section-title">
              {t('settings.botCycleIntervals')}
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-xs settings-hint-text">
              {t('settings.botCycleIntervalsDesc')}
            </p>
          </div>
        </div>

        {savedSuccess && (
          <div className="flex items-center gap-1.5 bg-emerald-50 dark:bg-emerald-500/20 px-3 py-1 border border-emerald-300 dark:border-emerald-500/40 rounded-xl font-bold text-emerald-700 dark:text-emerald-300 text-xs">
            <Check size={14} />
            <span>{t('settings.saved')}</span>
          </div>
        )}
      </div>

      {castlesLoading ? (
        <div className="flex justify-center items-center py-8 text-gray-400 text-xs">
          <span className="border-2 border-primary-500 border-t-transparent mr-2 rounded-full w-4 h-4 animate-spin" />
          <span>{t('common.loading')}</span>
        </div>
      ) : castles.length === 0 ? (
        <div className="py-6 text-center text-gray-500 text-sm">
          {t('settings.noCastlesFound')}
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((group, idx) => {
            const minRand = group.minutes
            const maxRand = group.minutes + 10
            const assignedCastles = group.castleIds
              .map(id => castlesById.get(id))
              .filter(Boolean) as Castle[]

            return (
              <div
                key={group.id}
                className="space-y-3 bg-gray-50/80 dark:bg-black/30 p-4 border border-gray-200 dark:border-white/10 rounded-2xl shadow-sm transition-all"
              >
                {/* Duration Row */}
                <div className="flex flex-wrap justify-between items-center gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-mono font-bold text-gray-400 dark:text-gray-500 text-xs bg-white dark:bg-white/5 px-2 py-1 rounded-lg border border-gray-200 dark:border-white/10">
                      #{idx + 1}
                    </span>

                    {/* Stepper Input */}
                    <div className="flex items-center bg-white dark:bg-black/50 border border-gray-300 dark:border-white/15 rounded-xl overflow-hidden shadow-inner">
                      <button
                        type="button"
                        onClick={() => handleUpdateMinutes(group.id, -5)}
                        disabled={group.minutes <= 30}
                        className="hover:bg-gray-100 dark:hover:bg-white/10 disabled:opacity-30 p-2 text-gray-600 dark:text-gray-300 disabled:cursor-not-allowed transition-colors cursor-pointer"
                        title="-5 min"
                      >
                        <Minus size={13} />
                      </button>

                      <div className="flex items-center px-2 min-w-[70px] text-center">
                        <input
                          type="number"
                          min={30}
                          max={180}
                          value={group.minutes}
                          onChange={e => handleDirectMinutes(group.id, parseInt(e.target.value, 10))}
                          className="bg-transparent text-center focus:outline-none w-full font-bold font-mono text-gray-900 dark:text-white text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                        />
                        <span className="mr-1 text-gray-500 dark:text-gray-400 text-xs font-normal">
                          {t('settings.minutesUnit')}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleUpdateMinutes(group.id, 5)}
                        disabled={group.minutes >= 180}
                        className="hover:bg-gray-100 dark:hover:bg-white/10 disabled:opacity-30 p-2 text-gray-600 dark:text-gray-300 disabled:cursor-not-allowed transition-colors cursor-pointer"
                        title="+5 min"
                      >
                        <Plus size={13} />
                      </button>
                    </div>

                    {/* Smart Jitter Badge */}
                    <div className="flex items-center gap-1.5 bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1.5 border border-emerald-300/80 dark:border-emerald-500/25 rounded-xl font-mono text-emerald-800 dark:text-emerald-300 text-xs font-medium">
                      <Dices size={13} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                      <span>
                        {minRand} ~ {maxRand} {t('settings.minutesUnit')}
                      </span>
                    </div>

                    {/* Button to Open Selection Modal */}
                    <button
                      type="button"
                      onClick={() => setActiveModalGroupId(group.id)}
                      className="flex items-center gap-1.5 bg-primary-50 hover:bg-primary-100 dark:bg-primary-500/15 dark:hover:bg-primary-500/25 border border-primary-200 dark:border-primary-500/40 text-primary-700 dark:text-primary-300 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-sm"
                    >
                      <span>🏰</span>
                      <span>{t('settings.selectCastlesBtn')}</span>
                      <span className="bg-primary-600 dark:bg-primary-400 text-white dark:text-gray-900 rounded-full text-[10px] px-1.5 py-0.2 font-mono">
                        {group.castleIds.length}
                      </span>
                    </button>
                  </div>

                  {groups.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveGroup(group.id)}
                      className="p-1.5 text-rose-500/80 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                      title={t('settings.removeGroup')}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>

                {/* Assigned Castles Display */}
                <div>
                  {assignedCastles.length === 0 ? (
                    <div
                      onClick={() => setActiveModalGroupId(group.id)}
                      className="border border-dashed border-gray-300 dark:border-white/15 rounded-xl p-3 text-center text-gray-500 dark:text-gray-400 text-xs cursor-pointer hover:border-primary-400 hover:bg-primary-50/20 dark:hover:bg-primary-500/5 transition-all flex items-center justify-center gap-2"
                    >
                      <span>🏰</span>
                      <span>{t('settings.noCastlesInGroup')} — {t('settings.clickToAssign')}</span>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2 pt-0.5">
                      {assignedCastles.map(c => {
                        const cName = c.castle_info?.lord_name || c.castle_info?.castle_name || c.email?.split('@')[0] || c.id.slice(0, 8)
                        return (
                          <div
                            key={c.id}
                            className="flex items-center gap-2 bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl px-2.5 py-1 text-xs shadow-sm"
                          >
                            <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                            <span className="font-semibold text-gray-800 dark:text-gray-100 truncate max-w-[130px]">
                              {cName}
                            </span>
                            {c.castle_info?.server_id ? (
                              <span className="font-mono text-gray-400 dark:text-gray-500 text-[10px]">
                                s{c.castle_info.server_id}
                              </span>
                            ) : null}
                            <button
                              type="button"
                              onClick={() => handleRemoveCastleFromGroup(group.id, c.id)}
                              className="text-gray-400 hover:text-rose-500 p-0.5 rounded transition-colors cursor-pointer"
                              title="إزالة القلعة من هذه المدة"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          {/* Action buttons: Add Group & Save */}
          <div className="flex flex-wrap justify-between items-center gap-3 pt-2">
            <button
              type="button"
              onClick={handleAddGroup}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-gray-50 dark:bg-white/5 dark:hover:bg-white/10 border border-gray-300 dark:border-white/10 rounded-xl text-xs font-semibold text-gray-700 dark:text-gray-200 transition-colors cursor-pointer shadow-sm"
            >
              <Plus size={14} />
              <span>{t('settings.addGroup')}</span>
            </button>

            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className={clsx(
                'flex items-center gap-2 btn-primary text-xs py-2 px-5 cursor-pointer',
                savedSuccess && 'bg-primary-600 border-primary-400 shadow-[0_0_15px_rgba(var(--theme-primary-rgb),0.5)]'
              )}
            >
              {saving ? (
                <>
                  <span className="border-2 border-white/30 border-t-white rounded-full w-3.5 h-3.5 animate-spin" />
                  <span>{t('settings.savingIntervals')}</span>
                </>
              ) : savedSuccess ? (
                <>
                  <Check size={14} className="text-white" />
                  <span>{t('settings.saved')}</span>
                </>
              ) : (
                <>
                  <Clock size={14} />
                  <span>{t('settings.saveIntervals')}</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Castle Selector Modal */}
      {activeModalGroup && (
        <CastleSelectorModal
          isOpen={Boolean(activeModalGroupId)}
          onClose={() => setActiveModalGroupId(null)}
          durationMinutes={activeModalGroup.minutes}
          allCastles={castles}
          currentGroupId={activeModalGroup.id}
          allGroups={groups}
          onConfirm={(selectedIds) => handleModalConfirm(activeModalGroup.id, selectedIds)}
        />
      )}
    </div>
  )
}
