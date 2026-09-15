import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:        60_000,   // دقيقة واحدة (مناسب لـ 1000 حساب)
      gcTime:           300_000,  // 5 دقائق في cache
      retry:            2,
      refetchOnWindowFocus: false,
    },
  },
})
