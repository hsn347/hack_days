import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, UserPlus, AlertCircle } from 'lucide-react'
import { createUserWithEmailAndPassword } from 'firebase/auth'
import { auth } from '../lib/firebase'
import { registerUser } from '../lib/botApi'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import {
  normalizeEmail,
  validateEmail,
  validateRegisterPassword,
  validateConfirmPassword,
  validateUsername,
  getPasswordStrength,
  mapFirebaseAuthError,
} from '../lib/validation'

export function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)

  // Validation errors
  const [errors, setErrors] = useState<{
    username?: string
    email?: string
    password?: string
    confirm?: string
    general?: string
  }>({})

  // Real-time password strength
  const pwStrength = getPasswordStrength(password, t)

  const handleUsernameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUsername(e.target.value)
    if (errors.username || errors.general) {
      setErrors(prev => ({ ...prev, username: undefined, general: undefined }))
    }
  }

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value)
    if (errors.email || errors.general) {
      setErrors(prev => ({ ...prev, email: undefined, general: undefined }))
    }
  }

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setPassword(val)
    if (errors.password || errors.general) {
      setErrors(prev => ({ ...prev, password: undefined, general: undefined }))
    }
    // Also re-check confirm mismatch if confirm was already entered
    if (confirm && val !== confirm) {
      setErrors(prev => ({ ...prev, confirm: t('validation.passwordMismatch', 'كلمتا المرور غير متطابقتين') }))
    } else if (confirm && val === confirm) {
      setErrors(prev => ({ ...prev, confirm: undefined }))
    }
  }

  const handleConfirmChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setConfirm(val)
    if (errors.confirm || errors.general) {
      setErrors(prev => ({ ...prev, confirm: undefined, general: undefined }))
    }
  }

  const handleEmailBlur = () => {
    if (email.trim()) {
      const err = validateEmail(email, t)
      if (err) setErrors(prev => ({ ...prev, email: err }))
    }
  }

  const handlePasswordBlur = () => {
    if (password) {
      const err = validateRegisterPassword(password, t)
      if (err) setErrors(prev => ({ ...prev, password: err }))
    }
  }

  const handleConfirmBlur = () => {
    if (confirm) {
      const err = validateConfirmPassword(password, confirm, t)
      if (err) setErrors(prev => ({ ...prev, confirm: err }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Comprehensive validation of all fields before network call
    const cleanEmail = normalizeEmail(email)
    const usernameErr = validateUsername(username, t)
    const emailErr = validateEmail(cleanEmail, t)
    const passwordErr = validateRegisterPassword(password, t)
    const confirmErr = validateConfirmPassword(password, confirm, t)

    if (usernameErr || emailErr || passwordErr || confirmErr) {
      setErrors({
        username: usernameErr || undefined,
        email: emailErr || undefined,
        password: passwordErr || undefined,
        confirm: confirmErr || undefined,
      })
      return
    }

    setLoading(true)
    setErrors({})

    try {
      const cred = await createUserWithEmailAndPassword(auth, cleanEmail, password)
      // تسجيل المستخدم في قاعدة بيانات SQLite المحلية عبر REST API
      await registerUser({
        uid: cred.user.uid,
        email: cleanEmail,
        username: username.trim() || cleanEmail.split('@')[0],
      })
      toast.success(t('register.success'))
      navigate('/dashboard')
    } catch (err: unknown) {
      const mapped = mapFirebaseAuthError(err, t)
      if (mapped.field === 'email') {
        setErrors(prev => ({ ...prev, email: mapped.message }))
      } else {
        setErrors(prev => ({ ...prev, general: mapped.message }))
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
            <img
              src="/logo.png?v=2"
              alt="IBRA BOT"
              className="w-full h-full object-contain rounded-xl"
            />
          </div>
          <h1 className="text-xl font-bold text-white tracking-wide">{t('register.title')}</h1>
          <p className="text-emerald-400 font-medium text-xs mt-1">{t('tagline')}</p>
          <p className="text-gray-400 text-xs mt-1">{t('register.subtitle')}</p>
        </div>

        {/* General server error alert */}
        {errors.general && (
          <div className="mb-3.5 flex items-center gap-2 p-3 rounded-xl bg-rose-500/15 border border-rose-500/35 text-rose-300 text-xs">
            <AlertCircle size={15} className="shrink-0 text-rose-400" />
            <span>{errors.general}</span>
          </div>
        )}

        {/* Form with noValidate to prevent native browser tooltip bubbles */}
        <form noValidate onSubmit={handleSubmit} className="space-y-3.5">
          {/* Username */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.username')}</label>
            <input
              id="reg-username"
              type="text"
              value={username}
              onChange={handleUsernameChange}
              className={clsx(
                'input-field',
                errors.username && '!border-rose-500/80 !ring-1 !ring-rose-500/30 bg-rose-500/5'
              )}
              placeholder={t('register.usernamePlaceholder')}
            />
            {errors.username && (
              <p className="flex items-center gap-1.5 text-xs text-rose-400 mt-1.5">
                <AlertCircle size={13} className="shrink-0 text-rose-500" />
                <span>{errors.username}</span>
              </p>
            )}
          </div>

          {/* Email */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.email')}</label>
            <input
              id="reg-email"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={email}
              onChange={handleEmailChange}
              onBlur={handleEmailBlur}
              className={clsx(
                'input-field',
                errors.email && '!border-rose-500/80 !ring-1 !ring-rose-500/30 bg-rose-500/5'
              )}
              placeholder="name@example.com"
              dir="ltr"
            />
            {errors.email && (
              <p className="flex items-center gap-1.5 text-xs text-rose-400 mt-1.5">
                <AlertCircle size={13} className="shrink-0 text-rose-500" />
                <span>{errors.email}</span>
              </p>
            )}
          </div>

          {/* Password */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.password')}</label>
            <div className="relative">
              <input
                id="reg-password"
                type={showPw ? 'text' : 'password'}
                autoComplete="new-password"
                value={password}
                onChange={handlePasswordChange}
                onBlur={handlePasswordBlur}
                className={clsx(
                  'input-field pe-10',
                  errors.password && '!border-rose-500/80 !ring-1 !ring-rose-500/30 bg-rose-500/5'
                )}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                className="absolute inset-y-0 end-3 flex items-center text-gray-500 hover:text-gray-300 transition-colors"
                tabIndex={-1}
              >
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>

            {/* Password Strength Indicator */}
            {password && pwStrength && (
              <div className="mt-2 space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-gray-400">قوة كلمة المرور:</span>
                  <span className={clsx('font-bold', pwStrength.colorClass)}>
                    {pwStrength.label}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5 h-1">
                  <div
                    className={clsx(
                      'rounded-full transition-colors duration-300',
                      pwStrength.score >= 1 ? pwStrength.bgClass : 'bg-gray-700/50'
                    )}
                  />
                  <div
                    className={clsx(
                      'rounded-full transition-colors duration-300',
                      pwStrength.score >= 2 ? pwStrength.bgClass : 'bg-gray-700/50'
                    )}
                  />
                  <div
                    className={clsx(
                      'rounded-full transition-colors duration-300',
                      pwStrength.score >= 3 ? pwStrength.bgClass : 'bg-gray-700/50'
                    )}
                  />
                </div>
              </div>
            )}

            {errors.password && (
              <p className="flex items-center gap-1.5 text-xs text-rose-400 mt-1.5">
                <AlertCircle size={13} className="shrink-0 text-rose-500" />
                <span>{errors.password}</span>
              </p>
            )}
          </div>

          {/* Confirm Password */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('register.confirmPassword')}</label>
            <input
              id="reg-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={handleConfirmChange}
              onBlur={handleConfirmBlur}
              className={clsx(
                'input-field',
                errors.confirm && '!border-rose-500/80 !ring-1 !ring-rose-500/30 bg-rose-500/5'
              )}
              placeholder="••••••••"
            />
            {errors.confirm && (
              <p className="flex items-center gap-1.5 text-xs text-rose-400 mt-1.5">
                <AlertCircle size={13} className="shrink-0 text-rose-500" />
                <span>{errors.confirm}</span>
              </p>
            )}
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
