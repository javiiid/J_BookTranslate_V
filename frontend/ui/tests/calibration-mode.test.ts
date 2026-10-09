import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { CALIBRATION_MODE_KEY, getStoredMode, setStoredMode } from '../src/hooks/useCalibrationMode.ts'

function memory(initial?: string) {
  let value = initial
  return {
    getItem: (_key: string) => value ?? null,
    setItem: (_key: string, next: string) => {
      value = next
    },
  }
}

describe('calibration mode storage', () => {
  it('defaults to simple when nothing is stored', () => {
    assert.equal(getStoredMode(memory()), 'simple')
  })

  it('reads expert back after it is written', () => {
    const store = memory()
    setStoredMode('expert', store)
    assert.equal(store.getItem(CALIBRATION_MODE_KEY), 'expert')
    assert.equal(getStoredMode(store), 'expert')
  })

  it('treats unknown values as simple rather than breaking the layout', () => {
    assert.equal(getStoredMode(memory('weird')), 'simple')
  })
})
