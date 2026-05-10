import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { IconX } from './Icons.jsx'

/**
 * @param {{
 *   open: boolean,
 *   onClose: () => void,
 *   title: string,
 *   children: import('react').ReactNode,
 * }} props
 */
export function PanelFullscreen({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div
      className="ws-fs-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="ws-fs-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ws-fs-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="ws-fs-dialog__head">
          <h2 id="ws-fs-dialog-title" className="ws-fs-dialog__title">
            {title}
          </h2>
          <button
            type="button"
            className="ws-fs-dialog__close ws-icon-btn ws-icon-btn--ghost"
            onClick={onClose}
            aria-label="Close full screen panel"
          >
            <IconX />
          </button>
        </header>
        <div className="ws-fs-dialog__body">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
