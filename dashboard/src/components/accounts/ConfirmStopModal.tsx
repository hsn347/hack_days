import React from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Square, X, ShieldAlert, Crown } from 'lucide-react'

export interface ConfirmStopModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  lordName?: string
  email?: string
  isAll?: boolean
  count?: number
  isPending?: boolean
}

export function ConfirmStopModal({
  isOpen,
  onClose,
  onConfirm,
  lordName,
  email,
  isAll = false,
  count = 0,
  isPending = false,
}: ConfirmStopModalProps) {
  if (typeof document === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* ─── Backdrop (Full Screen Overlay) ─── */}
          <motion.div
            key="confirm-stop-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9998,
              background: 'rgba(0, 0, 0, 0.78)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
            }}
          />

          {/* ─── Modal Container (Centered on Viewport) ─── */}
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
              key="confirm-stop-panel"
              initial={{ scale: 0.92, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 15 }}
              transition={{ type: 'spring', damping: 26, stiffness: 360 }}
              onClick={e => e.stopPropagation()}
              style={{
                pointerEvents: 'all',
                width: '100%',
                maxWidth: '440px',
                background: 'linear-gradient(145deg, rgba(20, 10, 14, 0.96) 0%, rgba(10, 10, 15, 0.98) 100%)',
                border: '1px solid rgba(244, 63, 94, 0.35)',
                borderRadius: '20px',
                backdropFilter: 'blur(30px)',
                WebkitBackdropFilter: 'blur(30px)',
                boxShadow: '0 0 0 1px rgba(244, 63, 94, 0.1), 0 24px 64px rgba(0, 0, 0, 0.75), 0 8px 30px rgba(244, 63, 94, 0.2)',
                overflow: 'hidden',
              }}
            >
              {/* Top Accent Line */}
              <div className="h-1 w-full bg-gradient-to-r from-rose-500 via-amber-500 to-rose-500" />

              <div className="p-6 text-center relative">
                {/* Close Button */}
                <button
                  type="button"
                  onClick={onClose}
                  className="absolute top-4 start-4 p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>

                {/* Animated Warning Icon */}
                <div className="mx-auto mb-4 relative flex items-center justify-center w-16 h-16 rounded-2xl bg-rose-500/15 border border-rose-500/35 text-rose-400 shadow-[0_0_30px_rgba(244,63,94,0.25)]">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-2xl bg-rose-500/20 opacity-75" />
                  <ShieldAlert size={32} className="relative text-rose-400" />
                </div>

                {/* Title */}
                <h3 className="text-xl font-bold text-white mb-1.5">
                  {isAll ? 'إيقاف جميع البوتات النشطة' : 'تأكيد إيقاف البوت'}
                </h3>
                <p className="text-xs text-gray-400 mb-4">
                  {isAll
                    ? `أنت على وشك إيقاف تشغيل البوت لجميع الحسابات النشطة (${count} حساب).`
                    : 'هل أنت متأكد من رغبتك في إيقاف تشغيل البوت لهذا الحساب؟'}
                </p>

                {/* Account Info Card (When single castle) */}
                {!isAll && (lordName || email) && (
                  <div className="mb-4 p-3 rounded-xl bg-white/[0.04] border border-white/10 text-start flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex items-center justify-center shrink-0">
                      <Crown size={18} className="text-amber-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-bold text-white truncate">
                        {lordName || 'قلعة اللورد'}
                      </div>
                      {email && (
                        <div className="text-[11px] text-gray-400 font-mono truncate">
                          {email}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Notice Box */}
                <div className="mb-6 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-start text-xs text-rose-200/90 leading-relaxed flex items-start gap-2.5">
                  <AlertTriangle size={16} className="text-rose-400 shrink-0 mt-0.5" />
                  <span>
                    سيتم إيقاف العمليات الحالية وإغلاق اتصال اللعبة بأمان، ولن يُنفّذ البوت أي دورات قادمة حتى تعيد تشغيله يدوياً.
                  </span>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="flex-1 py-2.5 px-4 rounded-xl text-xs font-semibold text-gray-300 bg-white/5 hover:bg-white/10 border border-white/10 transition-all cursor-pointer disabled:opacity-50"
                  >
                    تراجع / إلغاء
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={isPending}
                    className="flex-1 py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-rose-600 via-rose-500 to-red-600 hover:from-rose-500 hover:to-red-500 shadow-[0_0_20px_rgba(244,63,94,0.35)] transition-all cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-95"
                  >
                    <Square size={13} className="fill-white" />
                    <span>{isPending ? 'جاري الإيقاف...' : 'نعم، إيقاف البوت'}</span>
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

export default ConfirmStopModal
