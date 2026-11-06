import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { LoginPage }       from './pages/Login'
import { RegisterPage }    from './pages/Register'
import { DashboardPage }   from './pages/Dashboard'
// Route-level code splitting via React.lazy for admin & secondary views
const AccountsPage = React.lazy(() => import('./pages/Accounts').then(m => ({ default: m.AccountsPage })))
const CastleDetailPage = React.lazy(() => import('./pages/CastleDetail').then(m => ({ default: m.CastleDetailPage })))
const SettingsPage = React.lazy(() => import('./pages/Settings').then(m => ({ default: m.SettingsPage })))
const AdminPage = React.lazy(() => import('./pages/Admin').then(m => ({ default: m.AdminPage })))
const AdminLiveProcessesPage = React.lazy(() => import('./pages/AdminLiveProcesses').then(m => ({ default: m.AdminLiveProcessesPage })))
const AdminMerchantsPage = React.lazy(() => import('./pages/AdminMerchants').then(m => ({ default: m.AdminMerchantsPage })))
const AdminProxiesPage = React.lazy(() => import('./pages/AdminProxies').then(m => ({ default: m.AdminProxiesPage })))
const AdminUsersCastlesPage = React.lazy(() => import('./pages/AdminUsersCastles').then(m => ({ default: m.AdminUsersCastlesPage })))
import { AuthContext, useAuthProvider } from './hooks/useAuth'
import { TenantProvider }  from './context/TenantContext'
import { DevTenantSwitcher } from './components/common/DevTenantSwitcher'
import { queryClient }     from './lib/queryClient'
import { useAppStore }     from './store/appStore'
import i18n from './lib/i18n'

// ─── Auth Provider (Regular Users) ─────────────────────────
function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthProvider()
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

// ─── Private Route (Regular Users) ─────────────────────────
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const ctx = React.useContext(AuthContext)
  if (ctx?.loading) return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center">
      <div className="text-primary-400 animate-pulse">{i18n.t('common.loading', 'جارٍ التحميل...')}</div>
    </div>
  )
  if (!ctx?.user && !ctx?.firebaseUser) return <Navigate to="/login" replace />
  // المشرفون مخصصون للإدارة حصراً وتُمنع عنهم صفحات إدارة القلاع
  if (ctx?.isAdmin) return <Navigate to="/admin" replace />
  return <>{children}</>
}

// ─── توجيه الصفحة الرئيسية الافتراضي بحسب رتبة الحساب ────────
function HomeRoute() {
  const ctx = React.useContext(AuthContext)
  if (ctx?.loading) return (
    <div className="flex justify-center items-center bg-dark-bg min-h-screen">
      <div className="text-primary-400 animate-pulse">{i18n.t('common.loading', 'جارٍ التحميل...')}</div>
    </div>
  )
  if (!ctx?.user && !ctx?.firebaseUser) return <Navigate to="/login" replace />
  if (ctx?.isAdmin) return <Navigate to="/admin" replace />
  return <Navigate to="/dashboard" replace />
}

// ─── Admin Route (SuperAdmin or Merchant Admin) ─────────────
function AdminRoute({ children }: { children: React.ReactNode }) {
  const ctx = React.useContext(AuthContext)

  if (ctx?.loading) return (
    <div className="flex justify-center items-center bg-slate-50 dark:bg-[#060a08] min-h-screen text-emerald-600 dark:text-emerald-400">
      <div className="flex flex-col items-center gap-3">
        <div className="border-2 border-emerald-500/30 border-t-emerald-500 rounded-full w-8 h-8 animate-spin" />
        <span className="font-mono text-xs">{i18n.t('admin.checkingAuth', 'التحقق من الصلاحيات...')}</span>
      </div>
    </div>
  )

  if (!ctx?.user && !ctx?.firebaseUser) {
    return <Navigate to="/login" replace />
  }

  if (!ctx?.isAdmin) {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

// ─── Super Admin Route (Live Processes, Merchants Overview) ──
function SuperAdminRoute({ children }: { children: React.ReactNode }) {
  const ctx = React.useContext(AuthContext)

  if (ctx?.loading) return (
    <div className="flex justify-center items-center bg-slate-50 dark:bg-[#060a08] min-h-screen text-emerald-600 dark:text-emerald-400">
      <div className="flex flex-col items-center gap-3">
        <div className="border-2 border-emerald-500/30 border-t-emerald-500 rounded-full w-8 h-8 animate-spin" />
        <span className="font-mono text-xs">{i18n.t('admin.checkingAuth', 'التحقق من الصلاحيات...')}</span>
      </div>
    </div>
  )

  if (!ctx?.user && !ctx?.firebaseUser) {
    return <Navigate to="/login" replace />
  }

  if (!ctx?.isSuperAdmin) {
    return <Navigate to="/admin" replace />
  }
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
    if (i18n.language !== language) {
      i18n.changeLanguage(language)
    }
  }, [language])
  return null
}

function ThemedToaster() {
  const { theme } = useAppStore()
  const isLight = theme === 'light'
  return (
    <Toaster
      position="bottom-center"
      toastOptions={{
        style: isLight ? {
          background: '#ffffff',
          color: '#0f172a',
          border: '1px solid #cbd5e1',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)',
          borderRadius: '12px',
          fontSize: '14px',
          fontWeight: 600,
        } : {
          background: '#162016',
          color: '#fff',
          border: '1px solid rgba(34,197,94,0.2)',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.5)',
          borderRadius: '12px',
          fontSize: '14px',
        },
        success: { iconTheme: { primary: '#10b981', secondary: isLight ? '#ffffff' : '#fff' } },
        error:   { iconTheme: { primary: '#ef4444', secondary: isLight ? '#ffffff' : '#fff' } },
      }}
    />
  )
}

function RouteLoadingFallback() {
  return (
    <div className="flex justify-center items-center bg-slate-50 dark:bg-[#060a08] min-h-screen text-emerald-500">
      <div className="flex flex-col items-center gap-3">
        <div className="border-2 border-emerald-500/30 border-t-emerald-500 rounded-full w-8 h-8 animate-spin" />
        <span className="font-mono text-xs">{i18n.t('common.loading', 'جارٍ التحميل...')}</span>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TenantProvider>
          <ThemeEffect />
          <BrowserRouter>
            <React.Suspense fallback={<RouteLoadingFallback />}>
              <Routes>
                {/* Public User Auth */}
                <Route path="/login"    element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/" element={<HomeRoute />} />

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

                {/* 🛡️ Admin Portal */}
                <Route path="/admin" element={
                  <AdminRoute><AdminPage /></AdminRoute>
                } />
                <Route path="/admin/live-processes" element={
                  <SuperAdminRoute><AdminLiveProcessesPage /></SuperAdminRoute>
                } />
                <Route path="/admin/merchants" element={
                  <SuperAdminRoute><AdminMerchantsPage /></SuperAdminRoute>
                } />
                <Route path="/admin/proxies" element={
                  <SuperAdminRoute><AdminProxiesPage /></SuperAdminRoute>
                } />
                <Route path="/admin/users-castles" element={
                  <SuperAdminRoute><AdminUsersCastlesPage /></SuperAdminRoute>
                } />

                <Route path="*" element={<HomeRoute />} />
              </Routes>
            </React.Suspense>
          </BrowserRouter>

          <ThemedToaster />
          <DevTenantSwitcher />
        </TenantProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
