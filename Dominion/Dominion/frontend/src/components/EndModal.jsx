/**
 * EndModal — displayed when the game is over.
 *
 * Props:
 *   status      – "human_wins" | "ai_wins" | "tie"
 *   scores      – { human, ai }
 *   onPlayAgain – called when "Play Again" is clicked (same seed)
 *   onNewGame   – called when "New Game" is clicked (back to setup)
 */
export default function EndModal({ status, scores, onPlayAgain, onNewGame }) {
  const winnerText =
    status === 'human_wins' ? 'You win!' :
    status === 'ai_wins'   ? 'AI wins!' :
                              "It's a tie!"

  const overlayStyle = {
    position:       'fixed',
    inset:          0,
    background:     'rgba(0,0,0,0.7)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         100,
  }

  const boxStyle = {
    background:   '#1e2a38',
    color:        '#ecf0f1',
    borderRadius: 12,
    padding:      40,
    textAlign:    'center',
    fontFamily:   'sans-serif',
    minWidth:     280,
  }

  const btnStyle = (primary) => ({
    margin:       '8px 6px 0',
    padding:      '10px 24px',
    borderRadius: 8,
    border:       'none',
    fontSize:     15,
    cursor:       'pointer',
    background:   primary ? '#2980b9' : '#2c3e50',
    color:        '#fff',
  })

  return (
    <div style={overlayStyle} data-testid="end-modal">
      <div style={boxStyle}>
        <h2 style={{ marginTop: 0 }} data-testid="end-winner">{winnerText}</h2>
        <p data-testid="end-scores">Human: {scores.human} &nbsp;|&nbsp; AI: {scores.ai}</p>
        <div>
          <button style={btnStyle(true)} onClick={onPlayAgain} data-testid="btn-play-again">
            Play Again
          </button>
          <button style={btnStyle(false)} onClick={onNewGame} data-testid="btn-new-game">
            New Game
          </button>
        </div>
      </div>
    </div>
  )
}
