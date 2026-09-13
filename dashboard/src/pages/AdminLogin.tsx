import React, { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { Shield, Lock, Mail, Eye, EyeOff, AlertTriangle, ArrowRight, CheckCircle2, ShieldAlert } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAdminAuth } from '../hooks/useAdminAuth'
import toast from 'react-hot-toast'

export function AdminLoginPage() {
  const { isAuthenticated, loginAdmin, isLocked, lockCountdown, failedAttempts } = useAdminAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  // إذا كان مسجل دخول كمسؤول بالفعل، توجه مباشرة للوحة الإدارة
  if (isAuthenticated) {
    return <Navigate to="/admin" replace />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      toast.error('يرجى ملء جميع الحقول')
      return
    }

    if (isLocked) {
      toast.error(`النظام مقفل أمنياً. انتظر ${lockCountdown} ثانية`)
      return
    }

    setLoading(true)
    setErrorMsg('')

    try {
      await loginAdmin(email, password)
      toast.success('تم التحقق بنجاح — مرحباً بك في بوابة الإدارة العليا')
      navigate('/admin')
    } catch (err: any) {
      setErrorMsg(err.message || 'فشلت عملية التحقق الأمني')
      toast.error(err.message || 'فشل تسجيل الدخول')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#050806] text-white flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* ── Background Elements ── */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 -start-20 w-96 h-96 bg-emerald-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 -end-20 w-96 h-96 bg-amber-600/10 rounded-full blur-[120px]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.08)_0,transparent_70%)]" />
      </div>

      {/* ── Login Box ── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md relative z-10"
      >
        <div className="backdrop-blur-2xl bg-black/65 border-2 border-emerald-500/30 rounded-3xl p-6 sm:p-8 shadow-[0_0_50px_rgba(16,185,129,0.15)] relative overflow-hidden">
          {/* Top glowing ambient beam */}
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent animate-pulse" />

          {/* Header & Shield Icon */}
          <div className="text-center mb-7">
            <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/20 via-emerald-600/30 to-amber-500/20 border border-emerald-500/50 shadow-[0_0_25px_rgba(16,185,129,0.35)] mb-4">
              <Shield size={32} className="text-emerald-400" />
              <Lock size={15} className="absolute -bottom-1 -end-1 text-amber-400 bg-black/80 rounded-full p-0.5 border border-amber-400" />
            </div>

            <h1 className="text-2xl font-black tracking-wide text-white mb-1.5">
              بوابة الإدارة المركزية
            </h1>
            <p className="text-xs text-gray-400">
              منطقة شديدة الحماية — مخصصة للمشرفين المعتمدين فقط
            </p>

            <div className="mt-3 inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/25 px-3 py-1 rounded-full text-[11px] text-emerald-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
              <span>مراقبة وتشفير عالي الأمان (Zero-Trust)</span>
            </div>
          </div>

          {/* Brute Force Lockout Alert Banner */}
          <AnimatePresence>
            {isLocked && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mb-5 bg-rose-500/20 border border-rose-500/50 rounded-2xl p-4 text-center text-rose-300"
              >
                <div className="flex items-center justify-center gap-2 font-bold text-sm mb-1">
                  <ShieldAlert size={18} className="text-rose-400" />
                  <span>النظام في وضع الحماية المؤقتة!</span>
                </div>
                <div className="text-xs text-rose-200/90 mb-2">
                  تم رصد تكرار محاولات خاطئة. تم قفل تسجيل الدخول مؤقتاً لحماية النظام.
                </div>
                <div className="inline-block bg-black/50 border border-rose-500/30 px-3 py-1 rounded-lg font-mono font-bold text-base text-rose-400">
                  يرجى الانتظار: {lockCountdown} ثانية
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error Message Box */}
          {errorMsg && !isLocked && (
            <div className="mb-5 bg-rose-500/15 border border-rose-500/40 rounded-xl p-3 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertTriangle size={16} className="text-rose-400 flex-shrink-0 mt-0.5" />
              <div className="leading-relaxed">{errorMsg}</div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                بريد المشرف الإلكتروني
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 start-0 flex items-center ps-3.5 pointer-events-none text-gray-500">
                  <Mail size={16} />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading || isLocked}
                  placeholder="admin@osmanli.com"
                  dir="ltr"
                  required
                  className="w-full bg-white/5 border border-white/10 focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/40 rounded-xl py-2.5 ps-10 pe-4 text-sm text-white placeholder-gray-600 transition disabled:opacity-50 disabled:cursor-not-allowed font-mono"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                كلمة المرور
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 start-0 flex items-center ps-3.5 pointer-events-none text-gray-500">
                  <Lock size={16} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading || isLocked}
                  placeholder="••••••••••••"
                  dir="ltr"
                  required
                  className="w-full bg-white/5 border border-white/10 focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/40 rounded-xl py-2.5 ps-10 pe-10 text-sm text-white placeholder-gray-600 transition disabled:opacity-50 disabled:cursor-not-allowed font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3 text-gray-500 hover:text-white transition"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Failed Attempts Counter */}
            {failedAttempts > 0 && !isLocked && (
              <div className="text-[11px] text-amber-400/90 text-center">
                ⚠️ محاولة خاطئة: {failedAttempts} من 3 قبل تفعيل القفل الأمني
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || isLocked}
              className="w-full mt-2 bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold py-3 rounded-xl shadow-[0_0_25px_rgba(16,185,129,0.35)] transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>جاري التحقق والمصادقة الأمنية...</span>
                </>
              ) : (
                <>
                  <Shield size={16} />
                  <span>دخول بوابة المشرف</span>
                </>
              )}
            </button>
          </form>

          {/* Back link */}
          <div className="mt-6 pt-4 border-t border-white/10 text-center">
            <button
              onClick={() => navigate('/dashboard')}
              className="text-xs text-gray-500 hover:text-gray-300 transition inline-flex items-center gap-1.5"
            >
              <span>العودة إلى لوحة المستخدمين</span>
              <ArrowRight size={13} />
            </button>
          </div>
        </div>

        {/* Security Disclaimers */}
        <div className="mt-4 text-center text-[11px] text-gray-600 space-y-1">
          <div>🛡️ حماية مشددة • يتم تسجيل وتتبع جميع محاولات الدخول عبر المعرف الرقمي</div>
          <div>All Unauthorized Access Attempts Are Monitored and Logged</div>
        </div>
      </motion.div>
    </div>
  )
}
