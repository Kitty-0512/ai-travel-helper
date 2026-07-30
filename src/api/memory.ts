/**
 * Agent Memory API client
 */

import { getUserId } from '@/utils/userId'

const API_SECRET_KEY = import.meta.env.VITE_API_SECRET_KEY || 'change-me-to-a-random-string'
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface MemoryItem {
  id: string
  memory_type: string
  content: string
  structured: Record<string, unknown>
  source_session_id?: string | null
  created_time?: string | null
}

export interface MemoryListResponse {
  user_id: string
  available: boolean
  profile: Record<string, unknown>
  memories: MemoryItem[]
}

export interface MemoryDeleteResponse {
  user_id: string
  deleted: number
}

function authHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-API-Key': API_SECRET_KEY,
    'X-User-Id': getUserId(),
  }
}

export async function listMemory(): Promise<MemoryListResponse> {
  const res = await fetch(`${BASE_URL}/api/memory`, {
    method: 'GET',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`GET /api/memory failed: ${res.status}`)
  }
  return res.json()
}

export async function deleteAllMemory(): Promise<MemoryDeleteResponse> {
  const res = await fetch(`${BASE_URL}/api/memory`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`DELETE /api/memory failed: ${res.status}`)
  }
  return res.json()
}

export async function deleteMemory(id: string): Promise<MemoryDeleteResponse> {
  const res = await fetch(`${BASE_URL}/api/memory/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`DELETE /api/memory/${id} failed: ${res.status}`)
  }
  return res.json()
}
