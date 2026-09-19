import React, { useState, useEffect, createContext, useContext } from 'react'
import {
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
} from 'firebase/auth'
import { auth } from '../lib/firebase'
import { getUserProfile } from '../lib/botApi'
import type { User } from '../types'

interface AdminSession {
  uid: string
  email: string
  role: 'admin'
  expiresAt: number
  token: string
}

interface AdminAuthContextType {
  adminUser: User | null
  isAuthenticated: boolean
  loading: boolean
  failedAttempts: number
  isLocked: boolean
  lockCountdown: number
  loginAdmin: (email: string, pass: string) => Promise<void>
  logoutAdmin: () => Promise<void>
  refreshSession: () => void
}

const ADMIN_SESSION_KEY = 'osmanli_admin_session_token'
const FAILED_ATTEMPTS_KEY = 'osmanli_admin_failed_attempts'
const LOCK_UNTIL_KEY = 'osmanli_admin_lock_until'
const SESSION_DURATION_MS = 60 * 60 * 1000 // 60 دقيقة
const MAX_FAILED_ATTEMPTS = 3
const LOCKOUT_DURATION_SEC = 60 // حظر مؤقت لمدة 60 ثانية

export const AdminAuthContext = createContext<AdminAuthContextType | null>(null)

export function useAdminAuthProvider(): AdminAuthContextType {
  const [adminUser, setAdminUser] = useState<User | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [failedAttempts, setFailedAttempts] = useState<number>(() => {
    return parseInt(sessionStorage.getItem(FAILED_ATTEMPTS_KEY) || '0', 10)
  })
  const [isLocked, setIsLocked] = useState(false)
  const [lockCountdown, setLockCountdown] = useState(0)

  // ─── إدارة مؤقت القفل الأمني (Brute Force Defense) ─────────────
  useEffect(() => {
    const checkLock = () => {
      const lockUntil = parseInt(sessionStorage.getItem(LOCK_UNTIL_KEY) || '0', 10)
      const now = Date.now()
      if (lockUntil > now) {
        setIsLocked(true)
        setLockCountdown(Math.ceil((lockUntil - now) / 1000))
      } else {
        setIsLocked(false)
        setLockCountdown(0)
        sessionStorage.removeItem(LOCK_UNTIL_KEY)
      }
    }

    checkLock()
    const timer = setInterval(checkLock, 1000)
    return () => clearInterval(timer)
  }, [])

  // ─── التحقق من الجلسة المخزنة وتزامن تسجيل الدخول مع Firebase ─────
  useEffect(() => {
    const verifySession = async () => {
      try {
        const raw = sessionStorage.getItem(ADMIN_SESSION_KEY)
        if (!raw) {
          setIsAuthenticated(false)
          setAdminUser(null)
          setLoading(false)
          return
        }

        const session: AdminSession = JSON.parse(raw)
        if (Date.now() > session.expiresAt) {
          sessionStorage.removeItem(ADMIN_SESSION_KEY)
          setIsAuthenticated(false)
          setAdminUser(null)
          setLoading(false)
          return
        }

        const isSuperAdminEmail = session.email?.toLowerCase() === 'ibraboths@gmail.com'
        const profile = await getUserProfile()

        if ((profile && profile.role === 'admin') || isSuperAdminEmail) {
          setAdminUser({ uid: session.uid, ...(profile || {}), email: session.email, role: 'admin' } as User)
          setIsAuthenticated(true)
        } else {
          sessionStorage.removeItem(ADMIN_SESSION_KEY)
          setIsAuthenticated(false)
          setAdminUser(null)
        }
      } catch {
        sessionStorage.removeItem(ADMIN_SESSION_KEY)
        setIsAuthenticated(false)
        setAdminUser(null)
      } finally {
        setLoading(false)
      }
    }

    const unsub = onAuthStateChanged(auth, async (fbUser) => {
      if (fbUser) {
        const userEmail = (fbUser.email || '').trim().toLowerCase()
        const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

        const profile = await getUserProfile()

        if ((profile && profile.role === 'admin') || isSuperAdminEmail) {
          const sessionToken = `sec_admin_${fbUser.uid}_${Date.now()}`
          const sessionData: AdminSession = {
            uid: fbUser.uid,
            email: fbUser.email || userEmail,
            role: 'admin',
            expiresAt: Date.now() + SESSION_DURATION_MS,
            token: sessionToken,
          }
          sessionStorage.setItem(ADMIN_SESSION_KEY, JSON.stringify(sessionData))
          setAdminUser({ uid: fbUser.uid, ...(profile || {}), email: fbUser.email, role: 'admin' } as User)
          setIsAuthenticated(true)
          setLoading(false)
          return
        }
      }
      verifySession()
    })

    return () => unsub()
  }, [])

  // ─── تسجيل دخول المسؤول ─────────────────────────────────────────
  const loginAdmin = async (email: string, pass: string) => {
    const lockUntil = parseInt(sessionStorage.getItem(LOCK_UNTIL_KEY) || '0', 10)
    if (lockUntil > Date.now()) {
      const remaining = Math.ceil((lockUntil - Date.now()) / 1000)
      throw new Error(`النظام مقفل أمنياً بسبب تكرار المحاولات الخاطئة. يرجى الانتظار ${remaining} ثانية.`)
    }

    try {
      const cred = await signInWithEmailAndPassword(auth, email.trim(), pass)
      const uid = cred.user.uid
      const userEmail = (cred.user.email || email).trim().toLowerCase()
      const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

      const profile = await getUserProfile()
      const isAdmin = isSuperAdminEmail || profile?.role === 'admin'

      if (!isAdmin) {
        await signOut(auth)
        recordFailedAttempt()
        throw new Error('⛔ تم رفض الوصول: هذا الحساب لا يملك تصريح المشرف الأعلى (SuperAdmin)!')
      }

      if (profile?.is_banned) {
        await signOut(auth)
        throw new Error('هذا الحساب محظور من دخول النظام')
      }

      const sessionToken = `sec_admin_${uid}_${Date.now()}_${Math.random().toString(36).substring(2)}`
      const sessionData: AdminSession = {
        uid,
        email: cred.user.email || email,
        role: 'admin',
        expiresAt: Date.now() + SESSION_DURATION_MS,
        token: sessionToken,
      }

      sessionStorage.setItem(ADMIN_SESSION_KEY, JSON.stringify(sessionData))
      sessionStorage.removeItem(FAILED_ATTEMPTS_KEY)
      sessionStorage.removeItem(LOCK_UNTIL_KEY)
      setFailedAttempts(0)
      setIsLocked(false)
      setAdminUser({ uid, ...(profile || {}), role: 'admin' } as User)
      setIsAuthenticated(true)

    } catch (err: any) {
      if (err?.code === 'auth/wrong-password' || err?.code === 'auth/user-not-found' || err?.code === 'auth/invalid-credential') {
        recordFailedAttempt()
        throw new Error('البريد الإلكتروني أو كلمة المرور غير صحيحة')
      }
      throw err
    }
  }

  const recordFailedAttempt = () => {
    const next = failedAttempts + 1
    setFailedAttempts(next)
    sessionStorage.setItem(FAILED_ATTEMPTS_KEY, String(next))

    if (next >= MAX_FAILED_ATTEMPTS) {
      const lockUntil = Date.now() + LOCKOUT_DURATION_SEC * 1000
      sessionStorage.setItem(LOCK_UNTIL_KEY, String(lockUntil))
      setIsLocked(true)
      setLockCountdown(LOCKOUT_DURATION_SEC)
    }
  }

  const logoutAdmin = async () => {
    sessionStorage.removeItem(ADMIN_SESSION_KEY)
    setIsAuthenticated(false)
    setAdminUser(null)
    try {
      await signOut(auth)
    } catch {}
  }

  const refreshSession = () => {
    const raw = sessionStorage.getItem(ADMIN_SESSION_KEY)
    if (raw) {
      const session: AdminSession = JSON.parse(raw)
      session.expiresAt = Date.now() + SESSION_DURATION_MS
      sessionStorage.setItem(ADMIN_SESSION_KEY, JSON.stringify(session))
    }
  }

  return {
    adminUser,
    isAuthenticated,
    loading,
    failedAttempts,
    isLocked,
    lockCountdown,
    loginAdmin,
    logoutAdmin,
    refreshSession,
  }
}

export function useAdminAuth(): AdminAuthContextType {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error('useAdminAuth must be used inside AdminAuthProvider')
  return ctx
}
