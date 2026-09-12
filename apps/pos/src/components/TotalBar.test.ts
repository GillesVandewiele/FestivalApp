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

  it('shows undo only when there is something to undo', async () => {
    const bar = mount(TotalBar, { props: { total: 0, canUndo: true } })
    expect(bar.find('[data-test=undo]').exists()).toBe(true)
    await bar.setProps({ canUndo: false })
    expect(bar.find('[data-test=undo]').exists()).toBe(false)
  })

  it('emits undo when the undo button is tapped', async () => {
    const bar = mount(TotalBar, { props: { total: 0, canUndo: true } })
    await bar.get('[data-test=undo]').trigger('click')
    expect(bar.emitted('undo')).toHaveLength(1)
  })
})
