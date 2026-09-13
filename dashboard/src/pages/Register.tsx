import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import { Bot, Eye, EyeOff, UserPlus } from 'lucide-react'
import { createUserWithEmailAndPassword } from 'firebase/auth'
import { doc, setDoc, serverTimestamp } from 'firebase/firestore'
import { auth, db } from '../lib/firebase'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'

export function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) { toast.error('كلمتا المرور غير متطابقتين'); return }
    if (password.length < 6)  { toast.error('كلمة المرور يجب أن تكون 6 أحرف على الأقل'); return }

    setLoading(true)
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password)
      // إنشاء وثيقة المستخدم في Firestore
      await setDoc(doc(db, 'users', cred.user.uid), {
        uid:        cred.user.uid,
        username:   username.trim() || email.split('@')[0],
        email:      email.toLowerCase(),
        role:       'user',
        is_banned:  false,
        created_at: new Date().toISOString(),
        subscription: {
          plan_id:                'free',
          plan_name:              'مجاني',
          status:                 'active',
          started_at:             new Date().toISOString(),
          expires_at:             new Date(Date.now() + 7 * 86400000).toISOString(),
          days_remaining:         7,
          max_castles_allowed:    1,
          current_castles_count:  0,
        },
      })
      toast.success('تم إنشاء الحساب بنجاح!')
      navigate('/dashboard')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('email-already-in-use')) {
        toast.error('هذا البريد مستخدم بالفعل')
      } else if (msg.includes('invalid-email')) {
        toast.error('البريد الإلكتروني غير صالح')
      } else {
        toast.error('حدث خطأ أثناء إنشاء الحساب')
      }
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
        <div className="text-center mb-7">
          <div className="w-14 h-14 rounded-2xl bg-primary-600 flex items-center justify-center mx-auto mb-3 glow-pulse">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">إنشاء حساب جديد</h1>
          <p className="text-gray-500 text-sm mt-1">انضم إلى OsmanliBot</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {/* Username */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">الاسم المعروض</label>
            <input
              id="reg-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="input-field"
              placeholder="مثال: أبو عمر"
            />
          </div>

          {/* Email */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">البريد الإلكتروني</label>
            <input
              id="reg-email"
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
            <label className="text-sm text-gray-400 mb-1.5 block">كلمة المرور</label>
            <div className="relative">
              <input
                id="reg-password"
                type={showPw ? 'text' : 'password'}
                required
                minLength={6}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field pe-10"
                placeholder="6 أحرف على الأقل"
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                className="absolute inset-y-0 end-3 flex items-center text-gray-500 hover:text-gray-300"
              >
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">تأكيد كلمة المرور</label>
            <input
              id="reg-confirm"
              type="password"
              required
              minLength={6}
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              className="input-field"
              placeholder="أعد كتابة كلمة المرور"
            />
          </div>

          {/* Free plan notice */}
          <div className="flex items-center gap-2 p-3 rounded-xl bg-primary-900/20 border border-primary-700/25 text-xs text-primary-300">
            <span>🎁</span>
            <span>الخطة المجانية تشمل قلعة واحدة لمدة 7 أيام</span>
          </div>

          {/* Submit */}
          <button
            id="register-submit"
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 gap-2 mt-1"
          >
            {loading ? (
              'جارٍ إنشاء الحساب...'
            ) : (
              <>
                <UserPlus size={16} />
                إنشاء حساب
              </>
            )}
          </button>
        </form>

        {/* Back to login */}
        <p className="text-center text-sm text-gray-500 mt-5">
          لديك حساب بالفعل؟{' '}
          <Link
            to="/login"
            className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
          >
            تسجيل الدخول
          </Link>
        </p>
      </motion.div>
    </div>
  )
}
