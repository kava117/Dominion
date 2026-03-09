/**
 * Stage 6 tests — Frontend: Project Setup & Board Rendering
 *
 * Exit criteria (must all pass before Stage 7):
 *  1. Setup screen form validates min/max for width and height
 *  2. Submitting setup screen calls POST /game/new and renders the board
 *  3. All tile types render with their correct placeholder color
 *  4. Fog tiles render as dark overlay
 *  5. Wizard tile is always visible (not fogged) even on initial board
 *  6. Board scales correctly for a 12×10 default board and a 24×20 large board
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import SetupScreen from '../components/SetupScreen'
import Board from '../components/Board'
import Tile from '../components/Tile'
import App from '../App'
import assetMap from '../assets/assetMap'

// ── Mock the API module ────────────────────────────────────────────────────

vi.mock('../api', () => ({
  newGame:       vi.fn(),
  getState:      vi.fn(),
  getValidMoves: vi.fn(),
  submitMove:    vi.fn(),
  triggerAiMove: vi.fn(),
}))

import { newGame } from '../api'

// ── Helpers ────────────────────────────────────────────────────────────────

function makeTile(type, { owner = null, visible = true } = {}) {
  return { type, owner, visible }
}

function makeBoard(rows, cols, tileType = 'forest') {
  return Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => makeTile(tileType))
  )
}

function makeGameResponse(width = 12, height = 10, board = null) {
  return {
    game_id:        'test-game',
    board:          board ?? makeBoard(height, width),
    valid_moves:    [],
    scores:         { human: 0, ai: 0 },
    turn:           'human',
    status:         'in_progress',
    wizard_held_by: null,
    seed:           42,
    width,
    height,
    phase:          null,
    phase_data:     {},
  }
}

// ── 1. Setup screen validation ─────────────────────────────────────────────
//
// userEvent is used for number inputs with min/max because jsdom may block
// setting out-of-range values via direct property assignment (fireEvent.change),
// keeping the input at its last valid value and defeating the test.

describe('SetupScreen: width validation', () => {
  it('rejects width below minimum (< 6)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-width'))
    await user.type(screen.getByTestId('input-width'), '5')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.getByTestId('setup-error')).toBeInTheDocument()
    expect(onStart).not.toHaveBeenCalled()
  })

  it('rejects width above maximum (> 24)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-width'))
    await user.type(screen.getByTestId('input-width'), '25')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.getByTestId('setup-error')).toBeInTheDocument()
    expect(onStart).not.toHaveBeenCalled()
  })

  it('accepts width at minimum boundary (6)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-width'))
    await user.type(screen.getByTestId('input-width'), '6')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.queryByTestId('setup-error')).not.toBeInTheDocument()
    expect(onStart).toHaveBeenCalled()
  })

  it('accepts width at maximum boundary (24)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-width'))
    await user.type(screen.getByTestId('input-width'), '24')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.queryByTestId('setup-error')).not.toBeInTheDocument()
    expect(onStart).toHaveBeenCalled()
  })
})

describe('SetupScreen: height validation', () => {
  it('rejects height below minimum (< 6)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-height'))
    await user.type(screen.getByTestId('input-height'), '5')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.getByTestId('setup-error')).toBeInTheDocument()
    expect(onStart).not.toHaveBeenCalled()
  })

  it('rejects height above maximum (> 20)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-height'))
    await user.type(screen.getByTestId('input-height'), '21')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.getByTestId('setup-error')).toBeInTheDocument()
    expect(onStart).not.toHaveBeenCalled()
  })

  it('accepts height at minimum boundary (6)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-height'))
    await user.type(screen.getByTestId('input-height'), '6')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.queryByTestId('setup-error')).not.toBeInTheDocument()
    expect(onStart).toHaveBeenCalled()
  })

  it('accepts height at maximum boundary (20)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    render(<SetupScreen onStart={onStart} />)
    await user.clear(screen.getByTestId('input-height'))
    await user.type(screen.getByTestId('input-height'), '20')
    await user.click(screen.getByTestId('btn-start'))
    expect(screen.queryByTestId('setup-error')).not.toBeInTheDocument()
    expect(onStart).toHaveBeenCalled()
  })
})

// ── 2. Submitting setup calls POST /game/new and renders the board ─────────

describe('App: setup → board transition', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls newGame when the form is submitted', async () => {
    newGame.mockResolvedValueOnce(makeGameResponse())
    render(<App />)
    fireEvent.click(screen.getByTestId('btn-start'))
    await waitFor(() => expect(newGame).toHaveBeenCalledOnce())
  })

  it('passes correct width and height to newGame', async () => {
    newGame.mockResolvedValueOnce(makeGameResponse())
    render(<App />)
    fireEvent.click(screen.getByTestId('btn-start'))
    await waitFor(() => expect(newGame).toHaveBeenCalledOnce())
    expect(newGame).toHaveBeenCalledWith(expect.objectContaining({ width: 12, height: 10 }))
  })

  it('renders the board after a successful newGame response', async () => {
    newGame.mockResolvedValueOnce(makeGameResponse())
    render(<App />)
    fireEvent.click(screen.getByTestId('btn-start'))
    await waitFor(() => expect(screen.getByTestId('board')).toBeInTheDocument())
  })

  it('hides the setup screen once the board is rendered', async () => {
    newGame.mockResolvedValueOnce(makeGameResponse())
    render(<App />)
    expect(screen.getByTestId('btn-start')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('btn-start'))
    await waitFor(() => expect(screen.getByTestId('board')).toBeInTheDocument())
    expect(screen.queryByTestId('btn-start')).not.toBeInTheDocument()
  })

  it('shows a setup error when newGame rejects', async () => {
    newGame.mockRejectedValueOnce(new Error('Server unavailable'))
    render(<App />)
    fireEvent.click(screen.getByTestId('btn-start'))
    await waitFor(() => expect(screen.getByTestId('setup-error')).toBeInTheDocument())
  })
})

// ── 3. All tile types render with their correct placeholder color ───────────

describe('Tile: placeholder colors', () => {
  const neutralTypes = ['forest', 'plains', 'tower', 'cave', 'wizard', 'barbarian', 'mountain', 'domain']

  neutralTypes.forEach(type => {
    it(`"${type}" tile has the assetMap background color`, () => {
      const tile = makeTile(type)
      render(<Tile tile={tile} size={48} />)
      const el = screen.getByTestId('tile')
      expect(el).toHaveStyle({ backgroundColor: assetMap[type].bg })
    })
  })

  it('human-claimed forest tile uses the human variant color', () => {
    const tile = makeTile('forest', { owner: 'human' })
    render(<Tile tile={tile} size={48} />)
    expect(screen.getByTestId('tile')).toHaveStyle({ backgroundColor: assetMap.forest_human.bg })
  })

  it('AI-claimed forest tile uses the AI variant color', () => {
    const tile = makeTile('forest', { owner: 'ai' })
    render(<Tile tile={tile} size={48} />)
    expect(screen.getByTestId('tile')).toHaveStyle({ backgroundColor: assetMap.forest_ai.bg })
  })
})

// ── 4. Fog tiles render as dark overlay ───────────────────────────────────

describe('Board: fog overlay', () => {
  it('renders a fog overlay on a non-visible tile', () => {
    const board = [[makeTile('forest', { visible: false })]]
    render(<Board board={board} />)
    expect(screen.getByTestId('fog-overlay')).toBeInTheDocument()
  })

  it('does not render a fog overlay on a visible tile', () => {
    const board = [[makeTile('forest', { visible: true })]]
    render(<Board board={board} />)
    expect(screen.queryByTestId('fog-overlay')).not.toBeInTheDocument()
  })

  it('fog overlay has a dark background color', () => {
    const board = [[makeTile('forest', { visible: false })]]
    render(<Board board={board} />)
    expect(screen.getByTestId('fog-overlay')).toHaveStyle({ backgroundColor: assetMap.fog.bg })
  })
})

// ── 5. Wizard tile is always visible (not fogged) ─────────────────────────

describe('Board: wizard tile always visible', () => {
  it('wizard tile with visible=true has no fog overlay', () => {
    const board = [[makeTile('wizard', { visible: true })]]
    render(<Board board={board} />)
    expect(screen.queryByTestId('fog-overlay')).not.toBeInTheDocument()
  })

  it('non-wizard invisible tile next to wizard gets fog; wizard does not', () => {
    // Row with wizard (visible) and a forest (not visible)
    const board = [[
      makeTile('wizard',  { visible: true  }),
      makeTile('forest',  { visible: false }),
    ]]
    render(<Board board={board} />)
    const fogOverlays = screen.getAllByTestId('fog-overlay')
    expect(fogOverlays).toHaveLength(1)   // only the forest tile gets fogged
  })
})

// ── 6. Board scales correctly for different board sizes ────────────────────

describe('Board: dimensions', () => {
  it('renders a 12×10 board with correct row/col attributes', () => {
    const board = makeBoard(10, 12)
    render(<Board board={board} />)
    const boardEl = screen.getByTestId('board')
    expect(boardEl).toHaveAttribute('data-rows', '10')
    expect(boardEl).toHaveAttribute('data-cols', '12')
  })

  it('renders a 24×20 board with correct row/col attributes', () => {
    const board = makeBoard(20, 24)
    render(<Board board={board} />)
    const boardEl = screen.getByTestId('board')
    expect(boardEl).toHaveAttribute('data-rows', '20')
    expect(boardEl).toHaveAttribute('data-cols', '24')
  })

  it('renders exactly 120 tiles for a 12×10 board', () => {
    const board = makeBoard(10, 12)
    render(<Board board={board} />)
    expect(screen.getAllByTestId('tile')).toHaveLength(120)
  })

  it('renders exactly 480 tiles for a 24×20 board', () => {
    const board = makeBoard(20, 24)
    render(<Board board={board} />)
    expect(screen.getAllByTestId('tile')).toHaveLength(480)
  })
})
