import { getTileAsset } from '../assets/assetMap'

/**
 * Tile component — renders a single board tile.
 *
 * Props:
 *   tile         – tile object from the backend (type, owner, visible, ...)
 *   isValidMove  – bool: this tile is in the current player's valid moves pool
 *   isWizardMode – bool: wizard teleport mode active (all non-mountain unclaimed highlighted)
 *   isFlashing   – bool: tile is briefly highlighted due to a Barbarian sweep
 *   onClick      – called with () when the tile is actionable and clicked
 *   size         – pixel side length of the tile (default 48)
 */
export default function Tile({ tile, isValidMove, isWizardMode, isFlashing, onClick, size = 48 }) {
  const clickable = isValidMove || isWizardMode
  const asset = getTileAsset(tile.type, tile.owner)

  const style = {
    width:           size,
    height:          size,
    backgroundColor: asset.bg,
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'center',
    fontSize:        Math.max(10, size * 0.25),
    fontWeight:      'bold',
    color:           asset.textColor,
    cursor:          clickable ? 'pointer' : 'default',
    boxSizing:       'border-box',
    border:          isValidMove || isWizardMode ? '2px solid #f1c40f' : '1px solid rgba(0,0,0,0.15)',
    position:        'relative',
    userSelect:      'none',
    transition:      'filter 0.15s',
  }

  function handleClick() {
    if (clickable && onClick) onClick()
  }

  return (
    <div
      style={style}
      onClick={handleClick}
      data-testid="tile"
      data-tile-type={tile.type}
      data-owner={tile.owner ?? ''}
      data-valid={isValidMove ? 'true' : 'false'}
      data-wizard={isWizardMode ? 'true' : 'false'}
      data-visible={tile.visible ? 'true' : 'false'}
    >
      {!tile.visible ? null : asset.label}

      {isFlashing && (
        <div
          style={{
            position:        'absolute',
            inset:           0,
            backgroundColor: '#e74c3c',
            opacity:         0.65,
            pointerEvents:   'none',
            transition:      'opacity 0.8s',
          }}
          data-testid="barbarian-flash"
          aria-hidden="true"
        />
      )}
    </div>
  )
}
