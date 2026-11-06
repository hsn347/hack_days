import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  Users,
  Check,
  Plus,
  Trash2,
  X,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  Shield,
  Zap,
} from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { SavedAccount } from '../../lib/savedAccounts'
import { ConfirmRemoveSavedAccountModal } from './ConfirmRemoveSavedAccountModal'
import toast from 'react-hot-toast'
import clsx from 'clsx'

interface AccountSwitcherModalProps {
  isOpen: boolean
  onClose: () => void
}

export function AccountSwitcherModal({ isOpen, onClose }: AccountSwitcherModalProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, savedAccounts, switchAccount, removeAccount, login } = useAuth()

  const [isSwitching, setIsSwitching] = useState(false)
  const [switchingEmail, setSwitchingEmail] = useState<string | null>(null)
  const [isAddingNew, setIsAddingNew] = useState(false)
  const [accountToRemove, setAccountToRemove] = useState<string | null>(null)

  // Form for adding another account
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberNew, setRememberNew] = useState(true)
  const [addError, setAddError] = useState<string | null>(null)
  const [isAddingLoading, setIsAddingLoading] = useState(false)

  // Password prompt for accounts without saved password
  const [promptAccount, setPromptAccount] = useState<SavedAccount | null>(null)
  const [promptPassword, setPromptPassword] = useState('')
  const [showPromptPassword, setShowPromptPassword] = useState(false)
  const [promptError, setPromptError] = useState<string | null>(null)

  // Escape key handler
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const currentEmail = (user?.email || '').trim().toLowerCase()

  const handleSelectAccount = async (acc: SavedAccount) => {
    if (acc.email.toLowerCase() === currentEmail) {
      onClose()
      return
    }

    // إذا لم تكن كلمة المرور محفوظة، اطلبها فوراً
    if (!acc.hasSavedPassword) {
      setPromptAccount(acc)
      setPromptPassword('')
      setPromptError(null)
      return
    }

    setIsSwitching(true)
    setSwitchingEmail(acc.email)
    try {
      const res = await switchAccount(acc.email)
      toast.success(
        t('accountSwitcher.switchSuccess', {
          name: acc.username || acc.email,
        })
      )
      onClose()
      if (res.isAdmin) {
        navigate('/admin')
      } else {
        navigate('/dashboard')
      }
    } catch {
      toast.error(
        t('accountSwitcher.switchError', 'تعذر التبديل تلقائياً، يرجى إدخال كلمة المرور')
      )
      setPromptAccount(acc)
      setPromptPassword('')
    } finally {
      setIsSwitching(false)
      setSwitchingEmail(null)
    }
  }

  const handlePromptSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!promptAccount || !promptPassword) return

    setIsSwitching(true)
    setPromptError(null)
    try {
      const res = await switchAccount(promptAccount.email, promptPassword)
      toast.success(
        t('accountSwitcher.switchSuccess', {
          name: promptAccount.username || promptAccount.email,
        })
      )
      setPromptAccount(null)
      onClose()
      if (res.isAdmin) {
        navigate('/admin')
      } else {
        navigate('/dashboard')
      }
    } catch {
      setPromptError(t('login.invalidCreds', 'البريد أو كلمة المرور غير صحيحة'))
    } finally {
      setIsSwitching(false)
    }
  }

  const handleAddNewSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newEmail.trim() || !newPassword) {
      setAddError(t('validation.passwordRequired', 'يرجى إدخال البيانات'))
      return
    }

    setIsAddingLoading(true)
    setAddError(null)
    try {
      const res = await login(newEmail.trim(), newPassword, rememberNew)
      toast.success(
        t('accountSwitcher.loginSuccess', {
          email: newEmail,
        })
      )
      setIsAddingNew(false)
      setNewEmail('')
      setNewPassword('')
      onClose()
      if (res.isAdmin) {
        navigate('/admin')
      } else {
        navigate('/dashboard')
      }
    } catch {
      setAddError(t('login.invalidCreds', 'البريد أو كلمة المرور غير صحيحة'))
    } finally {
      setIsAddingLoading(false)
    }
  }

  const handlePromptRemove = (e: React.MouseEvent, email: string) => {
    e.stopPropagation()
    setAccountToRemove(email)
  }

  const handleConfirmRemove = () => {
    if (accountToRemove) {
      removeAccount(accountToRemove)
      toast.success(t('accountSwitcher.removedSuccess', 'تم الحذف من القائمة'))
      setAccountToRemove(null)
    }
  }

  return (
    <div
      className="z-50 fixed inset-0 flex justify-center items-center bg-black/75 backdrop-blur-xs p-3 sm:p-4 animate-fade-in"
      onClick={onClose}
    >
      {/* Solid Opaque Modal Dialog */}
      <div
        className="relative bg-white dark:bg-[#0c120f] shadow-2xl border border-gray-200 dark:border-primary-500/25 rounded-2xl w-full max-w-md overflow-hidden"
        style={{
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 35px -5px rgba(var(--theme-primary-rgb), 0.18)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Top Accent Gradient Line */}
        <div className="bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600 w-full h-1" />

        <div className="p-5 sm:p-6">
          {/* Header */}
          <div className="flex justify-between items-center pb-4 border-gray-200 dark:border-white/10 border-b">
            <div className="flex items-center gap-2.5">
              <div className="flex justify-center items-center bg-primary-500/15 border border-primary-500/30 rounded-xl w-9 h-9 text-primary-500">
                <Users size={18} />
              </div>
              <div>
                <h2 className="font-bold text-gray-900 dark:text-white text-base">
                  {isAddingNew
                    ? t('accountSwitcher.addNewAccount', 'إضافة حساب عميل آخر')
                    : promptAccount
                    ? t('login.title', 'تسجيل الدخول')
                    : t('accountSwitcher.title', 'تبديل الحساب')}
                </h2>
                <p className="text-gray-500 dark:text-gray-400 text-xs">
                  {isAddingNew
                    ? t('accountSwitcher.addAccountSubtitle', 'سجل الدخول بحساب عميل إضافي للتنقل السريع')
                    : promptAccount
                    ? t('accountSwitcher.enterPasswordFor', { email: promptAccount.email })
                    : t('accountSwitcher.savedAccountsSubtitle', 'اختر حساباً للمتابعة أو التبديل السريع')}
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                if (isAddingNew) setIsAddingNew(false)
                else if (promptAccount) setPromptAccount(null)
                else onClose()
              }}
              className="hover:bg-gray-100 dark:hover:bg-white/6 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="space-y-2 py-4 max-h-[60vh] overflow-y-auto">
            {/* View 1: Password Prompt Modal for an account */}
            {promptAccount ? (
              <form onSubmit={handlePromptSubmit} className="space-y-4">
                {promptError && (
                  <div className="flex items-center gap-2 bg-rose-500/10 p-2.5 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
                    <AlertCircle size={15} className="shrink-0" />
                    <span>{promptError}</span>
                  </div>
                )}
                <div className="flex items-center gap-3 bg-gray-50 dark:bg-[#141e19] p-3 border border-gray-200 dark:border-white/10 rounded-xl">
                  <div className="flex justify-center items-center bg-primary-600 rounded-full w-10 h-10 font-bold text-white shrink-0">
                    {promptAccount.username?.[0]?.toUpperCase() || promptAccount.email[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-gray-900 dark:text-white text-sm truncate">
                      {promptAccount.username}
                    </div>
                    <div className="text-gray-500 dark:text-gray-400 text-xs truncate">
                      {promptAccount.email}
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block mb-1.5 font-medium text-gray-500 dark:text-gray-400 text-xs">
                    {t('login.password', 'كلمة المرور')}
                  </label>
                  <div className="relative">
                    <input
                      type={showPromptPassword ? 'text' : 'password'}
                      value={promptPassword}
                      onChange={e => setPromptPassword(e.target.value)}
                      placeholder="••••••••"
                      autoFocus
                      required
                      className="bg-white dark:bg-[#111915] pe-10 input-field"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPromptPassword(v => !v)}
                      className="absolute inset-y-0 flex items-center text-gray-400 hover:text-gray-200 end-3"
                    >
                      {showPromptPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setPromptAccount(null)}
                    className="flex-1 py-2 text-xs btn-secondary"
                  >
                    {t('common.cancel', 'إلغاء')}
                  </button>
                  <button
                    type="submit"
                    disabled={isSwitching || !promptPassword}
                    className="flex flex-1 justify-center items-center gap-1.5 py-2 text-xs btn-primary"
                  >
                    {isSwitching ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      t('login.submit', 'دخول')
                    )}
                  </button>
                </div>
              </form>
            ) : isAddingNew ? (
              /* View 2: Add New Client Account */
              <form onSubmit={handleAddNewSubmit} className="space-y-3.5">
                {addError && (
                  <div className="flex items-center gap-2 bg-rose-500/10 p-2.5 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
                    <AlertCircle size={15} className="shrink-0" />
                    <span>{addError}</span>
                  </div>
                )}

                <div>
                  <label className="block mb-1.5 font-medium text-gray-500 dark:text-gray-400 text-xs">
                    {t('login.email', 'البريد الإلكتروني')}
                  </label>
                  <input
                    type="email"
                    value={newEmail}
                    onChange={e => setNewEmail(e.target.value)}
                    placeholder="client@example.com"
                    autoFocus
                    required
                    className="bg-white dark:bg-[#111915] input-field"
                  />
                </div>

                <div>
                  <label className="block mb-1.5 font-medium text-gray-500 dark:text-gray-400 text-xs">
                    {t('login.password', 'كلمة المرور')}
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      className="bg-white dark:bg-[#111915] pe-10 input-field"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(v => !v)}
                      className="absolute inset-y-0 flex items-center text-gray-400 hover:text-gray-200 end-3"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <label className="flex items-center gap-2 py-1 text-gray-600 dark:text-gray-300 text-xs cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberNew}
                    onChange={e => setRememberNew(e.target.checked)}
                    className="border-gray-300 dark:border-white/20 rounded focus:ring-primary-500 text-primary-600"
                  />
                  <span>{t('accountSwitcher.rememberAccount', 'حفظ الحساب للتبديل السريع بنقرة واحدة')}</span>
                </label>

                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddingNew(false)}
                    className="flex-1 py-2 text-xs btn-secondary"
                  >
                    {t('common.cancel', 'إلغاء')}
                  </button>
                  <button
                    type="submit"
                    disabled={isAddingLoading}
                    className="flex flex-1 justify-center items-center gap-1.5 py-2 text-xs btn-primary"
                  >
                    {isAddingLoading ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      t('login.submit', 'تسجيل الدخول')
                    )}
                  </button>
                </div>
              </form>
            ) : (
              /* View 3: Accounts List */
              <>
                {savedAccounts.length === 0 ? (
                  <div className="py-6 text-gray-400 text-xs text-center">
                    {t('accountSwitcher.noSaved', 'لا توجد حسابات أخرى محفوظة على هذا المتصفح')}
                  </div>
                ) : (
                  savedAccounts.map(acc => {
                    const isCurrent = acc.email.toLowerCase() === currentEmail
                    const isThisSwitching = isSwitching && switchingEmail === acc.email

                    return (
                      <div
                        key={acc.email}
                        onClick={() => !isSwitching && handleSelectAccount(acc)}
                        className={clsx(
                          'group flex justify-between items-center p-3 border rounded-xl transition-all cursor-pointer select-none',
                          isCurrent
                            ? 'bg-primary-50/80 dark:bg-primary-950/40 border-primary-500/40 text-primary-950 dark:text-primary-100 shadow-xs'
                            : 'bg-gray-50 hover:bg-gray-100 dark:bg-[#131b17] dark:hover:bg-[#1a2520] border-gray-200 dark:border-white/10 text-gray-800 dark:text-gray-200 hover:border-gray-300 dark:hover:border-primary-500/30'
                        )}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          {/* Avatar */}
                          <div
                            className={clsx(
                              'flex justify-center items-center rounded-full w-9 h-9 font-bold text-xs transition-colors shrink-0',
                              isCurrent
                                ? 'bg-primary-600 text-white shadow-xs'
                                : 'bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-200'
                            )}
                          >
                            {acc.username?.[0]?.toUpperCase() || acc.email[0].toUpperCase()}
                          </div>

                          {/* Details */}
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-gray-900 dark:text-white text-xs truncate">
                                {acc.username || acc.email.split('@')[0]}
                              </span>
                              {isCurrent && (
                                <span className="bg-primary-500/20 px-1.5 py-0.5 border border-primary-500/30 rounded-full font-semibold text-[10px] text-primary-700 dark:text-primary-400">
                                  {t('accountSwitcher.current', 'الحالي')}
                                </span>
                              )}
                              {acc.role === 'admin' && (
                                <Shield size={12} className="text-amber-500 shrink-0" />
                              )}
                            </div>
                            <div className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400 truncate">
                              {acc.email}
                            </div>
                          </div>
                        </div>

                        {/* Right actions */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {isThisSwitching ? (
                            <Loader2 size={16} className="text-primary-500 animate-spin" />
                          ) : isCurrent ? (
                            <div className="flex justify-center items-center bg-primary-500/20 rounded-full w-6 h-6 text-primary-500">
                              <Check size={14} />
                            </div>
                          ) : (
                            <>
                              <button
                                type="button"
                                onClick={e => handlePromptRemove(e, acc.email)}
                                className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 p-2 sm:p-1.5 rounded-lg text-rose-500 sm:text-gray-400 sm:hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/15 transition-all cursor-pointer shrink-0"
                                title={t('accountSwitcher.removeTooltip', 'إزالة من القائمة')}
                              >
                                <Trash2 size={15} />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    )
                  })
                )}
              </>
            )}
          </div>

          {/* Footer actions */}
          {!promptAccount && !isAddingNew && (
            <div className="pt-3 border-gray-200 dark:border-white/10 border-t">
              <button
                onClick={() => setIsAddingNew(true)}
                className="flex justify-center items-center gap-2 bg-primary-500/5 hover:bg-primary-500/10 px-3 py-2.5 border border-primary-500/40 hover:border-primary-500 border-dashed rounded-xl w-full font-bold text-primary-600 dark:text-primary-400 text-xs transition-all cursor-pointer"
              >
                <Plus size={15} />
                <span>{t('accountSwitcher.addNewAccount', '+ إضافة حساب عميل آخر')}</span>
              </button>
            </div>
          )}
        </div>
      </div>

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
