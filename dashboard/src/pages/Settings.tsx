import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { User, Lock, Eye, EyeOff, Check, Sparkles, ShieldCheck } from 'lucide-react'
import { updatePassword, EmailAuthProvider, reauthenticateWithCredential, updateProfile } from 'firebase/auth'
import { doc, updateDoc } from 'firebase/firestore'
import { motion, AnimatePresence } from 'framer-motion'
import { Layout } from '../components/layout/Layout'
import { useAuth } from '../hooks/useAuth'
import { auth, db } from '../lib/firebase'
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
      toast.error('يرجى كتابة اسم المستخدم')
      return
    }

    setSavingProfile(true)

    // 1. تحديث محلي وفوري في الذاكرة ليظهر في السايدبار والواجهة فوراً بـ 0 تأخير
    updateUserProfile({ username: trimmed })
    setSavedSuccess(true)

    try {
      // 2. تحديث قاعدة البيانات في Firestore
      await updateDoc(doc(db, 'users', user.uid), { username: trimmed })

      // 3. تحديث الاسم التعريفي في Firebase Auth
      if (firebaseUser) {
        try {
          await updateProfile(firebaseUser, { displayName: trimmed })
        } catch {
          // non-critical
        }
      }

      toast.success(`تم حفظ الاسم الجديد: ${trimmed}`, {
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
    if (newPw !== confirmPw) { toast.error('كلمتا المرور غير متطابقتين'); return }
    if (newPw.length < 6)    { toast.error('كلمة المرور يجب أن تكون 6 أحرف على الأقل'); return }
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
      toast.error(msg.includes('wrong-password') ? 'كلمة المرور الحالية غير صحيحة' : t('common.error'))
    } finally {
      setSavingPw(false)
    }
  }

  return (
    <Layout title={t('settings.title')}>
      <div className="space-y-6 mx-auto max-w-2xl">
        {/* Header */}
        <div>
          <h1 className="settings-page-title font-bold text-white text-2xl">{t('settings.title')}</h1>
          <p className="settings-page-desc mt-1 text-gray-500 text-sm">{t('settings.profileDesc')}</p>
        </div>

        {/* Profile section */}
        <div className="settings-profile-card space-y-6 p-6 glass-card">
          {/* Live Profile Header Banner */}
          <div className="settings-profile-banner flex flex-wrap justify-between items-center gap-4 bg-gradient-to-r from-primary-950/50 via-primary-900/30 to-black/40 shadow-inner p-4 border border-primary-500/30 rounded-2xl">
            <div className="flex items-center gap-3.5 min-w-0">
              {/* Avatar Circle with Ring */}
              <div className="relative shrink-0">
                <div className="settings-avatar flex justify-center items-center bg-gradient-to-br from-primary-600 via-primary-700 to-emerald-800 shadow-[0_0_20px_rgba(16,185,129,0.35)] border border-primary-400/40 rounded-2xl w-13 h-13 font-black text-white text-2xl">
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
                      className="settings-username-display font-bold text-white text-lg sm:text-xl truncate"
                    >
                      {user?.username || username || 'مستخدم جديد'}
                    </motion.h3>
                  </AnimatePresence>
                </div>
                <p className="settings-email-display font-mono text-gray-400 text-xs truncate select-all">{user?.email}</p>
              </div>
            </div>

            {savedSuccess && (
              <motion.div
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                className="settings-success-badge flex items-center gap-1.5 bg-emerald-500/20 shadow-sm px-3 py-1.5 border border-emerald-500/40 rounded-xl font-bold text-emerald-300 text-xs"
              >
                <Check size={14} />
                <span>تم الحفظ</span>
              </motion.div>
            )}
          </div>

          <div className="space-y-4">
            <div>
              <label className="settings-label block mb-1.5 text-gray-400 text-sm">{t('settings.email')}</label>
              <input
                id="settings-email"
                type="email"
                value={user?.email ?? ''}
                readOnly
                className="settings-readonly-input opacity-60 cursor-not-allowed input-field"
                dir="ltr"
              />
            </div>

            <div>
              <label className="settings-label block mb-1.5 text-gray-400 text-sm">{t('settings.username')}</label>
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
              <label className="settings-label block mb-1.5 text-gray-400 text-sm">{t('settings.castleCount')}</label>
              <div className="settings-stat-input flex items-center gap-2 opacity-60 cursor-not-allowed input-field">
                <span className="text-primary-400">🏰</span>
                <span>{user?.subscription?.current_castles_count ?? 0} {t('common.of')} {user?.subscription?.max_castles_allowed ?? 0}</span>
              </div>
            </div>

            <button
              id="save-profile-btn"
              onClick={handleSaveProfile}
              disabled={savingProfile}
              className={clsx(
                'flex items-center gap-2 transition-all duration-200 cursor-pointer btn-primary',
                savedSuccess && 'bg-emerald-600 border-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.5)]'
              )}
            >
              {savingProfile ? (
                <>
                  <span className="border-2 border-white/30 border-t-white rounded-full w-4 h-4 animate-spin" />
                  <span>جاري الحفظ...</span>
                </>
              ) : savedSuccess ? (
                <>
                  <Check size={16} className="text-white" />
                  <span>تم التحديث بنجاح!</span>
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

        {/* Change password */}
        <div className="settings-password-card space-y-5 p-6 glass-card">
          <div className="flex items-center gap-2">
            <div className="settings-lock-icon flex justify-center items-center bg-primary-700 rounded-lg w-7 h-7">
              <Lock size={15} className="text-white" />
            </div>
            <h2 className="settings-section-title font-semibold text-white">{t('settings.changePassword')}</h2>
          </div>

          <form onSubmit={handleChangePassword} className="space-y-4">
            {/* Current password */}
            <div>
              <label className="settings-label block mb-1.5 text-gray-400 text-sm">{t('settings.currentPassword')}</label>
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
                  className="settings-eye-btn absolute inset-y-0 flex items-center text-gray-500 hover:text-gray-300 end-3">
                  {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* New password */}
            <div>
              <label className="settings-label block mb-1.5 text-gray-400 text-sm">{t('settings.newPassword')}</label>
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
                  className="settings-eye-btn absolute inset-y-0 flex items-center text-gray-500 hover:text-gray-300 end-3">
                  {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <p className="settings-hint-text mt-1 text-gray-600 text-xs">{t('settings.minChars')}</p>
            </div>

            {/* Confirm password */}
            <div>
              <label className="settings-label block mb-1.5 text-gray-400 text-sm">{t('settings.confirmPassword')}</label>
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
