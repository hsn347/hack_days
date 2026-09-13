import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Theme, Language } from '../types'

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
      language: 'ar',
      sidebarOpen: true,
      setTheme:     (theme) => set({ theme }),
      setLanguage:  (language) => set({ language }),
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: 'osmanli_app',
      partialize: (s) => ({ theme: s.theme, language: s.language }),
    }
  )
)
