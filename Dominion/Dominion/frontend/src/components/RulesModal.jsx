/**
 * RulesModal — overlay showing game rules.
 *
 * Props:
 *   onClose – called when the modal is dismissed
 */
export default function RulesModal({ onClose }) {
  const overlay = {
    position:       'fixed',
    inset:          0,
    background:     'rgba(0,0,0,0.75)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         1000,
    padding:        16,
  }

  const modal = {
    background:   '#1e2a38',
    color:        '#ecf0f1',
    borderRadius: 12,
    padding:      '28px 32px',
    maxWidth:     620,
    width:        '100%',
    maxHeight:    '85vh',
    overflowY:    'auto',
    fontFamily:   'sans-serif',
    position:     'relative',
  }

  const h1 = {
    margin:       '0 0 4px',
    fontSize:     22,
    letterSpacing: 2,
    textAlign:    'center',
  }

  const subtitle = {
    textAlign:  'center',
    color:      '#7f8c8d',
    fontSize:   13,
    marginBottom: 20,
  }

  const h2 = {
    fontSize:     15,
    color:        '#f39c12',
    margin:       '20px 0 8px',
    textTransform: 'uppercase',
    letterSpacing: 1,
  }

  const p = { margin: '0 0 8px', lineHeight: 1.6, fontSize: 14 }

  const table = {
    width:          '100%',
    borderCollapse: 'collapse',
    fontSize:       13,
    marginBottom:   4,
  }

  const th = {
    textAlign:     'left',
    padding:       '5px 8px',
    background:    '#2c3e50',
    color:         '#bdc3c7',
    borderBottom:  '1px solid #4a5568',
  }

  const tdL = {
    padding:      '6px 8px',
    borderBottom: '1px solid #2c3e50',
    fontWeight:   'bold',
    whiteSpace:   'nowrap',
    color:        '#c9a84c',
  }

  const tdR = {
    padding:      '6px 8px',
    borderBottom: '1px solid #2c3e50',
    lineHeight:   1.5,
  }

  const closeBtnStyle = {
    position:     'absolute',
    top:          12,
    right:        16,
    background:   'none',
    border:       'none',
    color:        '#7f8c8d',
    fontSize:     22,
    cursor:       'pointer',
    lineHeight:   1,
  }

  const tileRows = [
    ['Forest',    'Your main terrain. Unlocks all cardinally adjacent tiles (up/down/left/right) as valid moves.'],
    ['Domain',    'Your starting tile — works exactly like Forest.'],
    ['Plains',    'Bonus turn: claim this tile, then pick 2 extra tiles this turn instead of 1.'],
    ['Tower',     'Lifts fog within 3 tiles; unlocks tiles exactly 3 steps away as new valid moves.'],
    ['Cave',      'Unlocks all other unclaimed Caves. Claim one on your next turn to connect both (both score). If you skip, the Cave keeps its power.'],
    ['Wizard',    'Always visible through fog. Gives a one-time power to teleport to any unclaimed tile on the board.'],
    ['Barbarian', 'Cannot be claimed while active. When revealed through fog, it instantly charges across its entire row or column — unclaiming every tile it passes through, friend or foe. It then becomes claimable Forest.'],
    ['Mountain',  'Impassable. Can never be claimed and never counts toward any score.'],
  ]

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={e => e.stopPropagation()} data-testid="rules-modal">
        <button style={closeBtnStyle} onClick={onClose} data-testid="btn-close-rules" aria-label="Close rules">×</button>

        <h1 style={h1}>Domain Expansion</h1>
        <p style={subtitle}>Rules &amp; Reference</p>

        <h2 style={h2}>Objective</h2>
        <p style={p}>
          Claim more tiles than your opponent. The game ends when all claimable tiles are taken,
          or one player holds more than half and their opponent can no longer catch up.
          Most tiles wins. Mountains never count.
        </p>

        <h2 style={h2}>How to Play</h2>
        <p style={p}>Players alternate turns. Humans go first by default.</p>
        <p style={p}>
          Each turn, click a <strong>highlighted tile</strong> to claim it.
          You can only claim tiles in your <em>valid moves pool</em> — the highlighted tiles on the board.
          When you claim a tile, new tiles may unlock based on that tile's type.
        </p>

        <h2 style={h2}>Tile Types</h2>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Tile</th>
              <th style={th}>Effect</th>
            </tr>
          </thead>
          <tbody>
            {tileRows.map(([name, desc]) => (
              <tr key={name}>
                <td style={tdL}>{name}</td>
                <td style={tdR}>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2 style={h2}>Fog of War</h2>
        <p style={p}>
          Tiles you haven't reached are hidden. Fog lifts when a tile enters your valid moves pool,
          is claimed, or is revealed by a Tower. The <strong>Wizard tile is always visible</strong> through fog.
        </p>

        <h2 style={h2}>Win Conditions</h2>
        <p style={p}>
          <strong>Full board:</strong> All claimable tiles taken — most tiles wins. Ties are possible.
        </p>
        <p style={{ ...p, marginBottom: 0 }}>
          <strong>Dominant win:</strong> If you hold more than half of all claimable tiles and your
          opponent has no valid moves that can change the outcome, you win immediately.
        </p>
      </div>
    </div>
  )
}
