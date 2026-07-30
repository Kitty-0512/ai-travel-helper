/**
 * Session history API client
 * list / get / delete past trip planning sessions
 */

import { getUserId } from '@/utils/userId'

const API_SECRET_KEY = import.meta.env.VITE_API_SECRET_KEY || 'change-me-to-a-random-string'
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// ── Types ───────────────────────────────────────────────────

export interface SessionSummary {
  session_id: string
  destination: string
  days: number
  styles: string[]
  created_at: string
}

export interface SessionDetail {
  session_id: string
  destination: string
  days: number
  styles: string[]
  itinerary: {
    days: { day: number; morning: string; afternoon: string; evening: string }[]
    allPlaces: string[]
  } | null
  places_detail: {
    name: string
    lng: number
    lat: number
  }[] | null
  markdown_text: string
  created_at: string
}

export interface SessionListResponse {
  user_id: string
  sessions: SessionSummary[]
}

export interface DeleteResponse {
  session_id: string
  deleted: boolean
}

// ── Helpers ─────────────────────────────────────────────────

function authHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-API-Key': API_SECRET_KEY,
    'X-User-Id': getUserId(),
  }
}

// ── Public API ──────────────────────────────────────────────

export async function listSessions(): Promise<SessionListResponse> {
  const res = await fetch(`${BASE_URL}/api/sessions`, {
    method: 'GET',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`GET /api/sessions failed: ${res.status}`)
  }
  return res.json()
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${BASE_URL}/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'GET',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`GET /api/sessions/${sessionId} failed: ${res.status}`)
  }
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<DeleteResponse> {
  const res = await fetch(`${BASE_URL}/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`DELETE /api/sessions/${sessionId} failed: ${res.status}`)
  }
  return res.json()
}
