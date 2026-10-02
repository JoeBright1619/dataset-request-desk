import { useCallback, useEffect, useRef, useState } from 'react'
import {
  searchEpisodes,
  type Episode,
  type EpisodeSearchParams,
} from '../api/episodes'

interface PageMeta {
  hasMore: boolean
  hasPrev: boolean
  nextCursor: string | null
}

interface UseEpisodeSearchResult {
  episodes: Episode[]
  loading: boolean
  error: string | null
  meta: PageMeta
  canPrev: boolean
  next: () => void
  prev: () => void
  refresh: () => Promise<void>
  clearError: () => void
}

const DEFAULT_LIMIT = 50

/**
 * Owns episode search state: fetch, cursor pagination, filter-reset.
 *
 * Pass the current filter set; the hook resets to page 1 whenever any
 * filter value changes (compared via JSON.stringify).
 */
export function useEpisodeSearch(
  params: EpisodeSearchParams,
  limit: number = DEFAULT_LIMIT,
): UseEpisodeSearchResult {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cursor, setCursor] = useState<string | undefined>(undefined)
  const [cursorStack, setCursorStack] = useState<string[]>([])
  const [meta, setMeta] = useState<PageMeta>({
    hasMore: false,
    hasPrev: false,
    nextCursor: null,
  })

  // Stable key for the filter set — anything that changes here resets
  // the cursor back to page 1.
  const paramsKey = JSON.stringify(params)
  const lastParamsKey = useRef(paramsKey)

  useEffect(() => {
    if (lastParamsKey.current !== paramsKey) {
      setCursor(undefined)
      setCursorStack([])
      lastParamsKey.current = paramsKey
    }
  }, [paramsKey])

  // Fetch whenever filters or cursor change.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        // `params` is safe to spread — the effect is keyed on paramsKey,
        // so identity churn from the caller doesn't cause extra fetches.
        const page = await searchEpisodes({ ...params, cursor, limit })
        if (cancelled) return
        setEpisodes(page.items)
        setMeta({
          hasMore: page.has_more,
          hasPrev: page.has_prev,
          nextCursor: page.next_cursor,
        })
        setError(null)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unexpected error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, cursor, limit])

  const next = useCallback(() => {
    setMeta((m) => {
      if (!m.hasMore || !m.nextCursor) return m
      setCursorStack((s) => [...s, cursor ?? ''])
      setCursor(m.nextCursor)
      return m
    })
    // Note: cursor is read from closure; safe because `next` only fires
    // from a user click, and the cursor state is stable at that moment.
  }, [cursor])

  const prev = useCallback(() => {
    setCursorStack((s) => {
      if (s.length === 0) return s
      const popped = s[s.length - 1]
      setCursor(popped || undefined)
      return s.slice(0, -1)
    })
  }, [])

  const refresh = useCallback(async () => {
    try {
      const page = await searchEpisodes({ ...params, cursor, limit })
      setEpisodes(page.items)
      setMeta({
        hasMore: page.has_more,
        hasPrev: page.has_prev,
        nextCursor: page.next_cursor,
      })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, cursor, limit])

  const clearError = useCallback(() => setError(null), [])

  return {
    episodes,
    loading,
    error,
    meta,
    canPrev: cursorStack.length > 0,
    next,
    prev,
    refresh,
    clearError,
  }
}