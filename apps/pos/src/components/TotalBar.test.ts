import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TotalBar from './TotalBar.vue'

describe('TotalBar', () => {
  it('shows the coupon total in Dutch', () => {
    const bar = mount(TotalBar, { props: { total: 5, canUndo: false } })
    expect(bar.text()).toContain('5')
    expect(bar.text()).toContain('bonnetjes')
  })

  it('uses the singular for one coupon', () => {
    const bar = mount(TotalBar, { props: { total: 1, canUndo: false } })
    expect(bar.text()).toContain('bonnetje')
    expect(bar.text()).not.toContain('bonnetjes')
  })

  it('emits commit when tapped with a non-empty order', async () => {
    const bar = mount(TotalBar, { props: { total: 3, canUndo: false } })
    await bar.get('[data-test=commit]').trigger('click')
    expect(bar.emitted('commit')).toHaveLength(1)
  })

  it('does not emit commit on an empty order', async () => {
    const bar = mount(TotalBar, { props: { total: 0, canUndo: false } })
    await bar.get('[data-test=commit]').trigger('click')
    expect(bar.emitted('commit')).toBeUndefined()
  })

  it('ignores a second tap inside the debounce window', async () => {
    // A double-tap must never create two sales.
    const bar = mount(TotalBar, { props: { total: 3, canUndo: false } })
    await bar.get('[data-test=commit]').trigger('click')
    await bar.get('[data-test=commit]').trigger('click')
    expect(bar.emitted('commit')).toHaveLength(1)
  })

  it('always shows undo, disabled when there is nothing to undo', async () => {
    // Rendering it only after the first sale made it undiscoverable, and made the
    // bar jump when it appeared. It is always present and disabled instead.
    const bar = mount(TotalBar, { props: { total: 0, canUndo: false } })
    const undo = bar.get('[data-test=undo]')
    expect(undo.attributes('disabled')).toBeDefined()

    await bar.setProps({ canUndo: true })
    expect(bar.get('[data-test=undo]').attributes('disabled')).toBeUndefined()
  })

  it('does not emit undo while disabled', async () => {
    const bar = mount(TotalBar, { props: { total: 0, canUndo: false } })
    await bar.get('[data-test=undo]').trigger('click')
    expect(bar.emitted('undo')).toBeUndefined()
  })

  it('emits undo when the undo button is tapped', async () => {
    const bar = mount(TotalBar, { props: { total: 0, canUndo: true } })
    await bar.get('[data-test=undo]').trigger('click')
    expect(bar.emitted('undo')).toHaveLength(1)
  })
})
