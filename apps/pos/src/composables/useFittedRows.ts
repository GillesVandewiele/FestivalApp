import { onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'

export interface FitInput {
  /** Number of products in each category group, in display order. */
  groupSizes: number[]
  /** Minimum width of one product button. */
  minColumnPx: number
  /** Gap between buttons and between rows. */
  gapPx: number
  /** Height of a category heading plus its bottom margin. */
  headingPx: number
  /** Gap between category sections. */
  sectionGapPx: number
  /** Below this a button stops being usable, so scrolling is the lesser evil. */
  minRowPx: number
  /** Above this a button just looks like a slab. Leftover space stays empty. */
  maxRowPx: number
}

/**
 * Work out how tall a product button may be so the whole till fits on one screen.
 *
 * Staff should never scroll to find a drink: at a bar the row that is off-screen is
 * the row nobody sells from. Width takes care of itself because the grid wraps, but
 * height does not, so it is measured.
 *
 * Shrinking to fit is the point; growing is not. A single category of ten drinks on a
 * tall screen should not become ten full-height columns, so the result is capped at
 * `maxRowPx` and the leftover space is simply left empty.
 *
 * When even the minimum button height will not fit, this gives up and returns
 * `minRowPx`, letting the container scroll. A button too small to hit reliably is
 * worse than a scrollbar.
 */
export function computeRowHeight(
  width: number,
  height: number,
  input: FitInput,
): { rowHeight: number; columns: number; fits: boolean } {
  const { groupSizes, minColumnPx, gapPx, headingPx, sectionGapPx, minRowPx, maxRowPx } = input
  const groups = groupSizes.filter((n) => n > 0)
  if (!groups.length || width <= 0 || height <= 0) {
    return { rowHeight: maxRowPx, columns: 1, fits: true }
  }

  const fitsAcross = Math.max(1, Math.floor((width + gapPx) / (minColumnPx + gapPx)))
  // No category has more drinks than the biggest one, so any track past that is empty.
  // Bounding the grid to the columns actually used lets the buttons grow toward their
  // cap instead of staying narrow with half the screen blank.
  const columns = Math.min(fitsAcross, Math.max(...groups))
  const rowsPerGroup = groups.map((n) => Math.ceil(n / columns))
  const totalRows = rowsPerGroup.reduce((a, b) => a + b, 0)

  const chrome =
    groups.length * headingPx +
    (groups.length - 1) * sectionGapPx +
    rowsPerGroup.reduce((sum, rows) => sum + (rows - 1) * gapPx, 0)

  const available = height - chrome
  const rowHeight = available / totalRows

  if (rowHeight < minRowPx) return { rowHeight: minRowPx, columns, fits: false }
  return { rowHeight: Math.floor(Math.min(rowHeight, maxRowPx)), columns, fits: true }
}

/** Keeps `computeRowHeight` up to date as the element or the catalogue changes. */
export function useFittedRows(el: Ref<HTMLElement | undefined>, input: Ref<FitInput>) {
  // Start at the cap, not the floor, so the first paint is not a row of slivers.
  const rowHeight = ref(input.value.maxRowPx)
  const columns = ref(1)
  const fits = ref(true)
  let observer: ResizeObserver | undefined

  function measure() {
    if (!el.value) return
    const result = computeRowHeight(el.value.clientWidth, el.value.clientHeight, input.value)
    rowHeight.value = result.rowHeight
    columns.value = result.columns
    fits.value = result.fits
  }

  onMounted(() => {
    measure()
    if (typeof ResizeObserver !== 'undefined' && el.value) {
      observer = new ResizeObserver(measure)
      observer.observe(el.value)
    }
  })
  onBeforeUnmount(() => observer?.disconnect())
  watch(input, measure, { deep: true })

  return { rowHeight, columns, fits, measure }
}
