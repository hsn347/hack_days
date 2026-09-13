import React from 'react'
import { clsx } from 'clsx'

interface ToggleProps {
  value: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  size?: 'sm' | 'md'
}

export function Toggle({ value, onChange, disabled, size = 'md' }: ToggleProps) {
  const isSmall = size === 'sm'
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      disabled={disabled}
      onClick={() => !disabled && onChange(!value)}
      className={clsx(
        'relative inline-flex items-center rounded-full transition-colors duration-200 cursor-pointer flex-shrink-0 focus:outline-none',
        isSmall ? 'h-5 w-9' : 'h-6 w-11',
        value ? 'bg-primary-600' : 'bg-gray-600',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <span
        className={clsx(
          'absolute rounded-full bg-white shadow transition-transform duration-200',
          isSmall ? 'w-3.5 h-3.5 top-[3px]' : 'w-4 h-4 top-1',
          value
            ? isSmall ? 'translate-x-[18px]' : 'translate-x-6'
            : isSmall ? 'translate-x-[3px]' : 'translate-x-1'
        )}
      />
    </button>
  )
}
