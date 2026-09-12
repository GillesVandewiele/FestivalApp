/**
 * One theme for every chart, so the reports read as a single system.
 *
 * The palette is the dataviz reference categorical set, validated with
 * scripts/validate_palette.js in both modes on the adjacent pairlist:
 * worst CVD dE 9.1 light / 8.4 dark, worst normal-vision dE 19.6 light / 19.3 dark.
 *
 * Deliberately NOT the POS app's category colours. Those work as 6px borders on
 * large tinted buttons, but as small chart marks the teal and blue sit at dE 11.5
 * for normal vision, under the 15 floor, and teal and brown fall below the chroma
 * floor and read as grey.
 *
 * Three light-mode slots fall below 3:1 against the surface, so the relief rule
 * applies: every chart ships a legend and a table view of the same numbers.
 */
export const SERIES_LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'] as const
export const SERIES_DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181'] as const

export interface ChartTheme {
  color: string[]
  surface: string
  ink: string
  inkDim: string
  grid: string
}

export const CHART_THEME: ChartTheme = {
  color: [...SERIES_LIGHT],
  surface: '#fcfcfb',
  ink: '#1a1a19',
  inkDim: '#5f5e58',
  grid: '#e7e6e1',
}

export const CHART_THEME_DARK: ChartTheme = {
  color: [...SERIES_DARK],
  surface: '#1a1a19',
  ink: '#ffffff',
  inkDim: '#c3c2b7',
  grid: '#33322e',
}

export function isDark(): boolean {
  if (typeof document === 'undefined') return false
  const stamped = document.documentElement.dataset.theme
  if (stamped === 'dark') return true
  if (stamped === 'light') return false
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function activeTheme(): ChartTheme {
  return isDark() ? CHART_THEME_DARK : CHART_THEME
}

const EUR = new Intl.NumberFormat('nl-BE', { style: 'currency', currency: 'EUR' })
const NUM = new Intl.NumberFormat('nl-BE')
// One decimal always, so a column of percentages lines up instead of mixing
// "+88%" with "+73,2%".
const PCT = new Intl.NumberFormat('nl-BE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** An unknown value renders as a dash. Never as 0,00, which reads as free. */
export function formatEur(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return EUR.format(value).replace(/ /g, ' ')
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return NUM.format(value)
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const sign = value < 0 ? '−' : '+'
  return `${sign}${PCT.format(Math.abs(value))}%`
}

/** Shared axis and grid styling so no chart invents its own chrome. */
export function baseOption(theme: ChartTheme = activeTheme()) {
  return {
    color: theme.color,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'system-ui, -apple-system, Segoe UI, sans-serif' },
    grid: { left: 56, right: 20, top: 28, bottom: 44, containLabel: true },
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: theme.surface,
      borderColor: theme.grid,
      textStyle: { color: theme.ink },
    },
    axisCommon: {
      axisLine: { lineStyle: { color: theme.grid } },
      axisTick: { show: false },
      axisLabel: { color: theme.inkDim },
      splitLine: { lineStyle: { color: theme.grid, type: 'dashed' as const } },
    },
  }
}
