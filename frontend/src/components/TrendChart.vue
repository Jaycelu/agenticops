<template>
  <div class="trend-chart" ref="rootRef" :style="{ width: width || '100%', height: height || '200px' }">
    <canvas ref="canvasRef" :width="canvasWidth" :height="canvasHeight"></canvas>
    <div v-if="!series || series.length === 0" class="empty app-empty">暂无趋势数据</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  series?: { label: string; color: string; values: number[] }[]
  labels?: string[]
  width?: string
  height?: string
  showGrid?: boolean
  yLabel?: string
}>(), {
  series: () => [],
  labels: () => [],
  showGrid: true,
})

const rootRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWidth = ref(600)
const canvasHeight = ref(200)
let resizeObs: ResizeObserver | null = null

const PAD = { top: 20, right: 16, bottom: 32, left: 48 }

function resolveColor(name: string): string {
  if (name.startsWith('--')) return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#2457d6'
  return name
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !props.series.length) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const w = canvas.width
  const h = canvas.height
  const pw = w - PAD.left - PAD.right
  const ph = h - PAD.top - PAD.bottom
  ctx.clearRect(0, 0, w, h)

  // compute bounds
  let min = Infinity, max = -Infinity
  let maxLen = 0
  for (const s of props.series) {
    for (const v of s.values) {
      if (v < min) min = v
      if (v > max) max = v
    }
    if (s.values.length > maxLen) maxLen = s.values.length
  }
  if (maxLen < 2) return
  if (min === max) { min -= 1; max += 1 }
  const yRange = max - min || 1
  const xStep = pw / Math.max(maxLen - 1, 1)

  // grid & axes
  if (props.showGrid) {
    ctx.strokeStyle = resolveColor('--app-border')
    ctx.lineWidth = 1
    for (let i = 0; i < 5; i++) {
      const y = PAD.top + (ph / 4) * i
      ctx.beginPath()
      ctx.moveTo(PAD.left, y)
      ctx.lineTo(PAD.left + pw, y)
      ctx.stroke()
    }
  }

  ctx.font = '11px ui-sans-serif, sans-serif'
  ctx.fillStyle = resolveColor('--app-text-muted')
  ctx.textAlign = 'right'
  for (let i = 0; i < 5; i++) {
    const y = PAD.top + (ph / 4) * i
    const val = Math.round(max - (yRange / 4) * i)
    ctx.fillText(String(val), PAD.left - 6, y + 4)
  }
  ctx.textAlign = 'center'
  if (props.yLabel) {
    ctx.fillText(props.yLabel, PAD.left / 2, 14)
  }

  // x-axis labels (time buckets)
  ctx.fillStyle = resolveColor('--app-text-muted')
  ctx.textAlign = 'center'
  const labelEvery = Math.max(1, Math.floor(maxLen / 8))
  for (let i = 0; i < maxLen; i++) {
    if (i % labelEvery !== 0 && i !== maxLen - 1) continue
    const x = PAD.left + xStep * i
    ctx.fillText(props.labels[i] || String(i), x, h - 6)
  }

  // data lines
  for (let si = 0; si < props.series.length; si++) {
    const s = props.series[si]
    const color = resolveColor(s.color)
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.beginPath()
    for (let i = 0; i < s.values.length; i++) {
      const x = PAD.left + xStep * i
      const y = PAD.top + ph - ((s.values[i] - min) / yRange) * ph
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.stroke()

    // dots
    const dotEvery = Math.max(1, Math.floor(maxLen / 12))
    for (let i = 0; i < s.values.length; i++) {
      if (i % dotEvery !== 0 && i !== s.values.length - 1) continue
      const x = PAD.left + xStep * i
      const y = PAD.top + ph - ((s.values[i] - min) / yRange) * ph
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(x, y, 3, 0, Math.PI * 2)
      ctx.fill()
    }

    // legend
    ctx.fillStyle = color
    ctx.textAlign = 'left'
    ctx.font = '12px ui-sans-serif, sans-serif'
    ctx.fillText(s.label, PAD.left, PAD.top - 6 + si * 16)
  }
}

function resize() {
  if (!rootRef.value || !canvasRef.value) return
  const rect = rootRef.value.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvasWidth.value = Math.round(rect.width * dpr)
  canvasHeight.value = Math.round(parseInt(props.height || '200') * dpr)
  canvasRef.value.width = canvasWidth.value
  canvasRef.value.height = canvasHeight.value
  canvasRef.value.style.width = rect.width + 'px'
  canvasRef.value.style.height = props.height || '200px'
  draw()
}

onMounted(() => {
  resize()
  resizeObs = new ResizeObserver(resize)
  if (rootRef.value) resizeObs.observe(rootRef.value)
})

onUnmounted(() => {
  resizeObs?.disconnect()
})

watch(() => [props.series, props.labels], resize, { deep: true })
</script>

<style scoped>
.trend-chart {
  position: relative;
  min-height: 120px;
}
canvas {
  display: block;
}
.empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
