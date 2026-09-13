import { useState, useEffect, createContext, useContext } from 'react'
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User as FirebaseUser,
} from 'firebase/auth'
import { doc, getDoc, onSnapshot } from 'firebase/firestore'
import { auth, db } from '../lib/firebase'
import type { User } from '../types'

interface AuthContextType {
  firebaseUser: FirebaseUser | null
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
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
        unsubUserDoc = onSnapshot(doc(db, 'users', fbUser.uid), (snap) => {
          if (snap.exists()) {
            setUser({ uid: fbUser.uid, ...snap.data() } as User)
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

  const login = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password)
  }

  const logout = async () => {
    await signOut(auth)
    setUser(null)
  }

  const updateUserProfile = (data: Partial<User>) => {
    setUser(prev => prev ? { ...prev, ...data } : null)
  }

  return {
    firebaseUser,
    user,
    loading,
    login,
    logout,
    isAdmin: user?.role === 'admin',
    updateUserProfile,
  }
}
