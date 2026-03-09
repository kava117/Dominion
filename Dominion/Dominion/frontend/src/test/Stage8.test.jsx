/**
 * Stage 8 tests — Frontend: Special Tile UX
 *
 * Exit criteria (must all pass before Stage 9):
 *  1. Plains: after claiming Plains, UI shows only distance-2 cardinal tiles as valid picks
 *  2. Plains: after first pick, UI shows only cardinal neighbors of that tile
 *  3. Cave: Cave destinations highlighted alongside normal valid moves after Cave claim
 *  4. Wizard button appears only when human holds the ability; disappears after use
 *  5. Wizard mode highlights all unclaimed non-Mountain tiles
 *  6. Cancel wizard exits mode cleanly without submitting a move
 *  7. Barbarian flash animation fires when swept tiles are detected in new state
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

// ── 1 & 2. Plains phase prompts ────────────────────────────────────────────

describe('Plains: two-step selection UI', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows "Select your first bonus tile" when phase is plains_first_pick', async () => {
    // Start in plains_first_pick phase (e.g., after claiming a Plains tile)
    await renderInGame(makeGameResponse({
      phase:       'plains_first_pick',
      valid_moves: [[0, 2]],
    }))

    expect(screen.getByTestId('phase-prompt')).toHaveTextContent('Select your first bonus tile')
  })

  it('highlights only the valid picks provided by the backend during plains_first_pick', async () => {
    const validMoves = [[0, 2], [2, 0]]
    await renderInGame(makeGameResponse({
      phase:       'plains_first_pick',
      valid_moves: validMoves,
    }))

    const tiles = screen.getAllByTestId('tile')
    // 4-wide board: tile at (0,2)=index 2, (2,0)=index 8
    expect(tiles[2]).toHaveAttribute('data-valid', 'true')
    expect(tiles[8]).toHaveAttribute('data-valid', 'true')
    // other tiles are not valid picks
    expect(tiles[0]).toHaveAttribute('data-valid', 'false')
  })

  it('transitions to "Select your second bonus tile" after first pick', async () => {
    await renderInGame(makeGameResponse({
      phase:       'plains_first_pick',
      valid_moves: [[0, 2]],
    }))

    submitMove.mockResolvedValueOnce(makeGameResponse({
      phase:       'plains_second_pick',
      valid_moves: [[0, 3]],
    }))

    fireEvent.click(screen.getAllByTestId('tile')[2])

    await waitFor(() =>
      expect(screen.getByTestId('phase-prompt')).toHaveTextContent('Select your second bonus tile')
    )
  })

  it('shows "Select your second bonus tile" when phase is plains_second_pick', async () => {
    await renderInGame(makeGameResponse({
      phase:       'plains_second_pick',
      valid_moves: [[0, 3]],
    }))

    expect(screen.getByTestId('phase-prompt')).toHaveTextContent('Select your second bonus tile')
  })

  it('clears the phase prompt after second pick completes', async () => {
    await renderInGame(makeGameResponse({
      phase:       'plains_second_pick',
      valid_moves: [[0, 3]],
    }))

    submitMove.mockResolvedValueOnce(makeGameResponse({ phase: null, valid_moves: [] }))

    fireEvent.click(screen.getAllByTestId('tile')[3])

    await waitFor(() =>
      expect(screen.queryByTestId('phase-prompt')).not.toBeInTheDocument()
    )
  })

  it('does not show phase prompt during a normal turn', async () => {
    await renderInGame(makeGameResponse({ phase: null }))
    expect(screen.queryByTestId('phase-prompt')).not.toBeInTheDocument()
  })
})

// ── 3. Cave: destinations highlighted alongside normal moves ───────────────

describe('Cave: destination highlighting', () => {
  beforeEach(() => vi.clearAllMocks())

  it('highlights Cave tiles that are in valid_moves alongside normal tiles', async () => {
    // After claiming a Cave, other cave positions appear in valid_moves
    const board = makeBoard()
    board[1][1] = makeTile('cave')  // cave destination at (1,1)
    board[2][2] = makeTile('forest') // normal valid move at (2,2)

    const validMoves = [[1, 1], [2, 2]]
    await renderInGame(makeGameResponse({ board, valid_moves: validMoves }))

    const tiles = screen.getAllByTestId('tile')
    expect(tiles[1 * 4 + 1]).toHaveAttribute('data-valid', 'true') // cave tile highlighted
    expect(tiles[2 * 4 + 2]).toHaveAttribute('data-valid', 'true') // normal tile highlighted
    expect(tiles[0]).toHaveAttribute('data-valid', 'false')         // others not highlighted
  })

  it('allows clicking a Cave destination (sends correct row,col)', async () => {
    const board = makeBoard()
    board[1][1] = makeTile('cave')

    await renderInGame(makeGameResponse({ board, valid_moves: [[1, 1]] }))
    submitMove.mockResolvedValueOnce(makeGameResponse())

    fireEvent.click(screen.getAllByTestId('tile')[1 * 4 + 1])

    await waitFor(() =>
      expect(submitMove).toHaveBeenCalledWith('game-123', { row: 1, col: 1 })
    )
  })
})

// ── 4. Wizard button: appears / disappears ─────────────────────────────────

describe('Wizard button visibility', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows "Use Wizard" when human holds wizard on human turn', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human', turn: 'human' }))
    expect(screen.getByTestId('btn-use-wizard')).toBeInTheDocument()
  })

  it('does not show "Use Wizard" when AI holds wizard', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'ai', turn: 'human' }))
    expect(screen.queryByTestId('btn-use-wizard')).not.toBeInTheDocument()
  })

  it('does not show "Use Wizard" when no one holds wizard', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: null }))
    expect(screen.queryByTestId('btn-use-wizard')).not.toBeInTheDocument()
  })

  it('does not show "Use Wizard" on AI turn even if human holds it', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human', turn: 'ai' }))
    expect(screen.queryByTestId('btn-use-wizard')).not.toBeInTheDocument()
  })

  it('wizard button disappears after wizard is used (wizard_held_by becomes null)', async () => {
    await renderInGame(makeGameResponse({
      wizard_held_by: 'human',
      turn:           'human',
      valid_moves:    [],
    }))

    // Enter wizard mode and click a tile
    fireEvent.click(screen.getByTestId('btn-use-wizard'))
    submitMove.mockResolvedValueOnce(makeGameResponse({ wizard_held_by: null }))

    const tiles = screen.getAllByTestId('tile')
    fireEvent.click(tiles[0])

    await waitFor(() =>
      expect(screen.queryByTestId('btn-use-wizard')).not.toBeInTheDocument()
    )
  })
})

// ── 5. Wizard mode: highlights all unclaimed non-Mountain tiles ────────────

describe('Wizard mode: board highlighting', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sets data-wizard=true on all unclaimed non-mountain tiles after entering wizard mode', async () => {
    const board = makeBoard() // all forest, all unowned
    await renderInGame(makeGameResponse({ wizard_held_by: 'human', board }))

    fireEvent.click(screen.getByTestId('btn-use-wizard'))

    const tiles = screen.getAllByTestId('tile')
    // All 16 tiles are forest + unowned → should all be wizard-highlighted
    tiles.forEach(t => expect(t).toHaveAttribute('data-wizard', 'true'))
  })

  it('does NOT set data-wizard=true on mountain tiles', async () => {
    const board = makeBoard()
    board[0][0] = makeTile('mountain')

    await renderInGame(makeGameResponse({ wizard_held_by: 'human', board }))
    fireEvent.click(screen.getByTestId('btn-use-wizard'))

    const tiles = screen.getAllByTestId('tile')
    expect(tiles[0]).toHaveAttribute('data-wizard', 'false') // mountain excluded
    expect(tiles[1]).toHaveAttribute('data-wizard', 'true')  // forest included
  })

  it('does NOT set data-wizard=true on tiles already owned by a player', async () => {
    const board = makeBoard()
    board[1][1] = makeTile('forest', { owner: 'human' })

    await renderInGame(makeGameResponse({ wizard_held_by: 'human', board }))
    fireEvent.click(screen.getByTestId('btn-use-wizard'))

    const tiles = screen.getAllByTestId('tile')
    expect(tiles[1 * 4 + 1]).toHaveAttribute('data-wizard', 'false') // claimed → excluded
    expect(tiles[0]).toHaveAttribute('data-wizard', 'true')           // unclaimed → included
  })

  it('sends { wizard: true, row, col } when clicking a tile in wizard mode', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human' }))
    submitMove.mockResolvedValueOnce(makeGameResponse({ wizard_held_by: null }))

    fireEvent.click(screen.getByTestId('btn-use-wizard'))
    fireEvent.click(screen.getAllByTestId('tile')[5]) // tile at (1,1) in a 4-wide board

    await waitFor(() =>
      expect(submitMove).toHaveBeenCalledWith('game-123', { wizard: true, row: 1, col: 1 })
    )
  })
})

// ── 6. Cancel wizard exits mode cleanly ───────────────────────────────────

describe('Cancel wizard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows "Cancel Wizard" button after entering wizard mode', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human' }))
    fireEvent.click(screen.getByTestId('btn-use-wizard'))
    expect(screen.getByTestId('btn-cancel-wizard')).toBeInTheDocument()
  })

  it('exits wizard mode without submitting a move when Cancel is clicked', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human' }))
    fireEvent.click(screen.getByTestId('btn-use-wizard'))

    // Verify we're in wizard mode (data-wizard on tiles)
    expect(screen.getAllByTestId('tile')[0]).toHaveAttribute('data-wizard', 'true')

    fireEvent.click(screen.getByTestId('btn-cancel-wizard'))

    // Wizard mode exits: tiles no longer wizard-highlighted
    await waitFor(() =>
      expect(screen.getAllByTestId('tile')[0]).toHaveAttribute('data-wizard', 'false')
    )
    expect(submitMove).not.toHaveBeenCalled()
  })

  it('"Use Wizard" button reappears after cancel', async () => {
    await renderInGame(makeGameResponse({ wizard_held_by: 'human' }))
    fireEvent.click(screen.getByTestId('btn-use-wizard'))
    expect(screen.queryByTestId('btn-use-wizard')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('btn-cancel-wizard'))
    await waitFor(() =>
      expect(screen.getByTestId('btn-use-wizard')).toBeInTheDocument()
    )
  })
})

// ── 7. Barbarian flash ────────────────────────────────────────────────────

describe('Barbarian flash animation', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows barbarian-flash overlay on tiles that transition from owned to unowned', async () => {
    // Initial board: tile (0,0) is owned by human
    const initialBoard = makeBoard()
    initialBoard[0][0] = makeTile('forest', { owner: 'human' })

    await renderInGame(makeGameResponse({ board: initialBoard, valid_moves: [[0, 1]] }))

    // After a move, the barbarian sweeps (0,0) — it becomes unowned
    const postMoveBoard = makeBoard()
    // (0,0) is now unowned (swept by barbarian)
    submitMove.mockResolvedValueOnce(makeGameResponse({ board: postMoveBoard }))

    fireEvent.click(screen.getAllByTestId('tile')[1]) // click valid move at (0,1)

    await waitFor(() =>
      expect(screen.getAllByTestId('barbarian-flash').length).toBeGreaterThan(0)
    )
  })

  it('does not show barbarian-flash when no tiles are swept', async () => {
    const board = makeBoard()
    await renderInGame(makeGameResponse({ board, valid_moves: [[0, 0]] }))

    // After move: same board ownership (no sweep)
    submitMove.mockResolvedValueOnce(makeGameResponse({ board }))

    fireEvent.click(screen.getAllByTestId('tile')[0])

    await waitFor(() => expect(submitMove).toHaveBeenCalled())
    expect(screen.queryByTestId('barbarian-flash')).not.toBeInTheDocument()
  })
})
