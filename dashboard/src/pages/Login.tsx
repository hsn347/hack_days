import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'

export function LoginPage() {
  const { t }       = useTranslation()
  const { login }   = useAuth()
  const navigate    = useNavigate()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await login(email, password)
      if (res?.isAdmin) {
        toast.success(t('roles.admin', 'المشرف الأعلى') + ' — ' + t('common.success', 'تم الدخول بنجاح'))
        navigate('/admin')
      } else {
        toast.success(t('common.success'))
        navigate('/dashboard')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast.error(msg.includes('wrong-password') || msg.includes('user-not-found') || msg.includes('invalid-credential')
        ? t('login.invalidCreds')
        : t('common.error')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-dark-bg bg-mesh flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-primary-600/10 rounded-full blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="glass-card w-full max-w-sm p-8 relative z-10"
        style={{ boxShadow: '0 24px 64px rgba(16,185,129,0.15)' }}
      >
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-white border border-emerald-500/30 flex items-center justify-center mx-auto mb-3.5 p-1 shadow-md">
            <img src="/logo.png?v=2" alt="IBRA BOT" className="w-full h-full object-contain rounded-xl" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-wide">IBRA BOT</h1>
          <p className="text-emerald-400 font-medium text-xs mt-1">{t('tagline')}</p>
          <p className="text-gray-400 text-xs mt-1.5">{t('login.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('login.email')}</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="input-field"
              placeholder="name@example.com"
              dir="ltr"
            />
          </div>

          {/* Password */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">{t('login.password')}</label>
            <div className="relative">
              <input
                id="password"
                type={showPw ? 'text' : 'password'}
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field pe-10"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                className="absolute inset-y-0 end-3 flex items-center text-gray-500 hover:text-gray-300"
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            id="login-submit"
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 mt-2"
          >
            {loading ? t('login.loading') : t('login.submit')}
          </button>
        </form>

        {/* Link to register */}
        <p className="text-center text-sm text-gray-500 mt-5">
          {t('login.noAccount')}{' '}
          <Link
            to="/register"
            className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
          >
            {t('login.createAccount')}
          </Link>
        </p>
      </motion.div>
    </div>
  )
}
