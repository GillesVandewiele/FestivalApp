import { describe, expect, it } from 'vitest'
import { CHART_THEME, CHART_THEME_DARK, formatEur, formatNumber, formatPct } from './theme'

describe('chart theme', () => {
  it('formats euros in Dutch convention', () => {
    expect(formatEur(1234.5)).toBe('€ 1.234,50')
    expect(formatEur(0)).toBe('€ 0,00')
  })

  it('renders an unknown value as a dash rather than zero', () => {
    // A missing cost price must never render as 0,00, which reads as free.
    expect(formatEur(null)).toBe('—')
    expect(formatPct(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
  })

  it('always uses one decimal so a column of percentages lines up', () => {
    expect(formatPct(88)).toBe('+88,0%')
    expect(formatPct(73.24)).toBe('+73,2%')
  })

  it('formats percentages with an explicit sign', () => {
    expect(formatPct(12.5)).toBe('+12,5%')
    expect(formatPct(-8)).toBe('−8,0%')
  })

  it('exposes a categorical palette of distinct colours', () => {
    expect(new Set(CHART_THEME.color).size).toBe(CHART_THEME.color.length)
  })

  it('has enough slots for the widest chart, so no series repeats a colour', () => {
    // The stacked hourly chart carries seven drinks plus "Overig". With only five
    // slots the palette wrapped and two drinks shared a colour.
    expect(CHART_THEME.color.length).toBeGreaterThanOrEqual(8)
    expect(CHART_THEME_DARK.color.length).toBe(CHART_THEME.color.length)
  })
})
