import { useEffect, useRef, useCallback } from 'react'
import './LiveMap.css'

const CELL_COLORS = {
  0: '#1a2332',
  1: '#243044',
  2: '#2d3a4d',
  3: '#364556',
  4: '#3d4f5f',
  5: '#465968',
}

// Sensitive gradient: 17–24°C, steep response so small temp changes are visible (power 0.55)
function tempToColor(temp) {
  const t = Math.max(17, Math.min(24, temp))
  const x = Math.pow((t - 17) / 7, 0.55)
  let r, g, b
  if (x <= 0.33) {
    const s = x / 0.33
    r = Math.round(25 + (110 - 25) * s)
    g = Math.round(120 + (195 - 120) * s)
    b = Math.round(70 + (55 - 70) * s)
  } else if (x <= 0.66) {
    const s = (x - 0.33) / 0.33
    r = Math.round(110 + (255 - 110) * s)
    g = Math.round(195 + (200 - 195) * s)
    b = Math.round(55 + (45 - 55) * s)
  } else {
    const s = (x - 0.66) / 0.34
    r = 255
    g = Math.round(200 + (70 - 200) * s)
    b = Math.round(45 + (38 - 45) * s)
  }
  return { r, g, b }
}

// Tighter blend so measured temps show more local variation (more sensitive)
const SMOOTH_SIGMA = 0.48
const SMOOTH_RADIUS = 1.5

function sampleTempSmooth(cx, cy, heatRows, heatCols, grid, gridRows, gridCols, heatmapCells) {
  const r0 = Math.max(0, Math.floor(cy - SMOOTH_RADIUS))
  const r1 = Math.min(heatRows - 1, Math.ceil(cy + SMOOTH_RADIUS))
  const c0 = Math.max(0, Math.floor(cx - SMOOTH_RADIUS))
  const c1 = Math.min(heatCols - 1, Math.ceil(cx + SMOOTH_RADIUS))
  let sum = 0
  let weight = 0
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) {
      const coarseR = gridRows ? Math.floor(r * gridRows / heatRows) : r
      const coarseC = gridCols ? Math.floor(c * gridCols / heatCols) : c
      if (grid?.[coarseR]?.[coarseC] === 0) continue
      const t = heatmapCells[`${r},${c}`]
      if (t == null) continue
      const dr = (r + 0.5) - cy
      const dc = (c + 0.5) - cx
      const d2 = dr * dr + dc * dc
      const w = Math.exp(-d2 / (2 * SMOOTH_SIGMA * SMOOTH_SIGMA))
      sum += t * w
      weight += w
    }
  }
  if (weight < 1e-6) return null
  return sum / weight
}

export default function LiveMap({ grid, rows, cols, heatmapRows, heatmapCols, state, trail, heatmapCells = {} }) {
  const canvasRef = useRef(null)
  const PIXELS_PER_CELL = 20
  const scale = Math.min(2.5, Math.max(1, (typeof window !== 'undefined' && window.devicePixelRatio) || 1))
  const hRows = heatmapRows > 0 ? heatmapRows : rows
  const hCols = heatmapCols > 0 ? heatmapCols : cols

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !grid.length || !cols || !rows) return

    const res = Math.round(scale * PIXELS_PER_CELL)
    const w = cols * res
    const h = rows * res
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
    }
    const ctx = canvas.getContext('2d')
    const imageData = ctx.createImageData(w, h)
    const data = imageData.data

    for (let py = 0; py < h; py++) {
      for (let px = 0; px < w; px++) {
        const cx = (px + 0.5) / w * cols
        const cy = (py + 0.5) / h * rows
        const r0 = Math.floor(cy)
        const c0 = Math.floor(cx)
        const cell = grid[r0]?.[c0] ?? 0
        const fineCx = (px + 0.5) / w * hCols
        const fineCy = (py + 0.5) / h * hRows
        let r, g, b
        if (cell === 0) {
          r = 0x1a
          g = 0x23
          b = 0x32
        } else {
          const temp = sampleTempSmooth(fineCx, fineCy, hRows, hCols, grid, rows, cols, heatmapCells)
          if (temp == null) {
            r = 0x28
            g = 0x32
            b = 0x40
          } else {
            const c = tempToColor(temp)
            r = c.r
            g = c.g
            b = c.b
          }
        }
        const i = (py * w + px) * 4
        data[i] = r
        data[i + 1] = g
        data[i + 2] = b
        data[i + 3] = 255
      }
    }
    ctx.putImageData(imageData, 0, 0)

    const cellW = w / cols
    const cellH = h / rows
    if (trail && trail.length > 1) {
      ctx.strokeStyle = 'rgba(0, 212, 170, 0.55)'
      ctx.lineWidth = 2.5
      ctx.beginPath()
      for (let i = 0; i < trail.length; i++) {
        const [x, y] = trail[i]
        const px = (x / cols) * w
        const py = (y / rows) * h
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      }
      ctx.stroke()
    }

    if (state?.position) {
      const { x, y } = state.position
      const px = (x / cols) * w
      const py = (y / rows) * h
      ctx.beginPath()
      ctx.arc(px, py, 7, 0, Math.PI * 2)
      ctx.fillStyle = '#00d4aa'
      ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,0.9)'
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }, [grid, rows, cols, hRows, hCols, state, trail, heatmapCells])

  useEffect(() => {
    draw()
  }, [draw])

  const res = Math.round(scale * PIXELS_PER_CELL)
  const canvasW = Math.max(1, cols) * res
  const canvasH = Math.max(1, rows) * res
  return (
    <div className="live-map">
      <canvas
        ref={canvasRef}
        width={canvasW}
        height={canvasH}
        style={{ width: '100%', height: 'auto', display: 'block', objectFit: 'contain' }}
      />
      <div className="map-legend">
        <span><span className="swatch unexplored" /> Unexplored</span>
        <span><span className="swatch cold" /> Cool</span>
        <span><span className="swatch mid" /> Warm</span>
        <span><span className="swatch hot" /> Hot</span>
      </div>
    </div>
  )
}
