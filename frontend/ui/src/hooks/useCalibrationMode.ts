import { useCallback, useState } from 'react'

export const CALIBRATION_MODE_KEY = 'kalima-calibration-mode'

export type CalibrationMode = 'simple' | 'expert'

export function getStoredMode(storage?: Pick<Storage, 'getItem'>): CalibrationMode {
  try {
    const source = storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
    const value = source?.getItem(CALIBRATION_MODE_KEY)
    return value === 'expert' ? 'expert' : 'simple'
  } catch {
    return 'simple'
  }
}

export function setStoredMode(mode: CalibrationMode, storage?: Pick<Storage, 'setItem'>): void {
  try {
    const target = storage ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
    target?.setItem(CALIBRATION_MODE_KEY, mode)
  } catch {
    // Private-mode storage failure must not break the toggle in memory.
  }
}

/**
 * Simple/expert toggle for the calibration workshop.
 * Defaults to simple (the 4-step wizard); experts opt into the full view.
 * Persisted so a refresh mid-step does not reset the layout.
 */
export function useCalibrationMode() {
  const [mode, setModeState] = useState<CalibrationMode>(() => getStoredMode())
  const setMode = useCallback((next: CalibrationMode) => {
    setModeState(next)
    setStoredMode(next)
  }, [])
  return { mode, setMode, isSimple: mode === 'simple' }
}
