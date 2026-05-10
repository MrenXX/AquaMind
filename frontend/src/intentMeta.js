/**
 * True when text is only `{"intent":"conversational"|"data"}` (no user-facing content).
 * @param {unknown} text
 */
export function isBareIntentMetadataJson(text) {
  const t = (typeof text === 'string' ? text : '').trim()
  if (!t.startsWith('{')) return false
  try {
    const o = JSON.parse(t)
    if (o == null || typeof o !== 'object') return false
    const keys = Object.keys(o)
    return (
      keys.length === 1 &&
      keys[0] === 'intent' &&
      (o.intent === 'conversational' || o.intent === 'data')
    )
  } catch {
    return false
  }
}
