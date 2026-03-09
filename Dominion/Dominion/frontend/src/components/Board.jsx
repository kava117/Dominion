import { useMemo } from 'react'
import Tile from './Tile'
import FogOverlay from './FogOverlay'

/**
 * Board component — renders the full 2D grid.
 *
 * Props:
 *   board        – 2D array of tile objects (board[row][col])
 *   validMoves   – array of [row, col] pairs (current player's pool)
 *   isWizardMode – bool: highlight all unclaimed non-mountain tiles
 *   flashTiles   – array of [row, col] pairs that should show the Barbarian flash overlay
 *   onTileClick  – called with (row, col) when an actionable tile is clicked
 *   maxWidth     – max CSS width of the board container (default '100%')
 *   maxHeight    – max CSS height of the board container (default '80vh')
 */
export default function Board({
  board,
  validMoves = [],
  isWizardMode = false,
  flashTiles = [],
  onTileClick,
  maxWidth = '100%',
  maxHeight = '80vh',
}) {
  const height = board.length
  const width  = board[0]?.length ?? 0

  // Build a set of "row,col" strings for O(1) lookup
  const validSet = useMemo(() => {
    const s = new Set()
    for (const [r, c] of validMoves) s.add(`${r},${c}`)
    return s
  }, [validMoves])

  const flashSet = useMemo(() => {
    const s = new Set()
    for (const [r, c] of flashTiles) s.add(`${r},${c}`)
    return s
  }, [flashTiles])

  const tileSize = 48  // base tile size in pixels; Board wrapper uses overflow:auto

  const gridStyle = {
    display:             'grid',
    gridTemplateColumns: `repeat(${width}, ${tileSize}px)`,
    gridTemplateRows:    `repeat(${height}, ${tileSize}px)`,
    gap:                 0,
    maxWidth,
    maxHeight,
    overflow:            'auto',
    border:              '2px solid #333',
    boxSizing:           'border-box',
  }

  return (
    <div style={gridStyle} data-testid="board" data-rows={height} data-cols={width}>
      {board.map((row, r) =>
        row.map((tile, c) => {
          const key        = `${r},${c}`
          const isValid    = validSet.has(key)
          const wizardHit  = isWizardMode && tile.owner == null && tile.type !== 'mountain'
          const isFlashing = flashSet.has(key)

          return (
            <div key={key} style={{ position: 'relative', width: tileSize, height: tileSize }}>
              <Tile
                tile={tile}
                isValidMove={isValid}
                isWizardMode={wizardHit}
                isFlashing={isFlashing}
                size={tileSize}
                onClick={() => onTileClick?.(r, c)}
              />
              {!tile.visible && <FogOverlay size={tileSize} />}
            </div>
          )
        })
      )}
    </div>
  )
}
