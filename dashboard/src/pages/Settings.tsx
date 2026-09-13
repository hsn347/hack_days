import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { User, Lock, Eye, EyeOff } from 'lucide-react'
import { updatePassword, EmailAuthProvider, reauthenticateWithCredential } from 'firebase/auth'
import { doc, updateDoc } from 'firebase/firestore'
import { Layout } from '../components/layout/Layout'
import { useAuth } from '../hooks/useAuth'
import { auth, db } from '../lib/firebase'
import toast from 'react-hot-toast'

export function SettingsPage() {
  const { t } = useTranslation()
  const { user, firebaseUser } = useAuth()

  const [username, setUsername] = useState(user?.username ?? '')
  const [savingProfile, setSavingProfile] = useState(false)

  const [currentPw, setCurrentPw]   = useState('')
  const [newPw, setNewPw]           = useState('')
  const [confirmPw, setConfirmPw]   = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew]         = useState(false)
  const [savingPw, setSavingPw]       = useState(false)

  const handleSaveProfile = async () => {
    if (!user) return
    setSavingProfile(true)
    try {
      await updateDoc(doc(db, 'users', user.uid), { username })
      toast.success(t('common.success'))
    } catch {
      toast.error(t('common.error'))
    } finally {
      setSavingProfile(false)
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
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">{t('settings.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('settings.profileDesc')}</p>
        </div>

        {/* Profile section */}
        <div className="glass-card p-6 space-y-5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary-700 flex items-center justify-center">
              <User size={15} className="text-white" />
            </div>
            <h2 className="font-semibold text-white">{t('settings.profile')}</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{t('settings.email')}</label>
              <input
                id="settings-email"
                type="email"
                value={user?.email ?? ''}
                readOnly
                className="input-field opacity-60 cursor-not-allowed"
                dir="ltr"
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{t('settings.username')}</label>
              <input
                id="settings-username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="input-field"
                placeholder={t('settings.username')}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{t('settings.castleCount')}</label>
              <div className="input-field opacity-60 cursor-not-allowed flex items-center gap-2">
                <span className="text-primary-400">🏰</span>
                <span>{user?.subscription?.current_castles_count ?? 0} {t('common.of')} {user?.subscription?.max_castles_allowed ?? 0}</span>
              </div>
            </div>

            <button
              id="save-profile-btn"
              onClick={handleSaveProfile}
              disabled={savingProfile}
              className="btn-primary"
            >
              {savingProfile ? t('common.loading') : t('settings.saveProfile')}
            </button>
          </div>
        </div>

        {/* Change password */}
        <div className="glass-card p-6 space-y-5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary-700 flex items-center justify-center">
              <Lock size={15} className="text-white" />
            </div>
            <h2 className="font-semibold text-white">{t('settings.changePassword')}</h2>
          </div>

          <form onSubmit={handleChangePassword} className="space-y-4">
            {/* Current password */}
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{t('settings.currentPassword')}</label>
              <div className="relative">
                <input
                  id="current-password"
                  type={showCurrent ? 'text' : 'password'}
                  required
                  value={currentPw}
                  onChange={e => setCurrentPw(e.target.value)}
                  className="input-field pe-10"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowCurrent(v => !v)}
                  className="absolute inset-y-0 end-3 flex items-center text-gray-500 hover:text-gray-300">
                  {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* New password */}
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{t('settings.newPassword')}</label>
              <div className="relative">
                <input
                  id="new-password"
                  type={showNew ? 'text' : 'password'}
                  required
                  minLength={6}
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  className="input-field pe-10"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowNew(v => !v)}
                  className="absolute inset-y-0 end-3 flex items-center text-gray-500 hover:text-gray-300">
                  {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <p className="text-xs text-gray-600 mt-1">{t('settings.minChars')}</p>
            </div>

            {/* Confirm password */}
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{t('settings.confirmPassword')}</label>
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
