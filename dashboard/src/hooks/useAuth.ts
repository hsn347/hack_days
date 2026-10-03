import { useState, useEffect, createContext, useContext } from 'react'
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User as FirebaseUser,
} from 'firebase/auth'
import { auth } from '../lib/firebase'
import { getUserProfile, updateUserProfileApi } from '../lib/botApi'
import type { User } from '../types'

interface AuthContextType {
  firebaseUser: FirebaseUser | null
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<{ isAdmin: boolean }>
  logout: () => Promise<void>
  isAdmin: boolean
  updateUserProfile: (data: Partial<User>) => void
}

export const AuthContext = createContext<AuthContextType | null>(null)

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

// ─── Local Storage User Cache for Instant 0ms App Boot ──────
const AUTH_CACHE_KEY = 'ibra_auth_profile'

function getInitialCachedUser(): User | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(AUTH_CACHE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed && parsed.uid) {
        // حماية فورية: إبطال أي كاش محلي قديم يدعي صلاحية الأدمن لغير المشرف الأعلى
        const email = String(parsed.email || '').trim().toLowerCase()
        if (email !== 'ibraboths@gmail.com' && parsed.role === 'admin') {
          localStorage.removeItem(AUTH_CACHE_KEY)
          return null
        }
        return parsed as User
      }
    }
  } catch {
    // ignore
  }
  return null
}

function saveCachedUser(user: User | null) {
  if (typeof window === 'undefined') return
  try {
    if (user) {
      const email = String(user.email || '').trim().toLowerCase()
      if (email !== 'ibraboths@gmail.com' && user.role === 'admin') {
        user.role = 'user'
      }
      localStorage.setItem(AUTH_CACHE_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(AUTH_CACHE_KEY)
    }
  } catch {
    // ignore
  }
}

export function useAuthProvider(): AuthContextType {
  const initialUser = getInitialCachedUser()
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null)
  const [user, setUser] = useState<User | null>(initialUser)
  // If we have a cached user from a previous session, do not block app startup!
  const [loading, setLoading] = useState<boolean>(!initialUser)

  useEffect(() => {
    const unsubAuth = onAuthStateChanged(auth, async (fbUser) => {
      setFirebaseUser(fbUser)
      if (fbUser) {
        const userEmail = (fbUser.email || '').trim().toLowerCase()
        const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

        try {
          const profile = await getUserProfile()
          if (profile) {
            // حماية حديدية: لا يمكن لأي حساب أن يحمل دور admin باستثناء ibraboths@gmail.com
            if (!isSuperAdminEmail) {
              profile.role = 'user'
            } else {
              profile.role = 'admin'
              profile.subscription = {
                ...(profile.subscription || {}),
                plan_id: 'super_admin_unlimited',
                plan_name: 'باقة المشرف الأعلى (غير محدود)',
                status: 'active',
                max_castles_allowed: 999999,
                expires_at: '2099-01-01T00:00:00Z',
                days_remaining: 99999,
              }
            }
            setUser(profile)
            saveCachedUser(profile)
          } else {
            // مستخدم مبدئي إذا تعذر الاتصال بالـ API مؤقتاً
            setUser(prev => {
              const fallback = prev || ({
                uid: fbUser.uid,
                email: userEmail,
                username: fbUser.displayName || userEmail.split('@')[0],
                role: isSuperAdminEmail ? 'admin' : 'user',
                is_banned: false,
                created_at: new Date().toISOString(),
                subscription: {
                  plan_id: isSuperAdminEmail ? 'super_admin_unlimited' : 'free',
                  plan_name: isSuperAdminEmail ? 'المشرف الأعلى' : 'مجاني',
                  status: 'active',
                  max_castles_allowed: isSuperAdminEmail ? 999999 : 1,
                  current_castles_count: 0,
                  started_at: new Date().toISOString(),
                  expires_at: '2099-01-01T00:00:00Z',
                  days_remaining: 99999,
                }
              } as User)
              saveCachedUser(fallback)
              return fallback
            })
          }
        } catch {
          // في حال عدم توفر اتصال بالشبكة، احتفظ بالمستخدم المخزن محلياً
          setUser(prev => {
            if (prev) return prev
            const fallback = {
              uid: fbUser.uid,
              email: userEmail,
              username: fbUser.displayName || userEmail.split('@')[0],
              role: isSuperAdminEmail ? 'admin' : 'user',
              is_banned: false,
              created_at: new Date().toISOString(),
              subscription: {
                plan_id: isSuperAdminEmail ? 'super_admin_unlimited' : 'free',
                plan_name: isSuperAdminEmail ? 'المشرف الأعلى' : 'مجاني',
                status: 'active',
                max_castles_allowed: isSuperAdminEmail ? 999999 : 1,
                current_castles_count: 0,
                started_at: new Date().toISOString(),
                expires_at: '2099-01-01T00:00:00Z',
                days_remaining: 99999,
              }
            } as User
            saveCachedUser(fallback)
            return fallback
          })
        } finally {
          setLoading(false)
        }
      } else {
        setUser(null)
        saveCachedUser(null)
        setLoading(false)
      }
    })

    return () => unsubAuth()
  }, [])

  const login = async (email: string, password: string): Promise<{ isAdmin: boolean }> => {
    const cred = await signInWithEmailAndPassword(auth, email.trim(), password)
    const uid = cred.user.uid
    const userEmail = (cred.user.email || email).trim().toLowerCase()
    const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

    // التحقق الصارم: الأدمن حصرياً لـ ibraboths@gmail.com
    let isAdmin = isSuperAdminEmail
    try {
      const profile = await getUserProfile()
      if (!isSuperAdminEmail && profile) {
        profile.role = 'user'
        saveCachedUser(profile)
      }
      if (isSuperAdminEmail && profile && profile.role === 'admin') {
        isAdmin = true
      } else if (!isSuperAdminEmail) {
        isAdmin = false
      }
    } catch (e) {
      console.warn('Profile check error:', e)
    }

    if (isAdmin) {
      const sessionToken = `sec_admin_${uid}_${Date.now()}`
      const sessionData = {
        uid,
        email: userEmail,
        role: 'admin',
        expiresAt: Date.now() + 60 * 60 * 1000,
        token: sessionToken,
      }
      sessionStorage.setItem('osmanli_admin_session_token', JSON.stringify(sessionData))
    }

    return { isAdmin }
  }

  const logout = async () => {
    sessionStorage.removeItem('osmanli_admin_session_token')
    saveCachedUser(null)
    await signOut(auth)
    setUser(null)
  }

  const updateUserProfile = (data: Partial<User>) => {
    setUser(prev => {
      const updated = prev ? { ...prev, ...data } : null
      saveCachedUser(updated)
      return updated
    })
    updateUserProfileApi({ username: data.username, phone: data.phone }).catch(() => {})
  }

  // 🛡️ شرط حديدي غير قابل للكسر: الأدمن يجب أن يطابق ibraboths@gmail.com في Firebase والبيانات والدور معاً
  const isUserAdmin =
    (firebaseUser?.email || '').trim().toLowerCase() === 'ibraboths@gmail.com' &&
    (user?.email || '').trim().toLowerCase() === 'ibraboths@gmail.com' &&
    user?.role === 'admin'

  return {
    firebaseUser,
    user,
    loading,
    login,
    logout,
    isAdmin: isUserAdmin,
    updateUserProfile,
  }
}
