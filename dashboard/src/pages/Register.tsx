import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, UserPlus } from 'lucide-react'
import { createUserWithEmailAndPassword } from 'firebase/auth'
import { auth } from '../lib/firebase'
import { registerUser } from '../lib/botApi'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'

export function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) { toast.error(t('register.passwordMismatch')); return }
    if (password.length < 6)  { toast.error(t('register.passwordTooShort')); return }

    setLoading(true)
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password)
      // تسجيل المستخدم في قاعدة بيانات SQLite المحلية عبر REST API
      await registerUser({
        uid:      cred.user.uid,
        email:    email.toLowerCase(),
        username: username.trim() || email.split('@')[0],
      })
      toast.success(t('register.success'))
      navigate('/dashboard')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('email-already-in-use')) {
        toast.error(t('register.emailInUse'))
      } else if (msg.includes('invalid-email')) {
        toast.error(t('register.invalidEmail'))
      } else {
        toast.error(t('register.createError', t('common.error')))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-dark-bg bg-mesh flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-primary-600/10 rounded-full blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="glass-card w-full max-w-sm p-8 relative z-10"
        style={{ boxShadow: '0 24px 64px rgba(16,185,129,0.15)' }}
      >
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-white border border-emerald-500/30 flex items-center justify-center mx-auto mb-3 p-1 shadow-md">
            <img src="/logo.png?v=2" alt="IBRA BOT" className="w-full h-full object-contain rounded-xl" />
          </div>
          <h1 className="text-xl font-bold text-white tracking-wide">{t('register.title')}</h1>
          <p className="text-emerald-400 font-medium text-xs mt-1">{t('tagline')}</p>
          <p className="text-gray-400 text-xs mt-1">{t('register.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {/* Username */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.username')}</label>
            <input
              id="reg-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="input-field"
              placeholder={t('register.usernamePlaceholder')}
            />
          </div>

          {/* Email */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.email')}</label>
            <input
              id="reg-email"
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="input-field"
              placeholder="name@example.com"
              dir="ltr"
            />
          </div>

          {/* Password */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.password')}</label>
            <div className="relative">
              <input
                id="reg-password"
                type={showPw ? 'text' : 'password'}
                required
                minLength={6}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field pe-10"
                placeholder={t('register.passwordTooShort')}
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                className="absolute inset-y-0 end-3 flex items-center text-gray-500 hover:text-gray-300"
              >
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.confirmPassword')}</label>
            <input
              id="reg-confirm"
              type="password"
              required
              minLength={6}
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              className="input-field"
              placeholder={t('register.confirmPassword')}
            />
          </div>

          {/* Free plan notice */}
          <div className="flex items-center gap-2 p-3 rounded-xl bg-primary-900/20 border border-primary-700/25 text-xs text-primary-300">
            <span>🎁</span>
            <span>{t('register.freePlanNotice')}</span>
          </div>

          {/* Submit */}
          <button
            id="register-submit"
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 gap-2 mt-1"
          >
            {loading ? (
              t('register.loading')
            ) : (
              <>
                <UserPlus size={16} />
                {t('register.submit')}
              </>
            )}
          </button>
        </form>

        {/* Back to login */}
        <p className="text-center text-sm text-gray-500 mt-5">
          {t('register.hasAccount')}{' '}
          <Link
            to="/login"
            className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
          >
            {t('register.signIn')}
          </Link>
        </p>
      </motion.div>
    </div>
  )
}
