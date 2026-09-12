import { describe, expect, it } from 'vitest'
import { computeRowHeight, type FitInput } from './useFittedRows'

const BASE: FitInput = {
  groupSizes: [],
  minColumnPx: 150,
  gapPx: 10,
  headingPx: 26,
  sectionGapPx: 14,
  minRowPx: 56,
  maxRowPx: 132,
}

describe('fitting the till on one screen', () => {
  it('never grows a button past the maximum, however much room there is', () => {
    // One category of four drinks on a tall screen would otherwise become four
    // full-height columns, which is what the fixed layout used to do.
    const { rowHeight, fits } = computeRowHeight(1280, 1400, { ...BASE, groupSizes: [4] })

    expect(fits).toBe(true)
    expect(rowHeight).toBe(BASE.maxRowPx)
  })

  it('leaves the surplus space empty rather than stretching', () => {
    const roomy = computeRowHeight(1280, 2000, { ...BASE, groupSizes: [4] }).rowHeight
    const tight = computeRowHeight(1280, 1000, { ...BASE, groupSizes: [4] }).rowHeight

    expect(roomy).toBe(tight) // both capped; the taller screen just has more blank
  })

  it('shrinks the buttons as categories are added', () => {
    const four = computeRowHeight(600, 700, { ...BASE, groupSizes: [4, 4, 4, 4] }).rowHeight
    const eight = computeRowHeight(600, 700, {
      ...BASE,
      groupSizes: [4, 4, 4, 4, 4, 4, 4, 4],
    }).rowHeight

    expect(eight).toBeLessThan(four)
  })

  it('accounts for a category wrapping onto a second row', () => {
    // 3 columns at 600px, so 12 drinks is four rows against 8 drinks in three.
    const fewer = computeRowHeight(600, 500, { ...BASE, groupSizes: [8] }).rowHeight
    const more = computeRowHeight(600, 500, { ...BASE, groupSizes: [12] }).rowHeight

    expect(more).toBeLessThan(fewer)
  })

  it('gives fewer columns, and so more rows, on a narrow screen', () => {
    // 1280 fits 8 in one row and hits the cap; 480 fits 3 across, so 3 rows, and the
    // height has to be shared out.
    const wide = computeRowHeight(1280, 400, { ...BASE, groupSizes: [8] }).rowHeight
    const narrow = computeRowHeight(480, 400, { ...BASE, groupSizes: [8] }).rowHeight

    expect(wide).toBe(BASE.maxRowPx)
    expect(narrow).toBeLessThan(wide)
  })

  it('never returns a button too small to hit, and says so', () => {
    // Twelve categories of eight drinks on a phone-sized screen cannot fit.
    const { rowHeight, fits } = computeRowHeight(400, 600, {
      ...BASE,
      groupSizes: Array(12).fill(8),
    })

    expect(rowHeight).toBe(BASE.minRowPx)
    expect(fits).toBe(false) // the caller lets it scroll rather than shrink further
  })

  it('ignores empty categories', () => {
    const withEmpty = computeRowHeight(1280, 800, { ...BASE, groupSizes: [4, 0, 0] }).rowHeight
    const without = computeRowHeight(1280, 800, { ...BASE, groupSizes: [4] }).rowHeight

    expect(withEmpty).toBe(without)
  })

  it('copes with being measured before layout', () => {
    expect(computeRowHeight(0, 0, { ...BASE, groupSizes: [4] }).rowHeight).toBe(BASE.maxRowPx)
  })

  it('reports the column count it used', () => {
    // 1280 wide with a 150px minimum and a 10px gap fits eight across.
    expect(computeRowHeight(1280, 800, { ...BASE, groupSizes: [8] }).columns).toBe(8)
    expect(computeRowHeight(414, 800, { ...BASE, groupSizes: [8] }).columns).toBe(2)
  })

  it('never claims more columns than the biggest category needs', () => {
    // A wide screen fits eleven across, but with three drinks per category eight of
    // those tracks would be empty and every button needlessly narrow.
    const { columns } = computeRowHeight(1920, 1200, { ...BASE, groupSizes: [3, 3, 3, 1] })
    expect(columns).toBe(3)
  })

  it('always keeps at least one column, however narrow', () => {
    // 80px cannot hold a 150px column, but one column is the floor rather than zero.
    // 3 drinks in 1 column is 3 rows: (400 - 26 - 20) / 3 = 118.
    const { rowHeight, fits } = computeRowHeight(80, 400, { ...BASE, groupSizes: [3] })

    expect(fits).toBe(true)
    expect(rowHeight).toBe(118)
  })
})
