/**
 * Stage 9 tests — Frontend: Integration, Polish & End-to-End
 *
 * Exit criteria (must all pass):
 *  1. API error banner appears when submitMove rejects
 *  2. Error banner shows the error message text
 *  3. Game remains interactive after an API error (tiles still clickable)
 *  4. Dismissing the error banner hides it
 *  5. Error clears after a successful move
 *  6. Seed copy-to-clipboard button is present in HUD
 *  7. Clicking copy button shows "Copied!" feedback
 *  8. "Copied!" feedback reverts to "Copy" after timeout
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import App from '../App'

// ── Mock the API module ────────────────────────────────────────────────────

vi.mock('../api', () => ({
  newGame:       vi.fn(),
  getState:      vi.fn(),
  getValidMoves: vi.fn(),
  submitMove:    vi.fn(),
  triggerAiMove: vi.fn(),
}))

import { newGame, submitMove } from '../api'

// ── Helpers ────────────────────────────────────────────────────────────────

function makeTile(type = 'forest', { owner = null, visible = true } = {}) {
  return { type, owner, visible }
}

function makeBoard(rows = 4, cols = 4, tileType = 'forest') {
  return Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => makeTile(tileType))
  )
}

function makeGameResponse(overrides = {}) {
  return {
    game_id:        'game-123',
    board:          makeBoard(),
    valid_moves:    [],
    scores:         { human: 2, ai: 2 },
    turn:           'human',
    status:         'in_progress',
    wizard_held_by: null,
    seed:           42,
    width:          4,
    height:         4,
    phase:          null,
    phase_data:     {},
    ...overrides,
  }
}

async function renderInGame(initialState = makeGameResponse()) {
  newGame.mockResolvedValueOnce(initialState)
  render(<App />)
  fireEvent.click(screen.getByTestId('btn-start'))
  await waitFor(() => expect(screen.getByTestId('board')).toBeInTheDocument())
  return initialState
}

// ── 1–5. API error banner ──────────────────────────────────────────────────

describe('API error banner', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows error banner when submitMove rejects', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    submitMove.mockRejectedValueOnce(new Error('Move rejected by server'))

    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() =>
      expect(screen.getByTestId('api-error-banner')).toBeInTheDocument()
    )
  })

  it('error banner contains the error message', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    submitMove.mockRejectedValueOnce(new Error('Move rejected by server'))

    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() =>
      expect(screen.getByTestId('api-error-banner')).toHaveTextContent(
        'Move rejected by server'
      )
    )
  })

  it('game remains interactive after error (board still rendered)', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    submitMove.mockRejectedValueOnce(new Error('Network error'))

    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() =>
      expect(screen.getByTestId('api-error-banner')).toBeInTheDocument()
    )

    // Board is still present
    expect(screen.getByTestId('board')).toBeInTheDocument()
    // Tiles are still rendered
    expect(screen.getAllByTestId('tile').length).toBeGreaterThan(0)
  })

  it('dismiss button clears the error banner', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    submitMove.mockRejectedValueOnce(new Error('Oops'))

    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() =>
      expect(screen.getByTestId('api-error-banner')).toBeInTheDocument()
    )

    fireEvent.click(screen.getByTestId('btn-dismiss-error'))

    await waitFor(() =>
      expect(screen.queryByTestId('api-error-banner')).not.toBeInTheDocument()
    )
  })

  it('error banner disappears after a subsequent successful move', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0], [0, 1]] }))

    // First move fails
    submitMove.mockRejectedValueOnce(new Error('Temporary error'))
    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() =>
      expect(screen.getByTestId('api-error-banner')).toBeInTheDocument()
    )

    // Second move succeeds — error should clear
    submitMove.mockResolvedValueOnce(makeGameResponse({ valid_moves: [] }))
    fireEvent.click(screen.getAllByTestId('tile')[1])

    await waitFor(() =>
      expect(screen.queryByTestId('api-error-banner')).not.toBeInTheDocument()
    )
  })
})

// ── 6–8. Seed copy-to-clipboard ────────────────────────────────────────────

describe('Seed copy-to-clipboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  it('copy seed button is present in the HUD', async () => {
    await renderInGame()
    expect(screen.getByTestId('btn-copy-seed')).toBeInTheDocument()
  })

  it('clicking copy button calls clipboard.writeText with the seed', async () => {
    await renderInGame(makeGameResponse({ seed: 1234 }))

    fireEvent.click(screen.getByTestId('btn-copy-seed'))

    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('1234')
    )
  })

  it('button label changes to "Copied!" after click', async () => {
    await renderInGame()

    fireEvent.click(screen.getByTestId('btn-copy-seed'))

    await waitFor(() =>
      expect(screen.getByTestId('btn-copy-seed')).toHaveTextContent('Copied!')
    )
  })

  it('"Copied!" label reverts to "Copy" after timeout', async () => {
    // Render with real timers first (waitFor inside renderInGame needs them)
    await renderInGame()

    vi.useFakeTimers()
    try {
      await act(async () => {
        fireEvent.click(screen.getByTestId('btn-copy-seed'))
        // Flush the clipboard promise microtask
        await Promise.resolve()
      })

      expect(screen.getByTestId('btn-copy-seed')).toHaveTextContent('Copied!')

      await act(async () => { vi.advanceTimersByTime(1500) })

      expect(screen.getByTestId('btn-copy-seed')).toHaveTextContent('Copy')
    } finally {
      vi.useRealTimers()
    }
  })
})
