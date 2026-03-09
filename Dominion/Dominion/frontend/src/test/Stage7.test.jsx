/**
 * Stage 7 tests — Frontend: Game Interaction & AI Turn
 *
 * Exit criteria (must all pass before Stage 8):
 *  1. Clicking a non-highlighted tile does nothing
 *  2. Clicking a highlighted tile sends the correct { row, col } to the backend
 *  3. HUD scores update after each move
 *  4. AI "thinking" indicator appears and disappears correctly
 *  5. End game modal displays correct winner text
 *  6. "Play Again" restarts with the same seed; "New Game" returns to setup screen
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

import { newGame, submitMove, triggerAiMove } from '../api'

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

/** Render App in a fully started game state via the setup flow. */
async function renderInGame(initialState = makeGameResponse()) {
  newGame.mockResolvedValueOnce(initialState)
  render(<App />)
  fireEvent.click(screen.getByTestId('btn-start'))
  await waitFor(() => expect(screen.getByTestId('board')).toBeInTheDocument())
  return initialState
}

// ── 1. Clicking a non-highlighted tile does nothing ────────────────────────

describe('Tile interaction: non-valid tile', () => {
  beforeEach(() => vi.clearAllMocks())

  it('does not call submitMove when clicking a non-highlighted tile', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [] }))

    const tiles = screen.getAllByTestId('tile')
    fireEvent.click(tiles[0])

    expect(submitMove).not.toHaveBeenCalled()
  })

  it('does not call submitMove when board is non-interactive during AI thinking', async () => {
    // Start with human turn
    await renderInGame(makeGameResponse({ valid_moves: [[0, 1]] }))

    // Trigger AI thinking by mocking submitMove → AI turn
    let resolveAiMove
    submitMove.mockResolvedValueOnce(makeGameResponse({ turn: 'ai' }))
    triggerAiMove.mockReturnValueOnce(new Promise(r => { resolveAiMove = r }))

    // Make a human move (transitions to AI thinking)
    const tiles = screen.getAllByTestId('tile')
    fireEvent.click(tiles[1])

    await waitFor(() => expect(screen.getByTestId('hud-turn')).toHaveTextContent('AI is thinking'))

    // Try clicking while AI is thinking
    submitMove.mockClear()
    fireEvent.click(tiles[0])
    expect(submitMove).not.toHaveBeenCalled()

    // Cleanup: resolve AI move
    await act(async () => resolveAiMove(makeGameResponse({ turn: 'human' })))
  })
})

// ── 2. Clicking a highlighted tile sends correct { row, col } ──────────────

describe('Tile interaction: valid tile click', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls submitMove with the correct row and col', async () => {
    const validMoves = [[1, 2]]
    await renderInGame(makeGameResponse({ valid_moves: validMoves }))

    submitMove.mockResolvedValueOnce(makeGameResponse())

    // Find the tile at row=1, col=2. The board is 4 cols wide, so index = 1*4 + 2 = 6
    const tiles = screen.getAllByTestId('tile')
    fireEvent.click(tiles[6])

    await waitFor(() =>
      expect(submitMove).toHaveBeenCalledWith('game-123', { row: 1, col: 2 })
    )
  })

  it('updates the board after a successful move', async () => {
    const validMoves = [[0, 1]]
    await renderInGame(makeGameResponse({ valid_moves: validMoves }))

    const updatedBoard = makeBoard()
    updatedBoard[0][1] = makeTile('forest', { owner: 'human' })
    submitMove.mockResolvedValueOnce(makeGameResponse({
      board:       updatedBoard,
      valid_moves: [],
      scores:      { human: 3, ai: 2 },
    }))

    const tiles = screen.getAllByTestId('tile')
    fireEvent.click(tiles[1])

    await waitFor(() =>
      expect(screen.getByTestId('hud-scores')).toHaveTextContent('Human: 3')
    )
  })
})

// ── 3. HUD scores update after each move ──────────────────────────────────

describe('HUD: score display', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows initial scores from game state', async () => {
    await renderInGame(makeGameResponse({ scores: { human: 4, ai: 3 } }))
    expect(screen.getByTestId('hud-scores')).toHaveTextContent('Human: 4')
    expect(screen.getByTestId('hud-scores')).toHaveTextContent('AI: 3')
  })

  it('updates scores after a move', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]], scores: { human: 2, ai: 2 } }))

    submitMove.mockResolvedValueOnce(makeGameResponse({ scores: { human: 5, ai: 2 } }))
    const tiles = screen.getAllByTestId('tile')
    fireEvent.click(tiles[0])

    await waitFor(() =>
      expect(screen.getByTestId('hud-scores')).toHaveTextContent('Human: 5')
    )
  })

  it('shows remaining claimable tile count', async () => {
    // 4×4 board, all forest, none owned → 16 remaining
    await renderInGame(makeGameResponse())
    expect(screen.getByTestId('hud-remaining')).toHaveTextContent('16')
  })

  it('reduces remaining count when a tile is claimed', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    const claimedBoard = makeBoard()
    claimedBoard[0][0] = makeTile('forest', { owner: 'human' })
    submitMove.mockResolvedValueOnce(makeGameResponse({ board: claimedBoard, valid_moves: [] }))

    fireEvent.click(screen.getAllByTestId('tile')[0])
    await waitFor(() =>
      expect(screen.getByTestId('hud-remaining')).toHaveTextContent('15')
    )
  })

  it('shows seed in HUD', async () => {
    await renderInGame(makeGameResponse({ seed: 99999 }))
    expect(screen.getByTestId('hud-seed')).toHaveTextContent('99999')
  })

  it('shows wizard indicator when a player holds the wizard', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human' }))
    expect(screen.getByTestId('hud-wizard')).toBeInTheDocument()
    expect(screen.getByTestId('hud-wizard')).toHaveTextContent('human')
  })

  it('hides wizard indicator when no one holds it', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: null }))
    expect(screen.queryByTestId('hud-wizard')).not.toBeInTheDocument()
  })
})

// ── 4. AI "thinking" indicator ─────────────────────────────────────────────

describe('AI thinking indicator', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows "AI is thinking" while triggerAiMove is pending', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    let resolveAiMove
    submitMove.mockResolvedValueOnce(makeGameResponse({ turn: 'ai' }))
    triggerAiMove.mockReturnValueOnce(new Promise(r => { resolveAiMove = r }))

    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() =>
      expect(screen.getByTestId('hud-turn')).toHaveTextContent('AI is thinking')
    )

    await act(async () => resolveAiMove(makeGameResponse({ turn: 'human' })))
  })

  it('removes "AI is thinking" after triggerAiMove resolves', async () => {
    await renderInGame(makeGameResponse({ valid_moves: [[0, 0]] }))

    let resolveAiMove
    submitMove.mockResolvedValueOnce(makeGameResponse({ turn: 'ai' }))
    triggerAiMove.mockReturnValueOnce(new Promise(r => { resolveAiMove = r }))

    fireEvent.click(screen.getAllByTestId('tile')[0])
    await waitFor(() =>
      expect(screen.getByTestId('hud-turn')).toHaveTextContent('AI is thinking')
    )

    await act(async () => resolveAiMove(makeGameResponse({ turn: 'human' })))

    await waitFor(() =>
      expect(screen.getByTestId('hud-turn')).toHaveTextContent('Your turn')
    )
  })

  it('triggers AI automatically when the game starts with AI going first', async () => {
    triggerAiMove.mockResolvedValueOnce(makeGameResponse({ turn: 'human' }))
    await renderInGame(makeGameResponse({ turn: 'ai' }))

    await waitFor(() => expect(triggerAiMove).toHaveBeenCalledOnce())
  })
})

// ── 5. End game modal ──────────────────────────────────────────────────────

describe('End game modal', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows "You win!" when status is human_wins', async () => {
    await renderInGame(makeGameResponse({ status: 'human_wins' }))
    expect(screen.getByTestId('end-modal')).toBeInTheDocument()
    expect(screen.getByTestId('end-winner')).toHaveTextContent('You win!')
  })

  it('shows "AI wins!" when status is ai_wins', async () => {
    await renderInGame(makeGameResponse({ status: 'ai_wins' }))
    expect(screen.getByTestId('end-winner')).toHaveTextContent('AI wins!')
  })

  it("shows \"It's a tie!\" when status is tie", async () => {
    await renderInGame(makeGameResponse({ status: 'tie' }))
    expect(screen.getByTestId('end-winner')).toHaveTextContent("It's a tie!")
  })

  it('shows final scores in the end modal', async () => {
    await renderInGame(makeGameResponse({ status: 'human_wins', scores: { human: 10, ai: 6 } }))
    expect(screen.getByTestId('end-scores')).toHaveTextContent('Human: 10')
    expect(screen.getByTestId('end-scores')).toHaveTextContent('AI: 6')
  })

  it('does not show end modal during an in-progress game', async () => {
    await renderInGame(makeGameResponse({ status: 'in_progress' }))
    expect(screen.queryByTestId('end-modal')).not.toBeInTheDocument()
  })
})

// ── 6. Play Again / New Game ───────────────────────────────────────────────

describe('End game actions', () => {
  beforeEach(() => vi.clearAllMocks())

  it('"Play Again" calls newGame with the same seed', async () => {
    await renderInGame(makeGameResponse({ status: 'human_wins', seed: 42 }))

    newGame.mockResolvedValueOnce(makeGameResponse({ seed: 42 }))
    fireEvent.click(screen.getByTestId('btn-play-again'))

    await waitFor(() => expect(newGame).toHaveBeenCalledTimes(2))
    expect(newGame).toHaveBeenLastCalledWith(expect.objectContaining({ seed: 42 }))
  })

  it('"New Game" returns to the setup screen', async () => {
    await renderInGame(makeGameResponse({ status: 'ai_wins' }))

    fireEvent.click(screen.getByTestId('btn-new-game'))

    await waitFor(() =>
      expect(screen.getByTestId('btn-start')).toBeInTheDocument()
    )
    expect(screen.queryByTestId('board')).not.toBeInTheDocument()
  })

  it('"New Game" hides the end modal', async () => {
    await renderInGame(makeGameResponse({ status: 'tie' }))

    fireEvent.click(screen.getByTestId('btn-new-game'))

    await waitFor(() =>
      expect(screen.queryByTestId('end-modal')).not.toBeInTheDocument()
    )
  })
})
