/**
 * Normalize OpenRouter model slug from SSE / JSON payloads.
 * Backend may use snake_case, camelCase, or `model`.
 *
 * @param {unknown} payload
 * @returns {string | null}
 */
export function parseOpenRouterModel(payload) {
  if (payload == null || typeof payload !== 'object') return null
  const o = /** @type {Record<string, unknown>} */ (payload)
  const candidates = [
    o.openrouter_model,
    o.openrouterModel,
    o.model_slug,
    o.modelSlug,
    o.model,
  ]
  for (const v of candidates) {
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return null
}
