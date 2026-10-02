interface Props {
  hasPrev: boolean
  hasMore: boolean
  onPrev: () => void
  onNext: () => void
  disabled?: boolean
}

export function PaginationControls({ hasPrev, hasMore, onPrev, onNext, disabled }: Props) {
  return (
    <div className="pagination">
      <button className="btn" onClick={onPrev} disabled={!hasPrev || disabled}>
        ← Previous
      </button>
      <button className="btn" onClick={onNext} disabled={!hasMore || disabled}>
        Next →
      </button>
    </div>
  )
}