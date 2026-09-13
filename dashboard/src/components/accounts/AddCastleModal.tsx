import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Eye, EyeOff, Plus, Loader2, Mail, Lock, Sparkles } from 'lucide-react'
import { useAddCastle } from '../../hooks/useCastles'
import toast from 'react-hot-toast'

interface AddCastleModalProps {
  isOpen: boolean
  onClose: () => void
  userId: string
}

export function AddCastleModal({ isOpen, onClose, userId }: AddCastleModalProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const emailRef = useRef<HTMLInputElement>(null)

  const addCastleMutation = useAddCastle(userId)

  // Focus email on open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => emailRef.current?.focus(), 80)
    }
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password) {
      toast.error('يرجى ملء كافة الحقول')
      return
    }

    try {
      const result = await addCastleMutation.mutateAsync({
        email: email.trim(),
        password,
      })

      if (result.isPending) {
        toast('تمت إضافة الحساب في طابور الانتظار — بانتظار موافقة المسؤول', {
          icon: '🕒',
          duration: 5000,
        })
      } else {
        toast.success('✅ تمت إضافة الحساب بنجاح!')
      }

      setEmail('')
      setPassword('')
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'حدث خطأ أثناء إضافة الحساب'
      toast.error(msg)
    }
  }

  const handleClose = () => {
    if (addCastleMutation.isPending) return
    setEmail('')
    setPassword('')
    onClose()
  }

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* ─── Backdrop ─── */}
          <motion.div
            key="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            onClick={handleClose}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9998,
              background: 'rgba(0,0,0,0.72)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
            }}
          />

          {/* ─── Modal Panel ─── */}
          <motion.div
            key="modal-panel"
            initial={{ scale: 0.92, opacity: 0, y: 24 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.94, opacity: 0, y: 16 }}
            transition={{ type: 'spring', stiffness: 420, damping: 30 }}
            onClick={e => e.stopPropagation()}
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
            <div
              style={{
                pointerEvents: 'all',
                width: '100%',
                maxWidth: '440px',
                background: 'linear-gradient(145deg, rgba(10,20,12,0.92) 0%, rgba(14,26,14,0.88) 100%)',
                border: '1px solid rgba(34,197,94,0.22)',
                borderRadius: '20px',
                backdropFilter: 'blur(40px)',
                WebkitBackdropFilter: 'blur(40px)',
                boxShadow: '0 0 0 1px rgba(34,197,94,0.08), 0 24px 64px rgba(0,0,0,0.55), 0 8px 24px rgba(16,185,129,0.12)',
                overflow: 'hidden',
              }}
            >
              {/* ─ Green glow accent bar at the top ─ */}
              <div
                style={{
                  height: '2px',
                  background: 'linear-gradient(90deg, transparent 0%, #10b981 40%, #22c55e 60%, transparent 100%)',
                  opacity: 0.9,
                }}
              />

              <div style={{ padding: '28px 28px 24px' }}>
                {/* ─ Header ─ */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #065f46 0%, #047857 100%)',
                        border: '1px solid rgba(16,185,129,0.35)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: '0 0 16px rgba(16,185,129,0.25)',
                        flexShrink: 0,
                      }}
                    >
                      <Sparkles size={18} color="#6ee7b7" />
                    </div>
                    <div>
                      <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f0fdf4', letterSpacing: '-0.01em' }}>
                        إضافة حساب جديد
                      </h2>
                      <p style={{ margin: '3px 0 0', fontSize: '12px', color: '#6b7280' }}>
                        أدخل بيانات حساب اللعبة
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={addCastleMutation.isPending}
                    style={{
                      padding: '6px',
                      borderRadius: '8px',
                      border: '1px solid rgba(255,255,255,0.08)',
                      background: 'rgba(255,255,255,0.05)',
                      color: '#9ca3af',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => {
                      const t = e.currentTarget
                      t.style.background = 'rgba(255,255,255,0.1)'
                      t.style.color = '#fff'
                    }}
                    onMouseLeave={e => {
                      const t = e.currentTarget
                      t.style.background = 'rgba(255,255,255,0.05)'
                      t.style.color = '#9ca3af'
                    }}
                  >
                    <X size={16} />
                  </button>
                </div>

                {/* ─ Form ─ */}
                <form onSubmit={handleSubmit}>
                  {/* Email */}
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>
                      البريد الإلكتروني
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Mail size={15} style={{
                        position: 'absolute',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        right: '12px',
                        color: '#4b5563',
                        pointerEvents: 'none',
                      }} />
                      <input
                        id="new-castle-email"
                        ref={emailRef}
                        type="email"
                        required
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        placeholder="example@gmail.com"
                        dir="ltr"
                        style={{
                          width: '100%',
                          background: 'rgba(255,255,255,0.05)',
                          border: '1px solid rgba(255,255,255,0.10)',
                          borderRadius: '12px',
                          padding: '11px 40px 11px 14px',
                          fontSize: '14px',
                          color: '#f0fdf4',
                          outline: 'none',
                          boxSizing: 'border-box',
                          transition: 'border-color 0.2s, box-shadow 0.2s',
                          fontFamily: 'inherit',
                        }}
                        onFocus={e => {
                          e.target.style.borderColor = 'rgba(34,197,94,0.5)'
                          e.target.style.boxShadow = '0 0 0 3px rgba(34,197,94,0.10)'
                          e.target.style.background = 'rgba(255,255,255,0.07)'
                        }}
                        onBlur={e => {
                          e.target.style.borderColor = 'rgba(255,255,255,0.10)'
                          e.target.style.boxShadow = 'none'
                          e.target.style.background = 'rgba(255,255,255,0.05)'
                        }}
                      />
                    </div>
                  </div>

                  {/* Password */}
                  <div style={{ marginBottom: '24px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>
                      كلمة المرور
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Lock size={15} style={{
                        position: 'absolute',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        right: '12px',
                        color: '#4b5563',
                        pointerEvents: 'none',
                      }} />
                      <input
                        id="new-castle-password"
                        type={showPassword ? 'text' : 'password'}
                        required
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="••••••••"
                        dir="ltr"
                        style={{
                          width: '100%',
                          background: 'rgba(255,255,255,0.05)',
                          border: '1px solid rgba(255,255,255,0.10)',
                          borderRadius: '12px',
                          padding: '11px 40px 11px 44px',
                          fontSize: '14px',
                          color: '#f0fdf4',
                          outline: 'none',
                          boxSizing: 'border-box',
                          transition: 'border-color 0.2s, box-shadow 0.2s',
                          fontFamily: 'inherit',
                          letterSpacing: showPassword ? 'normal' : '0.15em',
                        }}
                        onFocus={e => {
                          e.target.style.borderColor = 'rgba(34,197,94,0.5)'
                          e.target.style.boxShadow = '0 0 0 3px rgba(34,197,94,0.10)'
                          e.target.style.background = 'rgba(255,255,255,0.07)'
                        }}
                        onBlur={e => {
                          e.target.style.borderColor = 'rgba(255,255,255,0.10)'
                          e.target.style.boxShadow = 'none'
                          e.target.style.background = 'rgba(255,255,255,0.05)'
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(v => !v)}
                        style={{
                          position: 'absolute',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          left: '12px',
                          background: 'none',
                          border: 'none',
                          color: '#6b7280',
                          cursor: 'pointer',
                          padding: '2px',
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  {/* ─ Divider ─ */}
                  <div style={{ height: '1px', background: 'rgba(255,255,255,0.07)', marginBottom: '20px' }} />

                  {/* ─ Buttons ─ */}
                  <div style={{ display: 'flex', gap: '10px' }}>
                    {/* Cancel */}
                    <button
                      type="button"
                      onClick={handleClose}
                      disabled={addCastleMutation.isPending}
                      style={{
                        flex: 1,
                        padding: '11px',
                        borderRadius: '12px',
                        border: '1px solid rgba(255,255,255,0.10)',
                        background: 'rgba(255,255,255,0.05)',
                        color: '#9ca3af',
                        fontSize: '14px',
                        fontWeight: 500,
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={e => {
                        const t = e.currentTarget
                        t.style.background = 'rgba(255,255,255,0.09)'
                        t.style.color = '#d1d5db'
                      }}
                      onMouseLeave={e => {
                        const t = e.currentTarget
                        t.style.background = 'rgba(255,255,255,0.05)'
                        t.style.color = '#9ca3af'
                      }}
                    >
                      إلغاء
                    </button>

                    {/* Submit */}
                    <button
                      type="submit"
                      id="submit-add-castle"
                      disabled={addCastleMutation.isPending}
                      style={{
                        flex: 1,
                        padding: '11px',
                        borderRadius: '12px',
                        border: '1px solid rgba(34,197,94,0.40)',
                        background: addCastleMutation.isPending
                          ? 'rgba(16,185,129,0.25)'
                          : 'linear-gradient(135deg, #059669 0%, #10b981 50%, #22c55e 100%)',
                        color: '#fff',
                        fontSize: '14px',
                        fontWeight: 600,
                        cursor: addCastleMutation.isPending ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        boxShadow: addCastleMutation.isPending ? 'none' : '0 4px 20px rgba(16,185,129,0.35)',
                        transition: 'all 0.18s',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={e => {
                        if (!addCastleMutation.isPending) {
                          const t = e.currentTarget
                          t.style.boxShadow = '0 6px 28px rgba(16,185,129,0.50)'
                          t.style.transform = 'translateY(-1px)'
                        }
                      }}
                      onMouseLeave={e => {
                        if (!addCastleMutation.isPending) {
                          const t = e.currentTarget
                          t.style.boxShadow = '0 4px 20px rgba(16,185,129,0.35)'
                          t.style.transform = 'translateY(0)'
                        }
                      }}
                    >
                      {addCastleMutation.isPending ? (
                        <>
                          <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                          <span>جارٍ الإضافة...</span>
                        </>
                      ) : (
                        <>
                          <Plus size={16} />
                          <span>إضافة الحساب</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
