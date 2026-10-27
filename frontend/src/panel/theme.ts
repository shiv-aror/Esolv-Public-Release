import { useEffect, useState } from 'react'
import { store } from '../lib/platform'
import type { ThemePref } from '../lib/types'

export function applyTheme(t: ThemePref) {
  if (t === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', t)
}

export function useTheme(): [ThemePref, (t: ThemePref) => void] {
  const [theme, setTheme] = useState<ThemePref>('system')
  useEffect(() => {
    void store.local.get<ThemePref>('theme').then((t) => {
      if (t) { setTheme(t); applyTheme(t) }
    })
  }, [])
  const set = (t: ThemePref) => {
    setTheme(t)
    applyTheme(t)
    void store.local.set('theme', t)
  }
  return [theme, set]
}
