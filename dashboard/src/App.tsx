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
import { AdminLoginPage }  from './pages/AdminLogin'
import { SettingsPage }    from './pages/Settings'
import { AuthContext, useAuthProvider } from './hooks/useAuth'
import { AdminAuthContext, useAdminAuthProvider, useAdminAuth } from './hooks/useAdminAuth'
import { queryClient }     from './lib/queryClient'
import { useAppStore }     from './store/appStore'
import './lib/i18n'

// ─── Auth Provider (Regular Users) ─────────────────────────
function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthProvider()
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

// ─── Admin Auth Provider (SuperAdmin Only) ─────────────────
function AdminAuthProvider({ children }: { children: React.ReactNode }) {
  const adminAuth = useAdminAuthProvider()
  return <AdminAuthContext.Provider value={adminAuth}>{children}</AdminAuthContext.Provider>
}

// ─── Private Route (Regular Users) ─────────────────────────
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

// ─── Admin Route (SuperAdmin Only) ─────────────────────────
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAdminAuth()
  if (loading) return (
    <div className="min-h-screen bg-[#060a08] flex items-center justify-center text-emerald-400">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
        <span className="text-xs font-mono">التحقق من تصريح المشرف الأعلى...</span>
      </div>
    </div>
  )
  if (!isAuthenticated) return <Navigate to="/admin/login" replace />
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
    document.documentElement.dir = 'ltr'
    document.documentElement.lang = language
  }, [language])
  return null
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AdminAuthProvider>
          <ThemeEffect />
          <BrowserRouter>
            <Routes>
              {/* Public User Auth */}
              <Route path="/login"    element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* Protected User Dashboard */}
              <Route path="/dashboard" element={
                <PrivateRoute><DashboardPage /></PrivateRoute>
              } />
              <Route path="/accounts" element={
                <PrivateRoute><AccountsPage /></PrivateRoute>
              } />
              <Route path="/accounts/:id" element={
                <PrivateRoute><CastleDetailPage /></PrivateRoute>
              } />
              <Route path="/settings" element={
                <PrivateRoute><SettingsPage /></PrivateRoute>
              } />

              {/* 🛡️ Independent SuperAdmin Secure Gateway */}
              <Route path="/admin/login" element={<AdminLoginPage />} />
              <Route path="/admin" element={
                <AdminRoute><AdminPage /></AdminRoute>
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
        </AdminAuthProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
