import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, RotateCw, Loader2, Mail, Lock, Edit3 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useUpdateCastleCredentials } from '../../hooks/useCastles'
import type { Castle } from '../../types'
import toast from 'react-hot-toast'

interface EditCastleModalProps {
  castle: Castle | null
  isOpen: boolean
  onClose: () => void
  userId: string
}

export function EditCastleModal({ castle, isOpen, onClose, userId }: EditCastleModalProps) {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const updateMutation = useUpdateCastleCredentials(userId)

  useEffect(() => {
    if (castle) {
      setEmail(castle.email || '')
      setPassword('') // أبداً لا يتم ملء أو استرجاع كلمة المرور الحالية
    }
  }, [castle, isOpen])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) {
      toast.error(t('modals.fillAllFields'))
      return
    }

    try {
      await updateMutation.mutateAsync({
        castleId: castle!.id,
        email: email.trim(),
        password: password.trim() || undefined,
      })
      toast.success('✅ ' + t('common.success'))
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast.error(msg)
    }
  }

  const handleClose = () => {
    if (updateMutation.isPending) return
    onClose()
  }

  return createPortal(
    <AnimatePresence>
      {isOpen && castle && (
        <>
          {/* Backdrop */}
          <motion.div
            key="edit-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={handleClose}
            className="modal-backdrop"
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9998,
              background: 'rgba(0,0,0,0.72)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
            }}
          />

          {/* Modal Panel Container */}
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1rem',
              pointerEvents: 'none',
            }}
          >
            <motion.div
              key="edit-panel"
              initial={{ scale: 0.94, opacity: 0, y: 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 12 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              onClick={e => e.stopPropagation()}
              className="edit-castle-modal-box relative w-full max-w-[440px] rounded-2xl overflow-hidden shadow-2xl"
              style={{
                pointerEvents: 'all',
              }}
            >
              {/* Green glow accent bar */}
              <div
                style={{
                  height: '2px',
                  background: 'linear-gradient(90deg, transparent 0%, #10b981 40%, #22c55e 60%, transparent 100%)',
                  opacity: 0.9,
                }}
              />

              <div className="p-6 sm:p-7">
                {/* Header */}
                <div className="flex items-start justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-600/25 to-teal-600/25 border border-emerald-500/40 flex items-center justify-center shrink-0 shadow-sm"
                    >
                      <Edit3 size={18} className="text-emerald-400" />
                    </div>
                    <div>
                      <h2 className="edit-modal-title m-0 text-base font-bold text-gray-900 dark:text-emerald-50">
                        {t('modals.editCastleTitle')}
                      </h2>
                      <p className="edit-modal-subtitle m-0 text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate max-w-[240px]">
                        {castle.email}
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={updateMutation.isPending}
                    className="edit-modal-btn-close p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-white bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 border border-gray-200 dark:border-white/8 transition-colors cursor-pointer"
                    title={t('modals.close')}
                  >
                    <X size={16} />
                  </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit}>
                  {/* Email Field */}
                  <div className="mb-4">
                    <label className="edit-modal-label block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
                      {t('settings.email')}
                    </label>
                    <div className="relative">
                      <Mail size={15} className="absolute top-1/2 -translate-y-1/2 end-3 text-gray-400 pointer-events-none" />
                      <input
                        id="edit-castle-email"
                        type="email"
                        required
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        dir="ltr"
                        className="edit-modal-input w-full bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-xl py-2.5 pe-9 ps-3.5 text-sm text-gray-900 dark:text-emerald-50 placeholder-gray-400 dark:placeholder-gray-500 outline-none transition-all focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                      />
                    </div>
                  </div>

                  {/* Password Field */}
                  <div className="mb-6">
                    <label className="edit-modal-label block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
                      {t('settings.newPassword')}
                    </label>
                    <div className="relative">
                      <Lock size={15} className="absolute top-1/2 -translate-y-1/2 end-3 text-gray-400 pointer-events-none" />
                      <input
                        id="edit-castle-password"
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder={t('modals.leaveEmptyToKeep')}
                        dir="ltr"
                        autoComplete="new-password"
                        className="edit-modal-input w-full bg-white dark:bg-white/5 border border-gray-300 dark:border-white/10 rounded-xl py-2.5 pe-9 ps-3.5 text-sm text-gray-900 dark:text-emerald-50 placeholder-gray-400 dark:placeholder-gray-500 outline-none transition-all focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                      />
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="edit-modal-divider h-[1px] bg-gray-200 dark:bg-white/8 mb-5" />

                  {/* Action Buttons */}
                  <div className="flex gap-2.5">
                    <button
                      type="button"
                      onClick={handleClose}
                      disabled={updateMutation.isPending}
                      className="edit-modal-btn-cancel flex-1 py-2.5 px-3 rounded-xl text-xs sm:text-sm font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 border border-gray-300 dark:border-white/10 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {t('modals.cancel')}
                    </button>

                    <button
                      type="submit"
                      id="submit-edit-castle"
                      disabled={updateMutation.isPending}
                      className="edit-modal-btn-submit flex-1 py-2.5 px-3 rounded-xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 hover:from-emerald-500 hover:to-teal-400 shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-all cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-98"
                    >
                      {updateMutation.isPending ? (
                        <>
                          <Loader2 size={15} className="animate-spin" />
                          <span>{t('modals.saving')}</span>
                        </>
                      ) : (
                        <>
                          <RotateCw size={14} />
                          <span>{t('modals.saveChanges')}</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
