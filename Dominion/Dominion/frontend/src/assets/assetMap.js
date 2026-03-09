/**
 * assetMap.js
 *
 * Maps logical tile keys to visual representation.
 * Each entry: { bg, label, textColor }
 *
 * To swap in real PNGs later, add an `img` field to any entry and
 * update Tile.jsx to render <img src={asset.img} /> instead of the bg color.
 *
 * Key format: "<tile_type>" | "<tile_type>_human" | "<tile_type>_ai" | "fog" | "valid_move"
 */

const assetMap = {
  // ── Neutral (unclaimed, visible) ──────────────────────────────────────────
  forest:    { bg: '#4a7c3f', label: '',  textColor: '#fff' },
  plains:    { bg: '#c8b560', label: 'P', textColor: '#333' },
  tower:     { bg: '#8b7355', label: 'T', textColor: '#fff' },
  cave:      { bg: '#5c5c5c', label: 'C', textColor: '#fff' },
  wizard:    { bg: '#7b2d8b', label: 'W', textColor: '#fff' },
  barbarian: { bg: '#c0392b', label: 'B', textColor: '#fff' },
  mountain:  { bg: '#95a5a6', label: 'M', textColor: '#333' },
  domain:    { bg: '#2c3e50', label: 'D', textColor: '#fff' },

  // ── Claimed by human ─────────────────────────────────────────────────────
  forest_human:    { bg: '#2980b9', label: '',  textColor: '#fff' },
  plains_human:    { bg: '#1a6fa3', label: 'P', textColor: '#fff' },
  tower_human:     { bg: '#1560a0', label: 'T', textColor: '#fff' },
  cave_human:      { bg: '#1a5f8a', label: 'C', textColor: '#fff' },
  wizard_human:    { bg: '#1a4f9c', label: 'W', textColor: '#fff' },
  barbarian_human: { bg: '#1a4f9c', label: 'B', textColor: '#fff' },
  domain_human:    { bg: '#1a3a5c', label: 'D', textColor: '#fff' },

  // ── Claimed by AI ─────────────────────────────────────────────────────────
  forest_ai:    { bg: '#e74c3c', label: '',  textColor: '#fff' },
  plains_ai:    { bg: '#d44235', label: 'P', textColor: '#fff' },
  tower_ai:     { bg: '#c0392b', label: 'T', textColor: '#fff' },
  cave_ai:      { bg: '#b03020', label: 'C', textColor: '#fff' },
  wizard_ai:    { bg: '#a02820', label: 'W', textColor: '#fff' },
  barbarian_ai: { bg: '#a02820', label: 'B', textColor: '#fff' },
  domain_ai:    { bg: '#8b1a1a', label: 'D', textColor: '#fff' },

  // ── Special states ────────────────────────────────────────────────────────
  fog:        { bg: '#1a1a2e', label: '',  textColor: '#fff' },
  valid_move: { bg: '#f39c12', label: '',  textColor: '#333' },
}

/**
 * Get the asset for a tile given its type and owner.
 * Falls back to neutral type if owner variant not found.
 */
export function getTileAsset(tileType, owner) {
  if (owner) {
    const key = `${tileType}_${owner}`
    if (assetMap[key]) return assetMap[key]
  }
  return assetMap[tileType] ?? assetMap.forest
}

export default assetMap
