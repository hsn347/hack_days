import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import { Bot, Eye, EyeOff } from 'lucide-react'
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
      await login(email, password)
      navigate('/dashboard')
      toast.success(t('common.success'))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast.error(msg.includes('wrong-password') || msg.includes('user-not-found')
        ? 'البريد أو كلمة المرور غير صحيحة'
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
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-primary-600 flex items-center justify-center mx-auto mb-4 glow-pulse">
            <Bot size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">{t('appName')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('login.subtitle')}</p>
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
          ليس لديك حساب؟{' '}
          <Link
            to="/register"
            className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
          >
            إنشاء حساب جديد
          </Link>
        </p>
      </motion.div>
    </div>
  )
}
