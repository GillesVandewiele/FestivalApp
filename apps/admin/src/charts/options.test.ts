import { describe, expect, it } from 'vitest'
import { compareOption, hourlyOption, marginVolumeOption, paretoOption } from './options'

const products = [
  { slug: 'jupiler', name: 'Jupiler', category: 'bier', qty: 60, revenue_eur: 150, margin_eur: 114, cost_known: true },
  { slug: 'cava', name: 'Cava', category: 'wijn', qty: 20, revenue_eur: 150, margin_eur: 102, cost_known: true },
  { slug: 'water', name: 'Water', category: 'fris', qty: 20, revenue_eur: 50, margin_eur: null, cost_known: false },
]

describe('chart options', () => {
  it('labels hours in Dutch with a leading zero', () => {
    const o = hourlyOption([{ hour_local: 9, qty: 3 }, { hour_local: 20, qty: 40 }]) as never
    expect((o as { xAxis: { data: string[] } }).xAxis.data).toEqual(['09u', '20u'])
  })

  it('never uses a second y-axis', () => {
    // A dual-axis chart is the single most misleading chart form. The Pareto puts
    // both the share and the cumulative share on one 0-100% scale instead.
    for (const o of [hourlyOption([]), paretoOption(products), compareOption([], 'a', 'b')]) {
      expect(Array.isArray((o as { yAxis: unknown }).yAxis)).toBe(false)
    }
  })

  it('caps the pareto axis at 100 percent and ends the cumulative line there', () => {
    const o = paretoOption(products) as unknown as {
      yAxis: { max: number }
      series: { data: number[] }[]
    }
    expect(o.yAxis.max).toBe(100)
    expect(o.series[1].data.at(-1)).toBe(100)
  })

  it('sorts the pareto by descending volume', () => {
    const o = paretoOption(products) as unknown as { xAxis: { data: string[] } }
    expect(o.xAxis.data[0]).toBe('Jupiler')
  })

  it('excludes products without a cost price from the margin scatter', () => {
    // Plotting an unpriced product at zero margin would put a fabricated point
    // into the middle of a purchasing decision.
    const o = marginVolumeOption(products) as unknown as {
      series: { data: { name: string }[] }[]
    }
    expect(o.series[0].data.map((d) => d.name)).toEqual(['Jupiler', 'Cava'])
  })

  it('gives the margin scatter a single colour series', () => {
    const o = marginVolumeOption(products) as unknown as { series: unknown[] }
    expect(o.series).toHaveLength(1)
  })
})
