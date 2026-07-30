/**
 * Persistent anonymous user id for Agent Memory (X-User-Id).
 */

const STORAGE_KEY = 'ai_travel_helper_user_id'

function createId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `u_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

/** Get or create a stable user id in localStorage. */
export function getUserId(): string {
  try {
    const existing = localStorage.getItem(STORAGE_KEY)
    if (existing && existing.trim()) {
      return existing.trim()
    }
    const id = createId()
    localStorage.setItem(STORAGE_KEY, id)
    return id
  } catch {
    // Private mode / blocked storage — ephemeral id for this page load
    return createId()
  }
}
