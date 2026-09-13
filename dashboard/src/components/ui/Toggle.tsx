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
  const width = isSmall ? 40 : 48
  const height = isSmall ? 22 : 26
  const knobSize = isSmall ? 18 : 22
  const travel = width - knobSize - 4

  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation()
        if (!disabled) onChange(!value)
      }}
      style={{
        direction: 'ltr',
        width: `${width}px`,
        height: `${height}px`,
        minWidth: `${width}px`,
      }}
      className={clsx(
        'relative inline-flex items-center rounded-full transition-all duration-200 cursor-pointer flex-shrink-0 focus:outline-none select-none p-0.5 active:scale-95',
        value
          ? 'bg-gradient-to-r from-emerald-500 to-teal-500 shadow-[0_0_12px_rgba(16,185,129,0.45)]'
          : 'bg-gray-700 hover:bg-gray-600 border border-white/10 shadow-inner',
        disabled && 'opacity-40 cursor-not-allowed active:scale-100'
      )}
    >
      <span
        style={{
          width: `${knobSize}px`,
          height: `${knobSize}px`,
          transform: value ? `translateX(${travel}px)` : 'translateX(0px)',
        }}
        className="block rounded-full bg-white shadow-md transition-transform duration-200 ease-out pointer-events-none"
      />
    </button>
  )
}
