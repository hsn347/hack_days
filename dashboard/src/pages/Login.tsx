import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import {
  normalizeEmail,
  validateEmail,
  validateLoginPassword,
  mapFirebaseAuthError,
} from '../lib/validation'

export function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)

  // Validation errors
  const [errors, setErrors] = useState<{
    email?: string
    password?: string
    general?: string
  }>({})

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value)
    if (errors.email || errors.general) {
      setErrors(prev => ({ ...prev, email: undefined, general: undefined }))
    }
  }

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(e.target.value)
    if (errors.password || errors.general) {
      setErrors(prev => ({ ...prev, password: undefined, general: undefined }))
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
      const err = validateLoginPassword(password, t)
      if (err) setErrors(prev => ({ ...prev, password: err }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // 1. Comprehensive validation before touching the network
    const cleanEmail = normalizeEmail(email)
    const emailErr = validateEmail(cleanEmail, t)
    const passwordErr = validateLoginPassword(password, t)

    if (emailErr || passwordErr) {
      setErrors({
        email: emailErr || undefined,
        password: passwordErr || undefined,
      })
      return
    }

    setLoading(true)
    setErrors({})

    try {
      const res = await login(cleanEmail, password)
      if (res?.isAdmin) {
        toast.success(
          t('roles.admin', 'المشرف الأعلى') + ' — ' + t('common.success', 'تم الدخول بنجاح')
        )
        navigate('/admin')
      } else {
        toast.success(t('common.success'))
        navigate('/dashboard')
      }
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
          <div className="w-16 h-16 rounded-2xl bg-white border border-emerald-500/30 flex items-center justify-center mx-auto mb-3.5 p-1 shadow-md">
            <img
              src="/logo.png?v=2"
              alt="IBRA BOT"
              className="w-full h-full object-contain rounded-xl"
            />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-wide">IBRA BOT</h1>
          <p className="text-emerald-400 font-medium text-xs mt-1">{t('tagline')}</p>
          <p className="text-gray-400 text-xs mt-1.5">{t('login.subtitle')}</p>
        </div>

        {/* General server error alert */}
        {errors.general && (
          <div className="mb-4 flex items-center gap-2 p-3 rounded-xl bg-rose-500/15 border border-rose-500/35 text-rose-300 text-xs">
            <AlertCircle size={15} className="shrink-0 text-rose-400" />
            <span>{errors.general}</span>
          </div>
        )}

        {/* Form with noValidate to block native browser popup bubbles */}
        <form noValidate onSubmit={handleSubmit} className="space-y-4">
          {/* Email */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('login.email')}</label>
            <input
              id="email"
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
            <label className="text-sm text-gray-400 mb-1.5 block">{t('login.password')}</label>
            <div className="relative">
              <input
                id="password"
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
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
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.password && (
              <p className="flex items-center gap-1.5 text-xs text-rose-400 mt-1.5">
                <AlertCircle size={13} className="shrink-0 text-rose-500" />
                <span>{errors.password}</span>
              </p>
            )}
          </div>

          {/* Submit */}
          <button
            id="login-submit"
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 mt-2"
          >
            {loading ? t('login.loading') : t('login.submit')}
          </button>
        </form>

        {/* Link to register */}
        <p className="text-center text-sm text-gray-500 mt-5">
          {t('login.noAccount')}{' '}
          <Link
            to="/register"
            className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
          >
            {t('login.createAccount')}
          </Link>
        </p>
      </motion.div>
    </div>
  )
}
