/**
 * api.js — wraps all fetch calls to the backend.
 *
 * All functions return the parsed JSON response body on success.
 * On HTTP error they throw an Error with a `.status` property and a
 * human-readable `.message` extracted from the response body.
 */

const BASE = '/game'

async function _request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)

  const res = await fetch(path, opts)
  const data = await res.json()

  if (!res.ok) {
    const err = new Error(data.error ?? `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return data
}

/**
 * POST /game/new
 * @param {{ width, height, seed, difficulty, domain_tiles_per_player, first_player }} params
 */
export function newGame(params) {
  return _request('POST', `${BASE}/new`, params)
}

/**
 * GET /game/<id>
 */
export function getState(gameId) {
  return _request('GET', `${BASE}/${gameId}`)
}

/**
 * GET /game/<id>/valid-moves
 */
export function getValidMoves(gameId) {
  return _request('GET', `${BASE}/${gameId}/valid-moves`)
}

/**
 * POST /game/<id>/move
 * Normal move: { row, col }
 * Wizard teleport: { wizard: true, row, col }
 */
export function submitMove(gameId, moveBody) {
  return _request('POST', `${BASE}/${gameId}/move`, moveBody)
}

/**
 * POST /game/<id>/ai-move
 */
export function triggerAiMove(gameId) {
  return _request('POST', `${BASE}/${gameId}/ai-move`)
}
