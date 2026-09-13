import React from 'react'
import { clsx } from 'clsx'
import type { BotState } from '../../types'

interface StatusBadgeProps {
  state: BotState
  label: string
  showDot?: boolean
}

const stateStyles: Record<BotState, string> = {
  running:      'badge-green',
  idle:         'badge-gray',
  error:        'badge-red',
  paused:       'badge-yellow',
  pending:      'badge-yellow',
  disconnected: 'badge-yellow',
  reconnecting: 'badge-yellow',
  waiting:      'badge-blue',
}

const dotStyles: Record<BotState, string> = {
  running:      'bg-emerald-400 animate-pulse',
  idle:         'bg-gray-500',
  error:        'bg-red-500 animate-pulse',
  paused:       'bg-yellow-500',
  pending:      'bg-yellow-500 animate-pulse',
  disconnected: 'bg-amber-400 animate-pulse',
  reconnecting: 'bg-orange-400 animate-pulse',
  waiting:      'bg-sky-400 animate-pulse',
}

export function StatusBadge({ state, label, showDot = true }: StatusBadgeProps) {
  return (
    <span className={clsx('badge', stateStyles[state])}>
      {showDot && <span className={clsx('w-1.5 h-1.5 rounded-full', dotStyles[state])} />}
      {label}
    </span>
  )
}
