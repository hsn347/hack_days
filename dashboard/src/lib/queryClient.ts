import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            60_000,              // دقيقة كاملة لمنع تكرار الطلبات غير الضرورية
      gcTime:               1000 * 60 * 60 * 24, // 24 ساعة للحفاظ على البيانات في الذاكرة
      retry:                2,
      refetchOnWindowFocus: false,               // عدم إعادة التحميل عند قفل الشاشة أو التبديل بين التطبيقات
      refetchOnReconnect:   'always',            // مزامنة صامتة فقط عند عودة الإنترنت
    },
  },
})

