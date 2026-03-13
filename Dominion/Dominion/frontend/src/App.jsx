import { useState } from 'react'
import SetupScreen from './components/SetupScreen'
import Board from './components/Board'
import HUD from './components/HUD'
import EndModal from './components/EndModal'
import RulesModal from './components/RulesModal'
import { newGame, submitMove, triggerAiMove } from './api'

function App() {
  const [gameState,    setGameState]    = useState(null)
  const [setupParams,  setSetupParams]  = useState(null)
  const [setupError,   setSetupError]   = useState('')
  const [isAiThinking, setIsAiThinking] = useState(false)
  const [isWizardMode, setIsWizardMode] = useState(false)
  const [barbarianFlash, setBarbarianFlash] = useState([])
  const [apiError, setApiError] = useState('')
  const [showRules, setShowRules] = useState(false)

  // ── Detect tiles swept by a Barbarian (owned → unowned) ─────────────────
  function detectBarbarian(oldBoard, newBoard) {
    const swept = []
    for (let r = 0; r < oldBoard.length; r++) {
      for (let c = 0; c < (oldBoard[r]?.length ?? 0); c++) {
        if (oldBoard[r][c]?.owner && !newBoard[r]?.[c]?.owner) {
          swept.push([r, c])
        }
      }
    }
    if (swept.length > 0) {
      setBarbarianFlash(swept)
      setTimeout(() => setBarbarianFlash([]), 800)
    }
  }

  // ── AI turn runner ───────────────────────────────────────────────────────
  async function runAiTurn(gameId) {
    setIsAiThinking(true)
    try {
      const data = await triggerAiMove(gameId)
      detectBarbarian(gameState?.board ?? [], data.board)
      setGameState(data)
    } catch (err) {
      setApiError(err.message || 'AI move failed')
    } finally {
      setIsAiThinking(false)
    }
  }

  // ── Start / restart game ─────────────────────────────────────────────────
  async function handleStart(params) {
    setSetupError('')
    setIsWizardMode(false)
    setBarbarianFlash([])
    try {
      const data = await newGame(params)
      setSetupParams(params)
      setGameState(data)
      if (data.status === 'in_progress' && data.turn === 'ai') {
        runAiTurn(data.game_id)
      }
    } catch (err) {
      setSetupError(err.message)
    }
  }

  // ── Tile click ───────────────────────────────────────────────────────────
  async function handleTileClick(row, col) {
    if (!gameState || isAiThinking || gameState.status !== 'in_progress') return
    const moveBody = isWizardMode ? { wizard: true, row, col } : { row, col }
    try {
      const data = await submitMove(gameState.game_id, moveBody)
      setApiError('')
      if (isWizardMode) setIsWizardMode(false)
      detectBarbarian(gameState.board, data.board)
      setGameState(data)
      if (data.status === 'in_progress' && data.turn === 'ai') {
        runAiTurn(data.game_id)
      }
    } catch (err) {
      setApiError(err.message || 'Move failed')
    }
  }

  // ── Wizard mode ──────────────────────────────────────────────────────────
  function enterWizardMode() { setIsWizardMode(true) }
  function cancelWizardMode() { setIsWizardMode(false) }

  // ── End-game actions ─────────────────────────────────────────────────────
  function handlePlayAgain() {
    if (setupParams) handleStart({ ...setupParams, seed: gameState?.seed })
  }

  function handleNewGame() {
    setGameState(null)
    setSetupError('')
    setIsAiThinking(false)
    setIsWizardMode(false)
    setBarbarianFlash([])
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (!gameState) {
    return <SetupScreen onStart={handleStart} error={setupError} />
  }

  const isGameOver       = gameState.status !== 'in_progress'
  const activeValidMoves = (isAiThinking || isGameOver) ? [] : (gameState.valid_moves ?? [])

  return (
    <div style={{ background: '#0f1923', minHeight: '100vh', fontFamily: 'sans-serif' }}>
      {showRules && <RulesModal onClose={() => setShowRules(false)} />}
      {apiError && (
        <div
          style={{
            background: '#c0392b', color: '#fff', padding: '8px 16px',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}
          data-testid="api-error-banner"
        >
          <span>{apiError}</span>
          <button
            onClick={() => setApiError('')}
            style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 18 }}
            data-testid="btn-dismiss-error"
          >×</button>
        </div>
      )}
      <HUD
        gameState={gameState}
        isAiThinking={isAiThinking}
        isWizardMode={isWizardMode}
        onUseWizard={enterWizardMode}
        onCancelWizard={cancelWizardMode}
        onShowRules={() => setShowRules(true)}
        onHome={handleNewGame}
      />
      <div style={{ padding: 16 }}>
        <Board
          board={gameState.board}
          validMoves={activeValidMoves}
          isWizardMode={isWizardMode}
          flashTiles={barbarianFlash}
          onTileClick={handleTileClick}
        />
      </div>
      {isGameOver && (
        <EndModal
          status={gameState.status}
          scores={gameState.scores}
          onPlayAgain={handlePlayAgain}
          onNewGame={handleNewGame}
        />
      )}
    </div>
  )
}

export default App
