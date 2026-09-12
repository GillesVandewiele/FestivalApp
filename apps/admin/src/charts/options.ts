import type { EChartsCoreOption } from 'echarts'
import { activeTheme, baseOption } from './theme'

export interface HourRow {
  hour_local: number
  qty: number
}
export interface ProductRow {
  slug: string
  name: string
  category: string
  qty: number
  revenue_eur: number
  margin_eur: number | null
  cost_known: boolean
}
export interface CompareRow {
  slug: string
  name: string
  qty_a: number
  qty_b: number
}

/** Single series: the question is "when is the peak", and position answers it. */
export function hourlyOption(rows: HourRow[]): EChartsCoreOption {
  const theme = activeTheme()
  const base = baseOption(theme)
  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      ...base.axisCommon,
      type: 'category',
      data: rows.map((r) => `${String(r.hour_local).padStart(2, '0')}u`),
      splitLine: { show: false },
    },
    yAxis: { ...base.axisCommon, type: 'value', name: 'consumpties' },
    series: [
      {
        type: 'bar',
        name: 'Consumpties',
        data: rows.map((r) => r.qty),
        itemStyle: { color: theme.color[0], borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 44,
      },
    ],
  }
}

/**
 * Margin against volume. Position and bubble size carry everything, so this is a
 * single-colour series: the scatter form needs the all-pairs pairlist, where only
 * three categorical slots validate, and colour here would be decoration anyway.
 */
export function marginVolumeOption(rows: ProductRow[]): EChartsCoreOption {
  const theme = activeTheme()
  const base = baseOption(theme)
  const priced = rows.filter((r) => r.cost_known && r.margin_eur !== null)
  const maxProfit = Math.max(1, ...priced.map((r) => r.margin_eur ?? 0))

  return {
    ...base,
    grid: { ...base.grid, right: 40 },
    tooltip: {
      ...base.tooltip,
      formatter: (p: { data: { value: number[]; name: string } }) =>
        `<b>${p.data.name}</b><br/>${p.data.value[0]} verkocht<br/>` +
        `marge € ${p.data.value[1].toFixed(2)} per stuk`,
    },
    xAxis: { ...base.axisCommon, type: 'value', name: 'aantal verkocht' },
    yAxis: { ...base.axisCommon, type: 'value', name: 'marge per stuk (€)' },
    series: [
      {
        type: 'scatter',
        name: 'Producten',
        data: priced.map((r) => ({
          name: r.name,
          value: [r.qty, (r.margin_eur ?? 0) / Math.max(1, r.qty), r.margin_eur ?? 0],
        })),
        symbolSize: (v: number[]) => 12 + (v[2] / maxProfit) * 34,
        itemStyle: { color: theme.color[0], opacity: 0.85, borderColor: theme.surface, borderWidth: 2 },
        label: {
          show: true,
          position: 'right',
          formatter: (p: { data: { name: string } }) => p.data.name,
          color: theme.inkDim,
          fontSize: 12,
        },
      },
    ],
  }
}

/**
 * Pareto on ONE axis. A classic Pareto puts counts on the bars and a cumulative
 * percentage on a second y-axis, which is a dual-axis chart. Expressing both as a
 * share of total keeps a single 0-100% scale and reads more directly anyway.
 */
export function paretoOption(rows: ProductRow[]): EChartsCoreOption {
  const theme = activeTheme()
  const base = baseOption(theme)
  const total = rows.reduce((s, r) => s + r.qty, 0) || 1
  const sorted = [...rows].sort((a, b) => b.qty - a.qty)

  let running = 0
  const cumulative = sorted.map((r) => {
    running += r.qty
    return Math.round((running / total) * 1000) / 10
  })

  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis', valueFormatter: (v: number) => `${v}%` },
    legend: { data: ['Aandeel', 'Cumulatief'], textStyle: { color: theme.inkDim }, top: 0 },
    xAxis: {
      ...base.axisCommon,
      type: 'category',
      data: sorted.map((r) => r.name),
      axisLabel: { color: theme.inkDim, rotate: 30 },
      splitLine: { show: false },
    },
    yAxis: { ...base.axisCommon, type: 'value', max: 100, name: '% van volume' },
    series: [
      {
        type: 'bar',
        name: 'Aandeel',
        data: sorted.map((r) => Math.round((r.qty / total) * 1000) / 10),
        itemStyle: { color: theme.color[0], borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 40,
      },
      {
        type: 'line',
        name: 'Cumulatief',
        data: cumulative,
        lineStyle: { width: 2, color: theme.color[1] },
        itemStyle: { color: theme.color[1] },
        symbolSize: 8,
      },
    ],
  }
}

export function compareOption(rows: CompareRow[], labelA: string, labelB: string): EChartsCoreOption {
  const theme = activeTheme()
  const base = baseOption(theme)
  const sorted = [...rows].sort((a, b) => b.qty_b - a.qty_b)

  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: [labelA, labelB], textStyle: { color: theme.inkDim }, top: 0 },
    xAxis: {
      ...base.axisCommon,
      type: 'category',
      data: sorted.map((r) => r.name),
      axisLabel: { color: theme.inkDim, rotate: 30 },
      splitLine: { show: false },
    },
    yAxis: { ...base.axisCommon, type: 'value', name: 'aantal' },
    series: [
      {
        type: 'bar',
        name: labelA,
        data: sorted.map((r) => r.qty_a),
        itemStyle: { color: theme.color[0], borderRadius: [4, 4, 0, 0] },
      },
      {
        type: 'bar',
        name: labelB,
        data: sorted.map((r) => r.qty_b),
        itemStyle: { color: theme.color[1], borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
}
