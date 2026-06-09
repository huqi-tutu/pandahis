import { useEffect, useMemo, useState } from 'react'

type RevealOptions = {
  threshold?: number
  rootMargin?: string
  once?: boolean
}

export function useReveal(options: RevealOptions = {}) {
  const { threshold = 0.16, rootMargin = '0px 0px -10% 0px', once = true } = options
  const [shown, setShown] = useState(false)
  const [key] = useState(() => Math.random().toString(36).slice(2))

  const prefersReduced = useMemo(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
  }, [])

  useEffect(() => {
    if (prefersReduced) {
      setShown(true)
      return
    }
    const el = document.querySelector(`[data-reveal-key="${key}"]`) as HTMLElement | null
    if (!el) return

    const ob = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setShown(true)
            if (once) ob.disconnect()
          }
        }
      },
      { threshold, rootMargin }
    )
    ob.observe(el)
    return () => ob.disconnect()
  }, [key, once, prefersReduced, rootMargin, threshold])

  return {
    shown,
    dataAttrs: { 'data-reveal': shown ? 'shown' : 'pending', 'data-reveal-key': key } as const,
  }
}

