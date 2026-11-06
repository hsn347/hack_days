import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, AlertCircle, CheckCircle, Trash2, X, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export type ConfirmVariant = 'danger' | 'warning' | 'primary' | 'success'

export interface ActionConfirmModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: ConfirmVariant
  detail?: string
  isPending?: boolean
}

export function ActionConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText,
  cancelText,
  variant = 'danger',
  detail,
  isPending = false,
}: ActionConfirmModalProps) {
  const { t } = useTranslation()

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isPending) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isPending, onClose])

  if (typeof document === 'undefined') return null

  // Variant styling helpers
  const getAccentGradient = () => {
    switch (variant) {
      case 'warning':
        return 'bg-gradient-to-r from-amber-500/0 via-amber-500 to-amber-500/0'
      case 'primary':
      case 'success':
        return 'bg-gradient-to-r from-emerald-500/0 via-emerald-500 to-emerald-500/0'
      case 'danger':
      default:
        return 'bg-gradient-to-r from-red-500/0 via-red-500 to-red-500/0'
    }
  }

  const getIcon = () => {
    switch (variant) {
      case 'warning':
        return (
          <div className="flex justify-center items-center bg-amber-500/10 border border-amber-500/20 rounded-2xl w-12 h-12 text-amber-500 dark:text-amber-400">
            <AlertCircle size={24} />
          </div>
        )
      case 'primary':
      case 'success':
        return (
          <div className="flex justify-center items-center bg-emerald-500/10 border border-emerald-500/20 rounded-2xl w-12 h-12 text-emerald-500 dark:text-emerald-400">
            <CheckCircle size={24} />
          </div>
        )
      case 'danger':
      default:
        return (
          <div className="flex justify-center items-center bg-red-500/10 border border-red-500/20 rounded-2xl w-12 h-12 text-red-500 dark:text-red-400">
            <AlertTriangle size={24} />
          </div>
        )
    }
  }

  const getConfirmBtnClasses = () => {
    switch (variant) {
      case 'warning':
        return 'bg-amber-600 hover:bg-amber-500 shadow-amber-500/25'
      case 'primary':
      case 'success':
        return 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/25'
      case 'danger':
      default:
        return 'bg-red-600 hover:bg-red-500 shadow-red-500/25'
    }
  }

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="action-confirm-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => !isPending && onClose()}
            className="z-[9998] fixed inset-0 bg-slate-900/50 dark:bg-black/75 backdrop-blur-sm"
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
              key="action-confirm-panel"
              role="dialog"
              aria-modal="true"
              initial={{ scale: 0.94, opacity: 0, y: 12 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 12 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              onClick={e => e.stopPropagation()}
              className="relative bg-white dark:bg-[#0c1410] shadow-2xl border border-gray-200 dark:border-white/10 rounded-2xl w-full max-w-[390px] overflow-hidden text-gray-900 dark:text-gray-100"
              style={{ pointerEvents: 'all' }}
            >
              {/* Accent top line */}
              <div className={`w-full h-1 ${getAccentGradient()}`} />

              <div className="space-y-4 p-5 sm:p-6 text-center">
                {/* Close Button */}
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isPending}
                  className="top-3.5 absolute hover:bg-gray-100 dark:hover:bg-white/5 disabled:opacity-40 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer start-3.5"
                  aria-label={t('common.close', 'Close')}
                >
                  <X size={16} />
                </button>

                {/* Icon */}
                <div className="flex justify-center">{getIcon()}</div>

                {/* Title & Message */}
                <div>
                  <h3 className="font-bold text-gray-900 dark:text-white text-base sm:text-lg">
                    {title}
                  </h3>
                  <p className="mt-1.5 text-gray-500 dark:text-gray-400 text-xs sm:text-sm leading-relaxed whitespace-pre-line">
                    {message}
                  </p>
                </div>

                {/* Detail Pill (if provided) */}
                {detail && (
                  <div className="bg-gray-50 dark:bg-white/[0.03] px-3 py-1.5 border border-gray-200 dark:border-white/8 rounded-xl text-center">
                    <span className="block font-mono text-gray-700 dark:text-gray-300 text-xs truncate select-all">
                      {detail}
                    </span>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2.5 pt-1">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="flex-1 hover:bg-gray-100 dark:hover:bg-white/5 disabled:opacity-50 py-2.5 border border-gray-300 dark:border-white/10 rounded-xl font-semibold text-gray-700 hover:text-gray-900 dark:hover:text-white dark:text-gray-300 text-xs sm:text-sm transition-all cursor-pointer"
                  >
                    {cancelText || t('common.cancel', 'Cancel')}
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={isPending}
                    className={`flex flex-1 justify-center items-center gap-1.5 disabled:opacity-50 shadow-md py-2.5 rounded-xl font-bold text-white text-xs sm:text-sm active:scale-[0.98] transition-all cursor-pointer ${getConfirmBtnClasses()}`}
                  >
                    {isPending ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>{t('common.loading', 'Loading...')}</span>
                      </>
                    ) : (
                      <span>{confirmText || t('common.confirm', 'Confirm')}</span>
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

export default ActionConfirmModal
