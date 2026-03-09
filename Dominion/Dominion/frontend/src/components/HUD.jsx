/**
 * HUD — heads-up display shown during an active game.
 *
 * Props:
 *   gameState      – current game state from the backend API
 *   isAiThinking   – bool: AI turn computation is in progress
 *   isWizardMode   – bool: wizard teleport selection is active
 *   onUseWizard    – called when "Use Wizard" button is clicked
 *   onCancelWizard – called when "Cancel" wizard button is clicked
 */
import { useState } from 'react'

export default function HUD({ gameState, isAiThinking, isWizardMode, onUseWizard, onCancelWizard }) {
  const { scores, turn, wizard_held_by, seed, board, phase } = gameState
  const [seedCopied, setSeedCopied] = useState(false)

  function copySeed() {
    navigator.clipboard.writeText(String(seed)).then(() => {
      setSeedCopied(true)
      setTimeout(() => setSeedCopied(false), 1500)
    })
  }

  // Count unclaimed, non-mountain tiles as "remaining claimable"
  const remaining = board.reduce(
    (acc, row) => acc + row.filter(t => !t.owner && t.type !== 'mountain').length,
    0
  )

  const turnLabel = turn === 'human'
    ? 'Your turn'
    : isAiThinking
      ? 'AI is thinking…'
      : "AI's turn"

  const phasePrompt =
    phase === 'plains_first_pick'  ? 'Select your first bonus tile' :
    phase === 'plains_second_pick' ? 'Select your second bonus tile' :
    null

  const showUseWizard   = turn === 'human' && wizard_held_by === 'human' && !isAiThinking && !isWizardMode
  const showCancelWizard = isWizardMode

  const containerStyle = {
    display:      'flex',
    alignItems:   'center',
    gap:          24,
    padding:      '10px 16px',
    background:   '#1e2a38',
    color:        '#ecf0f1',
    fontFamily:   'sans-serif',
    fontSize:     15,
    borderBottom: '2px solid #2c3e50',
    flexWrap:     'wrap',
  }

  const chipStyle = (highlight) => ({
    padding:      '4px 10px',
    borderRadius: 6,
    background:   highlight ? '#e67e22' : '#2c3e50',
    fontWeight:   highlight ? 'bold' : 'normal',
  })

  const btnStyle = (color) => ({
    padding:      '5px 12px',
    borderRadius: 6,
    border:       'none',
    cursor:       'pointer',
    fontSize:     13,
    background:   color,
    color:        '#fff',
  })

  return (
    <div style={containerStyle} data-testid="hud">
      <span style={chipStyle(true)} data-testid="hud-turn">{turnLabel}</span>

      <span data-testid="hud-scores">
        Human: <strong>{scores.human}</strong>
        &nbsp;|&nbsp;
        AI: <strong>{scores.ai}</strong>
      </span>

      <span data-testid="hud-remaining">
        Remaining: <strong>{remaining}</strong>
      </span>

      {phasePrompt && (
        <span style={{ color: '#f39c12', fontWeight: 'bold' }} data-testid="phase-prompt">
          {phasePrompt}
        </span>
      )}

      {wizard_held_by && !isWizardMode && (
        <span style={chipStyle(false)} data-testid="hud-wizard">
          Wizard: {wizard_held_by}
        </span>
      )}

      {showUseWizard && (
        <button style={btnStyle('#8e44ad')} onClick={onUseWizard} data-testid="btn-use-wizard">
          Use Wizard
        </button>
      )}

      {showCancelWizard && (
        <button style={btnStyle('#7f8c8d')} onClick={onCancelWizard} data-testid="btn-cancel-wizard">
          Cancel Wizard
        </button>
      )}

      <span style={{ marginLeft: 'auto', color: '#7f8c8d', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }} data-testid="hud-seed">
        Seed: {seed}
        <button
          onClick={copySeed}
          style={{ background: 'none', border: '1px solid #7f8c8d', borderRadius: 4, color: '#7f8c8d', cursor: 'pointer', fontSize: 11, padding: '1px 6px' }}
          data-testid="btn-copy-seed"
        >
          {seedCopied ? 'Copied!' : 'Copy'}
        </button>
      </span>
    </div>
  )
}
