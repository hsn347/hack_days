import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import {
  Eye,
  EyeOff,
  AlertCircle,
  Plus,
  Trash2,
  Loader2,
  ArrowLeft,
  Shield,
  Zap,
} from 'lucide-react'
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
import { SavedAccount } from '../lib/savedAccounts'
import { ConfirmRemoveSavedAccountModal } from '../components/common/ConfirmRemoveSavedAccountModal'
import { AuthHeaderBar } from '../components/common/AuthHeaderBar'
import { useTenant } from '../context/TenantContext'

export function LoginPage() {
  const { t } = useTranslation()
  const { brandName, tagline, logoUrl } = useTenant()
  const { login, switchAccount, savedAccounts, removeAccount } = useAuth()
  const navigate = useNavigate()

  // إذا كان هناك حسابات محفوظة، نعرض قائمة الاختيار أولاً
  const [viewMode, setViewMode] = useState<'chooser' | 'form'>(
    savedAccounts.length > 0 ? 'chooser' : 'form'
  )

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [rememberAccount, setRememberAccount] = useState(true)
  const [loading, setLoading] = useState(false)
  const [switchingEmail, setSwitchingEmail] = useState<string | null>(null)
  const [accountToRemove, setAccountToRemove] = useState<string | null>(null)

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

  const handleAccountClick = async (acc: SavedAccount) => {
    if (!acc.hasSavedPassword) {
      // ملء البريد والتحويل للفورم لإدخال كلمة المرور
      setEmail(acc.email)
      setPassword('')
      setViewMode('form')
      return
    }

    setSwitchingEmail(acc.email)
    try {
      const res = await switchAccount(acc.email)
      toast.success(
        t('accountSwitcher.switchSuccess', {
          name: acc.username || acc.email,
        })
      )
      if (res?.isAdmin) {
        navigate('/admin')
      } else {
        navigate('/dashboard')
      }
    } catch {
      toast.error(
        t('accountSwitcher.switchError', 'تعذر الدخول التلقائي، يرجى إدخال كلمة المرور')
      )
      setEmail(acc.email)
      setPassword('')
      setViewMode('form')
    } finally {
      setSwitchingEmail(null)
    }
  }

  const handlePromptRemove = (e: React.MouseEvent, emailToRemove: string) => {
    e.stopPropagation()
    setAccountToRemove(emailToRemove)
  }

  const handleConfirmRemove = () => {
    if (accountToRemove) {
      removeAccount(accountToRemove)
      toast.success(t('accountSwitcher.removedSuccess', 'تم الحذف من القائمة'))
      setAccountToRemove(null)
      if (savedAccounts.length <= 1) {
        setViewMode('form')
      }
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
      const res = await login(cleanEmail, password, rememberAccount)
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
    <div className="relative flex justify-center items-center bg-[#f1f5f2] dark:bg-[#0a0f0a] p-4 min-h-screen overflow-hidden text-gray-900 dark:text-white transition-colors duration-200">
      {/* Top Header Bar with Theme & Language Switches */}
      <AuthHeaderBar />

      {/* Background ambient glow */}
      <div
        className="top-1/4 left-1/2 absolute opacity-20 blur-3xl rounded-full w-96 h-96 -translate-x-1/2 pointer-events-none"
        style={{ backgroundColor: 'var(--theme-primary)' }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{
          borderColor: 'rgba(var(--theme-primary-rgb), 0.25)',
          boxShadow: '0 24px 64px rgba(var(--theme-primary-rgb), 0.12)',
        }}
        className="z-10 relative bg-white dark:bg-[#0c120f] p-6 sm:p-8 border rounded-2xl w-full max-w-sm overflow-hidden"
      >
        {/* Top Gradient Accent */}
        <div
          className="top-0 absolute inset-x-0 h-1"
          style={{
            background: 'linear-gradient(90deg, var(--theme-primary), var(--theme-primary-light), var(--theme-primary))',
          }}
        />

        {/* Logo */}
        <div className="mb-6 text-center">
          <div
            className="flex justify-center items-center bg-gray-100 dark:bg-white/5 shadow-xs mx-auto mb-3.5 border rounded-2xl w-16 h-16 overflow-hidden"
            style={{ borderColor: 'rgba(var(--theme-primary-rgb), 0.35)' }}
          >
            <img
              src={logoUrl || '/logo.png?v=2'}
              alt={brandName}
              className="w-full h-full object-cover"
            />
          </div>
          <h1 className="font-bold text-gray-900 dark:text-white text-2xl tracking-wide">{brandName}</h1>
          {tagline ? (
            <p className="mt-1 font-bold text-xs" style={{ color: 'var(--theme-primary)' }}>{tagline}</p>
          ) : null}
        </div>

        {/* General server error alert */}
        {errors.general && (
          <div className="flex items-center gap-2 bg-rose-500/15 mb-4 p-3 border border-rose-500/35 rounded-xl text-rose-600 dark:text-rose-300 text-xs">
            <AlertCircle size={15} className="text-rose-500 shrink-0" />
            <span>{errors.general}</span>
          </div>
        )}

        {/* Mode 1: Saved Accounts Chooser */}
        {viewMode === 'chooser' && savedAccounts.length > 0 ? (
          <div className="space-y-3">
            <div className="space-y-2 pe-1 max-h-64 overflow-y-auto">
              {savedAccounts.map(acc => {
                const isLoggingIn = switchingEmail === acc.email
                return (
                  <div
                    key={acc.email}
                    onClick={() => !switchingEmail && handleAccountClick(acc)}
                    style={isLoggingIn ? { borderColor: 'var(--theme-primary)', backgroundColor: 'rgba(var(--theme-primary-rgb), 0.15)' } : {}}
                    className={clsx(
                      'group flex justify-between items-center p-3 border rounded-xl transition-all cursor-pointer select-none',
                      !isLoggingIn && 'bg-gray-50 hover:bg-gray-100/90 border-gray-200/80 text-gray-800 dark:bg-white/4 dark:hover:bg-white/8 dark:border-white/8 dark:text-white'
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className="flex justify-center items-center border rounded-full w-9 h-9 font-bold text-xs shrink-0"
                        style={{ backgroundColor: 'rgba(var(--theme-primary-rgb), 0.18)', color: 'var(--theme-primary)', borderColor: 'rgba(var(--theme-primary-rgb), 0.35)' }}
                      >
                        {acc.username?.[0]?.toUpperCase() || acc.email[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-gray-900 dark:text-white text-xs truncate">
                            {acc.username || acc.email.split('@')[0]}
                          </span>
                          {acc.role === 'admin' && (
                            <Shield size={12} className="text-amber-500 shrink-0" />
                          )}
                        </div>
                        <div className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400 truncate">
                          {acc.email}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {isLoggingIn ? (
                        <Loader2 size={16} className="animate-spin" style={{ color: 'var(--theme-primary)' }} />
                      ) : (
                        <>
                          {acc.hasSavedPassword && (
                            <span
                              className="flex items-center gap-0.5 px-1.5 py-0.5 border rounded font-semibold text-[10px]"
                              style={{ color: 'var(--theme-primary)', backgroundColor: 'rgba(var(--theme-primary-rgb), 0.12)', borderColor: 'rgba(var(--theme-primary-rgb), 0.3)' }}
                            >
                              <Zap size={10} />
                              <span>{t('accountSwitcher.instantSwitch', 'فوري')}</span>
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={e => handlePromptRemove(e, acc.email)}
                            className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 hover:bg-rose-50 dark:hover:bg-rose-500/15 p-2 sm:p-1.5 rounded-lg text-rose-500 sm:text-gray-400 sm:hover:text-rose-500 transition-all cursor-pointer shrink-0"
                            title={t('accountSwitcher.removeTooltip', 'إزالة من القائمة')}
                          >
                            <Trash2 size={15} />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Use another account button */}
            <button
              type="button"
              onClick={() => {
                setEmail('')
                setPassword('')
                setErrors({})
                setViewMode('form')
              }}
              style={{
                borderColor: 'rgba(var(--theme-primary-rgb), 0.45)',
                backgroundColor: 'rgba(var(--theme-primary-rgb), 0.08)',
                color: 'var(--theme-primary)',
              }}
              className="flex justify-center items-center gap-2 hover:opacity-90 mt-2 px-3 py-2.5 border border-dashed rounded-xl w-full font-bold text-xs transition-all cursor-pointer"
            >
              <Plus size={15} />
              <span>{t('accountSwitcher.useAnotherAccount', 'استخدام حساب آخر')}</span>
            </button>
          </div>
        ) : (
          /* Mode 2: Standard Login Form */
          <>
            {savedAccounts.length > 0 && (
              <button
                type="button"
                onClick={() => setViewMode('chooser')}
                style={{ color: 'var(--theme-primary)' }}
                className="flex items-center gap-1.5 hover:opacity-80 mb-4 font-bold text-xs transition-colors cursor-pointer"
              >
                <ArrowLeft size={14} />
                <span>
                  {t('accountSwitcher.backToSaved', 'العودة إلى الحسابات المحفوظة')} (
                  {savedAccounts.length})
                </span>
              </button>
            )}

            <form noValidate onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div>
                <label className="block mb-1.5 font-medium text-gray-700 dark:text-gray-300 text-sm">
                  {t('login.email')}
                </label>
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
                    'bg-gray-50/70 focus:bg-white dark:focus:bg-dark-surface dark:bg-dark-surface/60 border-gray-300 dark:border-white/10 text-gray-900 dark:text-white input-field',
                    errors.email && '!border-rose-500/80 !ring-1 !ring-rose-500/30 bg-rose-500/5'
                  )}
                  placeholder="name@example.com"
                  dir="ltr"
                />
                {errors.email && (
                  <p className="flex items-center gap-1.5 mt-1.5 text-rose-500 dark:text-rose-400 text-xs">
                    <AlertCircle size={13} className="shrink-0" />
                    <span>{errors.email}</span>
                  </p>
                )}
              </div>

              {/* Password */}
              <div>
                <label className="block mb-1.5 font-medium text-gray-700 dark:text-gray-300 text-sm">
                  {t('login.password')}
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPw ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={handlePasswordChange}
                    onBlur={handlePasswordBlur}
                    className={clsx(
                      'bg-gray-50/70 focus:bg-white dark:focus:bg-dark-surface dark:bg-dark-surface/60 pe-10 border-gray-300 dark:border-white/10 text-gray-900 dark:text-white input-field',
                      errors.password &&
                        '!border-rose-500/80 !ring-1 !ring-rose-500/30 bg-rose-500/5'
                    )}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(v => !v)}
                    className="absolute inset-y-0 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors end-3"
                    tabIndex={-1}
                  >
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="flex items-center gap-1.5 mt-1.5 text-rose-500 dark:text-rose-400 text-xs">
                    <AlertCircle size={13} className="shrink-0" />
                    <span>{errors.password}</span>
                  </p>
                )}
              </div>

              {/* Remember Account Checkbox */}
              <label className="flex items-center gap-2 py-1 text-gray-600 hover:text-gray-900 dark:hover:text-gray-200 dark:text-gray-400 text-xs cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberAccount}
                  onChange={e => setRememberAccount(e.target.checked)}
                  style={{ accentColor: 'var(--theme-primary)' }}
                  className="border-gray-300 dark:border-white/20 rounded focus:ring-0"
                />
                <span>{t('accountSwitcher.rememberAccount', 'حفظ الحساب للتبديل السريع بنقرة واحدة')}</span>
              </label>

              {/* Submit */}
              <button
                id="login-submit"
                type="submit"
                disabled={loading}
                style={{ backgroundColor: 'var(--theme-primary)', color: '#ffffff' }}
                className="flex justify-center items-center gap-2 hover:opacity-90 shadow-sm mt-2 py-3 rounded-xl w-full font-bold active:scale-[0.99] transition-all cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>{t('login.loading')}</span>
                  </>
                ) : (
                  t('login.submit')
                )}
              </button>
            </form>
          </>
        )}

        {/* Link to register */}
        <p className="mt-5 text-gray-500 dark:text-gray-400 text-sm text-center">
          {t('login.noAccount')}{' '}
          <Link
            to="/register"
            style={{ color: 'var(--theme-primary)' }}
            className="font-bold hover:underline transition-colors"
          >
            {t('login.createAccount')}
          </Link>
        </p>
      </motion.div>

      {/* Confirmation Modal for removing a saved account */}
      <ConfirmRemoveSavedAccountModal
        isOpen={Boolean(accountToRemove)}
        email={accountToRemove || ''}
        onClose={() => setAccountToRemove(null)}
        onConfirm={handleConfirmRemove}
      />
    </div>
  )
}
