import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Theme, Language } from '../types'
import { getCurrentTenant, getInitialLanguage } from '../config/tenants'

interface AppState {
  theme: Theme
  language: Language
  sidebarOpen: boolean
  setTheme: (t: Theme) => void
  setLanguage: (l: Language) => void
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      theme: 'dark',
      language: getInitialLanguage(),
      sidebarOpen: true,
      setTheme: (theme) => set({ theme }),
      setLanguage: (language) => {
        try {
          const tenantKey = typeof window !== 'undefined' ? (getCurrentTenant().id || 'main') : 'main'
          localStorage.setItem(`osmanli_lang_manual_${tenantKey}`, 'true')
          localStorage.setItem(`osmanli_lang_${tenantKey}`, language)
          localStorage.setItem('osmanli_lang_manual', 'true')
          localStorage.setItem('osmanli_lang', language)
        } catch {}
        set({ language })
      },
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: 'osmanli_app',
      partialize: (s) => ({ theme: s.theme, language: s.language }),
      merge: (persistedState, currentState) => {
        const p = persistedState as Partial<AppState> | undefined
        const tenantKey = typeof window !== 'undefined' ? (getCurrentTenant().id || 'main') : 'main'
        const isManual = typeof window !== 'undefined'
          ? localStorage.getItem(`osmanli_lang_manual_${tenantKey}`) === 'true'
          : false

        return {
          ...currentState,
          ...p,
          // إذا لم يقم المستخدم بتغيير اللغة يدوياً لهذا النطاق، نلتزم بلغة النطاق الافتراضية
          language: isManual && p?.language ? p.language : currentState.language,
        }
      },
    }
  )
)
