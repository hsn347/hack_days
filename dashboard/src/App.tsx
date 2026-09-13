import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { LoginPage }       from './pages/Login'
import { RegisterPage }    from './pages/Register'
import { DashboardPage }   from './pages/Dashboard'
import { AccountsPage }    from './pages/Accounts'
import { CastleDetailPage }from './pages/CastleDetail'
import { AdminPage }       from './pages/Admin'
import { SettingsPage }    from './pages/Settings'
import { AuthContext, useAuthProvider } from './hooks/useAuth'
import { queryClient }     from './lib/queryClient'
import { useAppStore }     from './store/appStore'
import './lib/i18n'

// ─── Auth Provider ─────────────────────────────────────────
function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthProvider()
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

// ─── Private Route ─────────────────────────────────────────
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const ctx = React.useContext(AuthContext)
  if (ctx?.loading) return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center">
      <div className="text-primary-400 animate-pulse">جارٍ التحميل...</div>
    </div>
  )
  if (!ctx?.firebaseUser) return <Navigate to="/login" replace />
  return <>{children}</>
}

// ─── Theme & Dir Effect ────────────────────────────────────
function ThemeEffect() {
  const { theme, language } = useAppStore()
  React.useEffect(() => {
    const isDark  = theme === 'dark'
    const isLight = theme === 'light'
    // dark & light classes on both html and body
    document.documentElement.classList.toggle('dark',  isDark)
    document.documentElement.classList.toggle('light', isLight)
    document.body.classList.toggle('dark',  isDark)
    document.body.classList.toggle('light', isLight)
    // background & text color fallback
    document.body.style.backgroundColor = isLight ? '#f1f5f2' : '#0a0f0a'
    document.body.style.color = isLight ? '#0f172a' : '#ffffff'
  }, [theme])
  React.useEffect(() => {
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = language
  }, [language])
  return null
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeEffect />
        <BrowserRouter>
          <Routes>
            <Route path="/login"    element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />

            <Route path="/dashboard" element={
              <PrivateRoute><DashboardPage /></PrivateRoute>
            } />
            <Route path="/accounts" element={
              <PrivateRoute><AccountsPage /></PrivateRoute>
            } />
            <Route path="/accounts/:id" element={
              <PrivateRoute><CastleDetailPage /></PrivateRoute>
            } />
            <Route path="/admin" element={
              <PrivateRoute><AdminPage /></PrivateRoute>
            } />
            <Route path="/settings" element={
              <PrivateRoute><SettingsPage /></PrivateRoute>
            } />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>

        <Toaster
          position="bottom-center"
          toastOptions={{
            style: {
              background: '#162016',
              color: '#fff',
              border: '1px solid rgba(34,197,94,0.2)',
              borderRadius: '12px',
              fontSize: '14px',
            },
            success: { iconTheme: { primary: '#10b981', secondary: '#fff' } },
            error:   { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
          }}
        />
      </AuthProvider>
    </QueryClientProvider>
  )
}
