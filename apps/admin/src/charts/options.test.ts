import { describe, expect, it } from 'vitest'
import {
  compareOption,
  hourlyOption,
  hourlyStackedOption,
  marginVolumeOption,
  paretoOption,
} from './options'

const products = [
  { slug: 'jupiler', name: 'Jupiler', category: 'bier', qty: 60, revenue_eur: 150, margin_eur: 114, cost_known: true },
  { slug: 'cava', name: 'Cava', category: 'wijn', qty: 20, revenue_eur: 150, margin_eur: 102, cost_known: true },
  { slug: 'water', name: 'Water', category: 'fris', qty: 20, revenue_eur: 50, margin_eur: null, cost_known: false },
]

describe('chart options', () => {
  it('labels hours in Dutch with a leading zero', () => {
    const o = hourlyOption([
      { hour_local: 9, qty: 3, coupons: 3, revenue_eur: 7, margin_eur: 4 },
      { hour_local: 20, qty: 40, coupons: 55, revenue_eur: 137, margin_eur: 80 },
    ]) as never
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

const stack = {
  hours: [22, 23, 0],
  series: [
    { name: 'Jupiler', data: [10, 20, 15] },
    { name: 'Water', data: [4, 8, 9] },
    { name: 'Overig', data: [2, 3, 1] },
  ],
}

describe('hourly chart', () => {
  it('switches the plotted metric without a second request', () => {
    const rows = [
      { hour_local: 22, qty: 10, coupons: 14, revenue_eur: 35, margin_eur: 20 },
      { hour_local: 23, qty: 20, coupons: 28, revenue_eur: 70, margin_eur: 41 },
    ]
    const asQty = hourlyOption(rows, 'qty') as unknown as { series: { data: number[] }[] }
    const asRevenue = hourlyOption(rows, 'revenue_eur') as unknown as {
      series: { data: number[] }[]
    }

    expect(asQty.series[0].data).toEqual([10, 20])
    expect(asRevenue.series[0].data).toEqual([35, 70])
  })

  it('plots an unknown margin as zero rather than breaking the chart', () => {
    // The table alongside shows a dash; the bar simply has no height.
    const rows = [{ hour_local: 22, qty: 10, coupons: 14, revenue_eur: 35, margin_eur: null }]
    const o = hourlyOption(rows, 'margin_eur') as unknown as { series: { data: number[] }[] }
    expect(o.series[0].data).toEqual([0])
  })

  it('stacks every series onto one group', () => {
    const o = hourlyStackedOption(stack) as unknown as { series: { stack: string }[] }
    expect(o.series.map((s) => s.stack)).toEqual(['uur', 'uur', 'uur'])
  })

  it('always shows a legend for a stack, so colour is never the only encoding', () => {
    const o = hourlyStackedOption(stack) as unknown as { legend: { data: string[] } }
    expect(o.legend.data).toEqual(['Jupiler', 'Water', 'Overig'])
  })

  it('never needs a ninth colour', () => {
    // The backend folds everything past the seventh drink into "Overig".
    const o = hourlyStackedOption(stack) as unknown as { series: unknown[] }
    expect(o.series.length).toBeLessThanOrEqual(8)
  })

  it('gives every stacked series its own colour', () => {
    const eight = {
      hours: [22],
      series: Array.from({ length: 8 }, (_, i) => ({ name: `s${i}`, data: [1] })),
    }
    const o = hourlyStackedOption(eight) as unknown as {
      series: { itemStyle: { color: string } }[]
    }
    const colours = o.series.map((s) => s.itemStyle.color)
    expect(new Set(colours).size).toBe(8)
  })

  it('keeps the stacked chart on one axis too', () => {
    const o = hourlyStackedOption(stack) as unknown as { yAxis: unknown }
    expect(Array.isArray(o.yAxis)).toBe(false)
  })
})
