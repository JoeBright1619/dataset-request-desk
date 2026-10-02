import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEpisodeSearch } from '../hooks/useEpisodeSearch'
import { EpisodeFilters } from '../components/EpisodeFilters'
import { EpisodeTable } from '../components/EpisodeTable'
import { PaginationControls } from '../components/PaginationControls'
import type { EpisodeQuality } from '../api/episodes'
import './EpisodesPage.css'

interface Filters {
  taskName: string
  quality: EpisodeQuality | ''
  robotId: string
  recordedFrom: string
  recordedTo: string
  assigned: 'any' | 'true' | 'false'
}

const EMPTY_FILTERS: Filters = {
  taskName: '',
  quality: '',
  robotId: '',
  recordedFrom: '',
  recordedTo: '',
  assigned: 'any',
}

function EpisodesPage() {

  const [filtersInput, setFiltersInput] = useState<Filters>(EMPTY_FILTERS)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)

  useEffect(() => {
    const id = setTimeout(() => setFilters(filtersInput), 300)
    return () => clearTimeout(id)
  }, [filtersInput])

  const { episodes, loading, error, meta, next, prev, canPrev } = useEpisodeSearch({
    taskName: filters.taskName || undefined,
    quality: filters.quality || undefined,
    robotId: filters.robotId || undefined,
    recordedFrom: filters.recordedFrom || undefined,
    recordedTo: filters.recordedTo || undefined,
    assigned: filters.assigned === 'any' ? undefined : filters.assigned === 'true',
  })


  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>Episodes</h1>
          <p className="muted">Browse and search the episode catalog</p>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}

      <EpisodeFilters
        {...filtersInput}
        disabled={loading}
        onChange={(patch) => setFiltersInput((f) => ({ ...f, ...patch }))}
      />

      {loading && episodes.length === 0 ? (
        <p className="muted">Loading…</p>
      ) : (
        <EpisodeTable episodes={episodes} />
      )}

      <PaginationControls
        hasMore={meta.hasMore}
        hasPrev={canPrev}
        onPrev={prev}
        onNext={next}
        disabled={loading}
      />
    </div>
  )
}

export default EpisodesPage