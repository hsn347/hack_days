import { useState, useEffect, createContext, useContext } from 'react'
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User as FirebaseUser,
} from 'firebase/auth'
import { doc, getDoc, setDoc, onSnapshot } from 'firebase/firestore'
import { auth, db } from '../lib/firebase'
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

// We export this for use in createContext below
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
    let unsubUserDoc: (() => void) | null = null

    const unsubAuth = onAuthStateChanged(auth, (fbUser) => {
      setFirebaseUser(fbUser)
      if (unsubUserDoc) {
        unsubUserDoc()
        unsubUserDoc = null
      }
      if (fbUser) {
        const userEmail = (fbUser.email || '').trim().toLowerCase()
        const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

        unsubUserDoc = onSnapshot(doc(db, 'users', fbUser.uid), async (snap) => {
          if (snap.exists()) {
            const data = snap.data()
            if (data?.role === 'admin' || isSuperAdminEmail) {
              data.subscription = {
                ...(data.subscription || {}),
                plan_id: 'super_admin_unlimited',
                plan_name: 'باقة المشرف الأعلى (غير محدود)',
                status: 'active',
                max_castles_allowed: 999999,
                expires_at: '2099-01-01T00:00:00Z',
                days_remaining: 99999,
              }
            }
            setUser({ uid: fbUser.uid, ...data } as User)
          } else if (isSuperAdminEmail) {
            const superAdminDoc = {
              uid: fbUser.uid,
              email: userEmail,
              username: 'المشرف الأعلى (SuperAdmin)',
              role: 'admin',
              is_banned: false,
              created_at: new Date().toISOString(),
              subscription: {
                plan_id: 'super_admin_unlimited',
                plan_name: 'باقة المشرف الأعلى (غير محدود)',
                status: 'active',
                max_castles_allowed: 999999,
                current_castles_count: 0,
                started_at: new Date().toISOString(),
                expires_at: '2099-01-01T00:00:00Z',
                days_remaining: 99999,
              }
            }
            try {
              await setDoc(doc(db, 'users', fbUser.uid), superAdminDoc, { merge: true })
              setUser(superAdminDoc as unknown as User)
            } catch {}
          } else {
            setUser(null)
          }
          setLoading(false)
        }, () => {
          setUser(null)
          setLoading(false)
        })
      } else {
        setUser(null)
        setLoading(false)
      }
    })

    return () => {
      unsubAuth()
      if (unsubUserDoc) unsubUserDoc()
    }
  }, [])

  const login = async (email: string, password: string): Promise<{ isAdmin: boolean }> => {
    const cred = await signInWithEmailAndPassword(auth, email.trim(), password)
    const uid = cred.user.uid
    const userEmail = (cred.user.email || email).trim().toLowerCase()
    const isSuperAdminEmail = userEmail === 'ibraboths@gmail.com'

    let isAdmin = isSuperAdminEmail
    try {
      const snap = await getDoc(doc(db, 'users', uid))
      if (snap.exists()) {
        const uData = snap.data()
        if (uData?.role === 'admin') isAdmin = true
      }
    } catch (e) {
      console.warn('User doc check error:', e)
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
