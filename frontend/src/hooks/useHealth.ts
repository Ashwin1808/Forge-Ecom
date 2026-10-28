import { useEffect, useState } from 'react'
import { api } from '../api/client'

export type HealthState = 'checking' | 'online' | 'offline'

export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>('checking')

  useEffect(() => {
    let active = true

    const check = async () => {
      try {
        await api.health()
        if (active) setState('online')
      } catch {
        if (active) setState('offline')
      }
    }

    void check()
    const interval = window.setInterval(check, 30_000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  return state
}
