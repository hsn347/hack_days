import { useState, useEffect } from 'react'

/**
 * useDebounce Hook
 * Debounces a fast-changing value (such as search keystrokes) by a specified delay in ms.
 * Default delay is 300ms (within 250-300ms standard).
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}

export default useDebounce
