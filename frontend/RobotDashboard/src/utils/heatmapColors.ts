/**
 * Shared heatmap color gradient. Use this everywhere for consistent visuals.
 * Range: 14–26°C. Blue/cyan (cool) → green → yellow → orange/red (hot).
 */
const T_MIN = 14
const T_MAX = 26

function tempToRgb(temp: number): { r: number; g: number; b: number } {
  const t = Math.max(T_MIN, Math.min(T_MAX, temp))
  const x = (t - T_MIN) / (T_MAX - T_MIN)
  let r: number, g: number, b: number
  if (x <= 0.35) {
    const s = x / 0.35
    r = Math.round(40 + (60 - 40) * s)
    g = Math.round(100 + (180 - 100) * s)
    b = Math.round(200 + (140 - 200) * s)
  } else if (x <= 0.6) {
    const s = (x - 0.35) / 0.25
    r = Math.round(60 + (140 - 60) * s)
    g = Math.round(180 + (220 - 180) * s)
    b = Math.round(140 + (80 - 140) * s)
  } else if (x <= 0.85) {
    const s = (x - 0.6) / 0.25
    r = Math.round(140 + (255 - 140) * s)
    g = Math.round(220 + (200 - 220) * s)
    b = Math.round(80 + (50 - 80) * s)
  } else {
    const s = (x - 0.85) / 0.15
    r = 255
    g = Math.round(200 + (80 - 200) * s)
    b = Math.round(50 + (40 - 50) * s)
  }
  return { r, g, b }
}

export function tempToColorHex(temp: number): number {
  const { r, g, b } = tempToRgb(temp)
  return (r << 16) | (g << 8) | b
}

export function tempToColor(temp: number): { r: number; g: number; b: number } {
  return tempToRgb(temp)
}
