import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export interface ConfirmRemoveSavedAccountModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  email: string
}

export function ConfirmRemoveSavedAccountModal({
  isOpen,
  onClose,
  onConfirm,
  email,
}: ConfirmRemoveSavedAccountModalProps) {
  const { t } = useTranslation()

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (typeof document === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="confirm-remove-account-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 99998,
              background: 'rgba(0, 0, 0, 0.72)',
              backdropFilter: 'blur(6px)',
              WebkitBackdropFilter: 'blur(6px)',
            }}
          />

          {/* Modal Container */}
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 99999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1rem',
              pointerEvents: 'none',
            }}
          >
            <motion.div
              key="confirm-remove-account-panel"
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              onClick={e => e.stopPropagation()}
              className="confirm-logout-modal-box relative w-full max-w-[390px] rounded-2xl overflow-hidden shadow-2xl bg-white dark:bg-[#12161f] border border-gray-200 dark:border-white/10"
              style={{
                pointerEvents: 'all',
              }}
            >
              {/* Top Accent Gradient Line */}
              <div className="h-1 w-full bg-gradient-to-r from-rose-500 via-red-500 to-rose-500" />

              <div className="p-5 sm:p-6 text-center relative">
                {/* Close Button */}
                <button
                  type="button"
                  onClick={onClose}
                  className="modal-close-btn absolute top-4 start-4 p-1.5 rounded-lg text-gray-400 hover:text-gray-200 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
                  title={t('modals.close', 'إغلاق')}
                >
                  <X size={17} />
                </button>

                {/* Trash Icon Badge */}
                <div className="mx-auto mb-3.5 flex items-center justify-center w-12 h-12 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-500 shadow-[0_0_24px_rgba(244,63,94,0.2)]">
                  <Trash2 size={22} className="text-rose-500" />
                </div>

                {/* Title */}
                <h3 className="modal-title text-base sm:text-lg font-bold text-gray-900 dark:text-white mb-2">
                  {t('modals.removeSavedAccountTitle', 'إزالة الحساب المحفوظ')}
                </h3>

                {/* Description with highlighted email */}
                <p className="modal-desc text-xs sm:text-sm text-gray-600 dark:text-gray-400 mb-2 leading-relaxed">
                  {t('modals.removeSavedAccountDesc', 'هل أنت متأكد من رغبتك في إزالة هذا الحساب من قائمة الدخول السريع؟')}
                </p>

                {email && (
                  <div className="mb-5 inline-block px-3 py-1 bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg text-xs font-semibold text-gray-800 dark:text-gray-200 dir-ltr max-w-full truncate">
                    {email}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-2.5 mt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="modal-btn-cancel flex-1 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 border border-gray-300 dark:border-white/10 transition-colors cursor-pointer"
                  >
                    {t('modals.cancel', 'إلغاء')}
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    className="modal-btn-confirm flex-1 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 shadow-[0_0_20px_rgba(244,63,94,0.3)] transition-all cursor-pointer flex items-center justify-center gap-1.5 active:scale-98"
                  >
                    <Trash2 size={14} />
                    <span>{t('modals.confirmRemoveBtn', 'إزالة الحساب')}</span>
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
