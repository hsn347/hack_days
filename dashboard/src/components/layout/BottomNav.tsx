import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { LayoutDashboard, Users, Settings, Shield } from 'lucide-react'
import { clsx } from 'clsx'
import { useAuth } from '../../hooks/useAuth'
import { useCastles } from '../../hooks/useCastles'

export function BottomNav() {
  const { t } = useTranslation()
  const location = useLocation()
  const { user, isAdmin } = useAuth()
  const uid = user?.uid ?? ''
  const { data } = useCastles(uid)

  const allCastles = data?.pages.flatMap(p => p.items) ?? []
  const runningCount = allCastles.filter(c => c.is_active && c.bot_status?.state === 'running').length

  const navItems = [
    {
      to: '/dashboard',
      icon: LayoutDashboard,
      label: t('nav.dashboard', 'الرئيسية'),
      isActive: (path: string) => path === '/dashboard' || path === '/',
    },
    {
      to: '/accounts',
      icon: Users,
      label: t('nav.accounts', 'الحسابات'),
      badge: runningCount > 0 ? runningCount : undefined,
      isActive: (path: string) => path.startsWith('/accounts'),
    },
    {
      to: '/settings',
      icon: Settings,
      label: t('nav.settings', 'الإعدادات'),
      isActive: (path: string) => path.startsWith('/settings'),
    },
    ...(isAdmin ? [{
      to: '/admin',
      icon: Shield,
      label: t('nav.admin', 'الإدارة'),
      isActive: (path: string) => path.startsWith('/admin'),
    }] : []),
  ]

  return (
    <nav
      dir="rtl"
      aria-label="Mobile Navigation"
      className="bottom-nav-glass md:hidden fixed bottom-0 left-0 right-0 w-full z-50 m-0 p-0 border-b-0 transition-all duration-200"
      style={{
        bottom: 0,
        left: 0,
        right: 0,
        width: '100%',
        margin: 0,
        marginBottom: 0,
        paddingBottom: 0,
      }}
    >
      <div className="flex items-center justify-around max-w-lg mx-auto px-3 pt-1 pb-0.5">
        {navItems.map((item) => {
          const active = item.isActive(location.pathname)
          const Icon = item.icon

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={clsx(
                'bottom-nav-item relative flex flex-col items-center justify-center min-w-[70px] pt-1 pb-0 px-2 rounded-xl transition-all duration-200 active:scale-95 select-none',
                active ? 'bottom-nav-item-active font-bold' : 'bottom-nav-item-inactive font-medium'
              )}
            >
              {/* Active glow top bar indicator */}
              {active && (
                <span className="bottom-nav-active-pill absolute -top-2 inset-x-3 h-[3px] rounded-full bg-primary-500 shadow-[0_0_10px_rgba(34,197,94,0.8)]" />
              )}

              <div className="relative">
                <Icon
                  size={20}
                  className={clsx(
                    'bottom-nav-icon transition-transform duration-200',
                    active ? 'scale-110 text-primary-400' : 'text-gray-400'
                  )}
                />

                {/* Badge for running accounts */}
                {item.badge !== undefined && (
                  <span className="absolute -top-1 -end-2.5 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-black text-black ring-2 ring-gray-950 animate-pulse">
                    {item.badge}
                  </span>
                )}
              </div>

              <span
                className={clsx(
                  'bottom-nav-label text-[11px] mt-1 tracking-tight truncate max-w-[80px]',
                  active ? 'text-primary-400 font-bold' : 'text-gray-400'
                )}
              >
                {item.label}
              </span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
