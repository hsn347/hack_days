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

export function useAuthProvider(): AuthContextType {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const unsubAuth = onAuthStateChanged(auth, async (fbUser) => {
      setFirebaseUser(fbUser)
      if (fbUser) {
        const userEmail = (fbUser.email || '').trim().toLowerCase()
        const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

        try {
          const profile = await getUserProfile()
          if (profile) {
            if (profile.role === 'admin' || isSuperAdminEmail) {
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
          } else {
            // مستخدم مبدئي إذا تعذر الاتصال بالـ API مؤقتاً
            setUser({
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
          }
        } catch {
          setUser(null)
        } finally {
          setLoading(false)
        }
      } else {
        setUser(null)
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

    let isAdmin = isSuperAdminEmail
    try {
      const profile = await getUserProfile()
      if (profile && profile.role === 'admin') isAdmin = true
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
    await signOut(auth)
    setUser(null)
  }

  const updateUserProfile = (data: Partial<User>) => {
    setUser(prev => prev ? { ...prev, ...data } : null)
    updateUserProfileApi({ username: data.username, phone: data.phone }).catch(() => {})
  }

  const isUserAdmin = user?.role === 'admin' ||
                      user?.email?.toLowerCase() === 'ibraboths@gmail.com' ||
                      firebaseUser?.email?.toLowerCase() === 'ibraboths@gmail.com'

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
