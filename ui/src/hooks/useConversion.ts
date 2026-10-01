import { createContext, useContext } from 'react'
import type { ConversionFormat, ConversionResult } from '@/lib/conversion'

export interface ConversionEntry {
  key: number
  filename: string
  createdAt: string
  outputs: ConversionFormat[]
  result: ConversionResult | null
  error: string | null
}

interface ConversionContextValue {
  file: File | null
  outputs: ConversionFormat[]
  pending: boolean
  error: string | null
  entries: ConversionEntry[]
  selectFiles: (files: File[]) => void
  clearFile: () => void
  toggleOutput: (output: ConversionFormat) => void
  start: () => Promise<void>
}

export const ConversionContext = createContext<ConversionContextValue | null>(null)

export function useConversion() {
  const context = useContext(ConversionContext)
  if (!context) throw new Error('ConversionProvider is required')
  return context
}
