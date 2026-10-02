import { useEffect, useState } from 'react'
import type { Request, RequestStatus } from '../api/types'
import type { AllowedTransition } from '../lib/transitions'

interface Props {
  request: Request
  transitions: AllowedTransition[]
  submitting: boolean
  onClose: () => void
  onSubmit: (status: RequestStatus, reason?: string) => void
}

export function RequestDetailModal({
  request,
  transitions,
  submitting,
  onClose,
  onSubmit,
}: Props) {
  const [transition, setTransition] = useState<RequestStatus | ''>('')
  const [reason, setReason] = useState('')

  // Escape closes
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const selected = transitions.find((t) => t.status === transition)
  const needsReason = !!selected?.requiresReason
  const canSubmit = !!transition && (!needsReason || reason.trim().length > 0) && !submitting

  const handleSubmit = () => {
    if (!transition) return
    onSubmit(transition, needsReason ? reason.trim() : undefined)
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-content" role="dialog" aria-modal="true">
        <h2>Request Details</h2>

        <div className="detail-section">
          <p><strong>ID:</strong> {request.id}</p>
          <p><strong>Client:</strong> {request.client_name}</p>
          <p><strong>Task Name:</strong> {request.task_name}</p>
          <p><strong>Episodes Requested:</strong> {request.episodes_requested}</p>
          <p><strong>Episodes Assigned:</strong> {request.episodes_assigned}</p>
          <p><strong>Deadline:</strong> {new Date(request.deadline).toLocaleString()}</p>
          <p><strong>Notes:</strong> {request.notes || 'None'}</p>
          <p><strong>Current Status:</strong> {request.status}</p>
          <p><strong>Created At:</strong> {new Date(request.created_at).toLocaleString()}</p>
          <p><strong>Updated At:</strong> {new Date(request.updated_at).toLocaleString()}</p>
          {request.delivered_at && (
            <p><strong>Delivered At:</strong> {new Date(request.delivered_at).toLocaleString()}</p>
          )}
        </div>

        <div className="transition-section">
          <h3>Transition Status</h3>
          {transitions.length === 0 ? (
            <p>No valid transitions available for this request.</p>
          ) : (
            <>
              <label>
                New Status:
                <select
                  value={transition}
                  onChange={(e) => setTransition(e.target.value as RequestStatus)}
                  disabled={submitting}
                >
                  <option value="">Select a transition</option>
                  {transitions.map((t) => (
                    <option key={t.status} value={t.status}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>

              {needsReason && (
                <label>
                  Reason:
                  <textarea
                    rows={3}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Enter reason for status change"
                    disabled={submitting}
                  />
                </label>
              )}

              <div className="modal-actions">
                <button className="btn btn-secondary" onClick={onClose} disabled={submitting}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={handleSubmit} disabled={!canSubmit}>
                  {submitting ? 'Updating…' : 'Update Status'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}