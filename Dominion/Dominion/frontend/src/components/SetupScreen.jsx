import { useState } from 'react'

/**
 * SetupScreen — pre-game configuration form.
 *
 * Props:
 *   onStart – called with the validated params object when the user submits
 *   error   – optional error string to display
 */
export default function SetupScreen({ onStart, error }) {
  const [width,      setWidth]      = useState(12)
  const [height,     setHeight]     = useState(10)
  const [seed,       setSeed]       = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [domainTiles, setDomainTiles] = useState(2)
  const [firstPlayer, setFirstPlayer] = useState('human')

  const [validationError, setValidationError] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    setValidationError('')

    const w = Number(width)
    const h = Number(height)
    const d = Number(domainTiles)

    if (!Number.isInteger(w) || w < 6 || w > 24) {
      setValidationError('Width must be between 6 and 24.')
      return
    }
    if (!Number.isInteger(h) || h < 6 || h > 20) {
      setValidationError('Height must be between 6 and 20.')
      return
    }
    if (!Number.isInteger(d) || d < 1 || d > 4) {
      setValidationError('Domain tiles per player must be between 1 and 4.')
      return
    }

    const params = { width: w, height: h, difficulty, domain_tiles_per_player: d, first_player: firstPlayer }
    if (seed.trim() !== '') params.seed = Number(seed.trim())

    onStart(params)
  }

  const displayError = validationError || error

  const containerStyle = {
    maxWidth: 480,
    margin: '60px auto',
    padding: 32,
    background: '#1e2a38',
    borderRadius: 12,
    color: '#ecf0f1',
    fontFamily: 'sans-serif',
  }

  const fieldStyle = {
    display: 'flex',
    flexDirection: 'column',
    marginBottom: 16,
  }

  const labelStyle = { marginBottom: 4, fontSize: 14, color: '#bdc3c7' }

  const inputStyle = {
    padding: '8px 10px',
    borderRadius: 6,
    border: '1px solid #4a5568',
    background: '#2d3748',
    color: '#ecf0f1',
    fontSize: 15,
  }

  const btnStyle = {
    width: '100%',
    padding: '12px 0',
    background: '#2980b9',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 16,
    cursor: 'pointer',
    marginTop: 8,
  }

  return (
    <div style={containerStyle}>
      <h1 style={{ textAlign: 'center', marginBottom: 24, letterSpacing: 2 }}>Domain Expansion</h1>
      <form onSubmit={handleSubmit} noValidate>
        <div style={fieldStyle}>
          <label style={labelStyle}>Width (6–24)</label>
          <input
            style={inputStyle}
            type="number"
            min={6}
            max={24}
            value={width}
            onChange={e => setWidth(e.target.value)}
            data-testid="input-width"
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Height (6–20)</label>
          <input
            style={inputStyle}
            type="number"
            min={6}
            max={20}
            value={height}
            onChange={e => setHeight(e.target.value)}
            data-testid="input-height"
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Seed (optional)</label>
          <input
            style={inputStyle}
            type="number"
            placeholder="random"
            value={seed}
            onChange={e => setSeed(e.target.value)}
            data-testid="input-seed"
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Difficulty</label>
          <select
            style={inputStyle}
            value={difficulty}
            onChange={e => setDifficulty(e.target.value)}
            data-testid="select-difficulty"
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Domain tiles per player (1–4)</label>
          <input
            style={inputStyle}
            type="number"
            min={1}
            max={4}
            value={domainTiles}
            onChange={e => setDomainTiles(e.target.value)}
            data-testid="input-domain-tiles"
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>First player</label>
          <select
            style={inputStyle}
            value={firstPlayer}
            onChange={e => setFirstPlayer(e.target.value)}
            data-testid="select-first-player"
          >
            <option value="human">Human</option>
            <option value="ai">AI</option>
          </select>
        </div>

        {displayError && (
          <p style={{ color: '#e74c3c', marginBottom: 8 }} data-testid="setup-error">{displayError}</p>
        )}

        <button style={btnStyle} type="submit" data-testid="btn-start">
          Start Game
        </button>
      </form>
    </div>
  )
}
