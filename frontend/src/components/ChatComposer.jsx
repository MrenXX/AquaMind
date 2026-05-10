/**
 * @param {{
 *   value: string,
 *   streaming: boolean,
 *   onChange: (value: string) => void,
 *   onSend: () => void,
 * }} props
 */
export function ChatComposer({ value, streaming, onChange, onSend }) {
  const disabled = streaming || !value.trim()

  const onKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!disabled) onSend()
    }
  }

  return (
    <form
      className="ws-chat-composer"
      onSubmit={(event) => {
        event.preventDefault()
        if (!disabled) onSend()
      }}
    >
      <textarea
        className="ws-chat-composer__input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask AquaMind..."
        rows={2}
        disabled={streaming}
        aria-label="Ask AquaMind"
      />
      <button
        type="submit"
        className="ws-pill-btn ws-pill-btn--primary ws-chat-composer__send"
        disabled={disabled}
      >
        {streaming ? 'Running...' : 'Send'}
      </button>
    </form>
  )
}
