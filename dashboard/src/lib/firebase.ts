/// <reference types="vite/client" />
// ════════════════════════════════════════════════════
//  Firebase Configuration (Authentication Only)
// ════════════════════════════════════════════════════
import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY            || "REPLACE_ME",
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN        || "REPLACE_ME.firebaseapp.com",
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID         || "REPLACE_ME",
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET     || "REPLACE_ME.appspot.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "REPLACE_ME",
  appId:             import.meta.env.VITE_FIREBASE_APP_ID             || "REPLACE_ME",
}

export const app  = initializeApp(firebaseConfig)
export const auth = getAuth(app)
