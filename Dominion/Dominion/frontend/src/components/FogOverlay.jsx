import assetMap from '../assets/assetMap'

/**
 * FogOverlay — renders a fog tile (absolutely positioned over a Tile).
 *
 * Used as a sibling overlay so it doesn't interfere with click events on
 * the underlying Tile when fog should block interaction.
 *
 * Props:
 *   size – pixel side length matching the parent Tile (default 48)
 */
export default function FogOverlay({ size = 48 }) {
  const { bg } = assetMap.fog

  const style = {
    position:        'absolute',
    top:             0,
    left:            0,
    width:           size,
    height:          size,
    backgroundColor: bg,
    opacity:         0.85,
    pointerEvents:   'none',
  }

  return <div style={style} data-testid="fog-overlay" aria-hidden="true" />
}
