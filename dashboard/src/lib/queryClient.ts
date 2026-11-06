import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            60_000,              // دقيقة كاملة لمنع تكرار الطلبات غير الضرورية
      gcTime:               600_000,             // 10 دقائق لتجنب تضخم الذاكرة وتحرير الموارد تلقائياً
      retry:                2,
      refetchOnWindowFocus: false,               // عدم إعادة التحميل عند قفل الشاشة أو التبديل بين التطبيقات
      refetchOnReconnect:   'always',            // مزامنة صامتة فقط عند عودة الإنترنت
    },
  },
})

