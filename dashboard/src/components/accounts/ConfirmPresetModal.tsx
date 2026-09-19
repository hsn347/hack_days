import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, X, Check, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export interface ConfirmPresetModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  isBatch?: boolean
  count?: number
  lordName?: string
  email?: string
  isPending?: boolean
}

export function ConfirmPresetModal({
  isOpen,
  onClose,
  onConfirm,
  isBatch = false,
  count = 1,
  lordName,
  email,
  isPending = false,
}: ConfirmPresetModalProps) {
  const { t } = useTranslation()

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isPending) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose, isPending])

  if (typeof document === 'undefined') return null

  const presetTasks = [
    { icon: '⛏️', text: t('modals.presetTasks.gatherIron') },
    { icon: '🌊', text: t('modals.presetTasks.watermillAll') },
    { icon: '🐪', text: t('modals.presetTasks.caravan') },
    { icon: '🤝', text: t('modals.presetTasks.alliance') },
    { icon: '🐕', text: t('modals.presetTasks.petPatrol') },
    { icon: '🏛️', text: t('modals.presetTasks.tacticsHall') },
    { icon: '⛲', text: t('modals.presetTasks.fountain') },
    { icon: '🔨', text: t('modals.presetTasks.materialWorkshop') },
    { icon: '⚡', text: t('modals.presetTasks.quickGatherSkill') },
    { icon: '🌾', text: t('modals.presetTasks.harvestSkill') },
    { icon: '🗝️', text: t('modals.presetTasks.basicDungeon') },
    { icon: '🚩', text: t('modals.presetTasks.territoryExpansion') },
  ]

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="confirm-preset-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => !isPending && onClose()}
            className="fixed inset-0 z-[9998] bg-black/70 dark:bg-black/80 backdrop-blur-sm"
          />

          {/* Modal Container */}
          <div className="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-4 overflow-y-auto pointer-events-none">
            <motion.div
              key="confirm-preset-panel"
              initial={{ scale: 0.94, opacity: 0, y: 12 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 12 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              onClick={e => e.stopPropagation()}
              className="relative w-full max-w-md bg-white dark:bg-[#0c1410] text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden pointer-events-auto my-auto"
            >
              {/* Top Accent Gradient Line */}
              <div className="w-full h-1.5 bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500" />

              <div className="p-4 sm:p-6 text-start">
                {/* Header Row with Icon and Close Button */}
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-2xl bg-amber-500/15 dark:bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-600 dark:text-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.25)] shrink-0">
                      <Sparkles size={22} />
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900 dark:text-white text-base sm:text-lg leading-tight">
                        {isBatch ? t('modals.presetModalBatchTitle') : t('modals.presetModalSingleTitle')}
                      </h3>
                      <p className="text-gray-500 dark:text-gray-400 text-xs mt-0.5">
                        {isBatch
                          ? t('modals.presetModalBatchDesc', { count })
                          : (lordName || email ? `${lordName || ''} (${email || ''})` : t('modals.presetModalSingleDesc'))}
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="text-gray-400 hover:text-gray-700 dark:hover:text-white p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors cursor-pointer disabled:opacity-50"
                  >
                    <X size={18} />
                  </button>
                </div>

                {/* Grid of 12 Configured Tasks */}
                <div className="mb-5">
                  <div className="text-xs font-semibold text-gray-600 dark:text-gray-300 mb-2 flex items-center gap-1.5">
                    <Check size={14} className="text-emerald-500" />
                    <span>{t('modals.presetTasksHeading')}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 bg-gray-50 dark:bg-white/[0.02] p-2.5 rounded-xl border border-gray-200/80 dark:border-white/6 text-[11px] sm:text-xs">
                    {presetTasks.map((taskItem, idx) => (
                      <div key={idx} className="flex items-center gap-1.5 py-1 px-1.5 rounded-lg text-gray-700 dark:text-gray-300 font-medium">
                        <span className="shrink-0">{taskItem.icon}</span>
                        <span className="truncate">{taskItem.text}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2.5 pt-1">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="flex-1 py-2.5 px-4 rounded-xl font-semibold text-xs sm:text-sm bg-gray-100 hover:bg-gray-200 dark:bg-white/5 dark:hover:bg-white/10 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-white/10 transition cursor-pointer disabled:opacity-50"
                  >
                    {t('modals.cancel')}
                  </button>

                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={isPending}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 px-4 rounded-xl font-bold text-xs sm:text-sm bg-gradient-to-r from-amber-500 hover:from-amber-400 to-amber-600 hover:to-amber-500 text-gray-950 shadow-md hover:shadow-lg active:scale-98 transition cursor-pointer disabled:opacity-50"
                  >
                    {isPending ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        <span>{t('modals.saving')}</span>
                      </>
                    ) : (
                      <>
                        <Sparkles size={16} />
                        <span>{t('modals.confirmApplyPreset')}</span>
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

export default ConfirmPresetModal
