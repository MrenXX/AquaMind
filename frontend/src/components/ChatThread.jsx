import { useEffect, useRef } from 'react'
import { IconTrash } from './Icons.jsx'

/**
 * @param {{
 *   messages: { id: string, role: 'user' | 'assistant' | 'system', text: string }[],
 *   streaming: boolean,
 *   onClearConversation: () => void,
 * }} props
 */
export function ChatThread({ messages, streaming, onClearConversation }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, streaming])

  return (
    <section className="ws-chat-card" aria-label="AquaMind chat">
      <header className="ws-chat-card__head">
        <div>
          <p className="ws-chat-card__eyebrow">Ask AquaMind</p>
          <h1 className="ws-chat-card__title">Chat</h1>
        </div>
        <div className="ws-chat-card__head-actions">
          <button
            type="button"
            className="ws-icon-btn"
            disabled={streaming || messages.length === 0}
            title="Clear conversation"
            aria-label="Clear conversation"
            onClick={() => onClearConversation()}
          >
            <IconTrash />
          </button>
          <span className="ws-chat-card__badge">
            {streaming ? 'Working…' : 'Ready'}
          </span>
        </div>
      </header>
      <div className="ws-chat-thread">
        {messages.length === 0 ? (
          <div className="ws-chat-empty">
            <span className="ws-chat-empty__icon" aria-hidden>
              +
            </span>
            <p className="ws-chat-empty__title">What would you like to check?</p>
            <p className="ws-chat-empty__text">
              Replies appear here during the run. Run output and visualizations stack full width
              beside this chat once results arrive.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <article
              key={message.id}
              className={`ws-chat-bubble ws-chat-bubble--${message.role}`}
            >
              <pre>{message.text}</pre>
            </article>
          ))
        )}
        {streaming ? (
          <div className="ws-chat-typing" aria-label="AquaMind is running">
            <span />
            <span />
            <span />
          </div>
        ) : null}
        <div ref={endRef} />
      </div>
    </section>
  )
}
