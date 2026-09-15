import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, X, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export interface ConfirmDeleteCastleModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  isPending?: boolean
}

export function ConfirmDeleteCastleModal({
  isOpen,
  onClose,
  onConfirm,
  isPending = false,
}: ConfirmDeleteCastleModalProps) {
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
            key="confirm-delete-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9998,
              background: 'rgba(0, 0, 0, 0.72)',
              backdropFilter: 'blur(6px)',
              WebkitBackdropFilter: 'blur(6px)',
            }}
          />

          {/* Modal Centered Container */}
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
              key="confirm-delete-panel"
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              onClick={e => e.stopPropagation()}
              className="confirm-logout-modal-box relative w-full max-w-[380px] rounded-2xl overflow-hidden shadow-2xl"
              style={{
                pointerEvents: 'all',
              }}
            >
              {/* Top Accent Line */}
              <div className="h-1 w-full bg-gradient-to-r from-rose-500 via-red-500 to-rose-500" />

              <div className="p-5 sm:p-6 text-center relative">
                {/* Close Button */}
                <button
                  type="button"
                  onClick={onClose}
                  className="modal-close-btn absolute top-4 start-4 p-1.5 rounded-lg text-gray-400 hover:text-gray-200 dark:hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                  title={t('modals.close')}
                >
                  <X size={17} />
                </button>

                {/* Refined Trash Icon */}
                <div className="mx-auto mb-3.5 flex items-center justify-center w-12 h-12 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-400 shadow-[0_0_24px_rgba(244,63,94,0.2)]">
                  <Trash2 size={22} className="text-rose-400" />
                </div>

                {/* Title */}
                <h3 className="modal-title text-base sm:text-lg font-bold text-gray-900 dark:text-white mb-1.5">
                  {t('modals.deleteCastleTitle')}
                </h3>

                {/* Description */}
                <p className="modal-desc text-xs sm:text-sm text-gray-500 dark:text-gray-400 mb-6 leading-relaxed">
                  {t('modals.deleteCastleDesc')}
                </p>

                {/* Action Buttons */}
                <div className="flex items-center gap-2.5">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="modal-btn-cancel flex-1 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 border border-gray-300 dark:border-white/10 transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {t('modals.cancel')}
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={isPending}
                    className="modal-btn-confirm flex-1 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 shadow-[0_0_20px_rgba(244,63,94,0.3)] transition-all cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-98"
                  >
                    {isPending ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>{t('modals.deleting')}</span>
                      </>
                    ) : (
                      <>
                        <Trash2 size={14} />
                        <span>{t('modals.deleteCastleTitle')}</span>
                      </>
                    )}
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
