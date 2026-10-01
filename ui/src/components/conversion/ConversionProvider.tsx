import { useEffect, useRef, useState, type ReactNode } from 'react'
import { conversionFileError, convertFile, type ConversionFormat } from '@/lib/conversion'
import { ConversionContext, type ConversionEntry } from '@/hooks/useConversion'

export function ConversionProvider({ children }: { children: ReactNode }) {
  const [file, setFile] = useState<File | null>(null)
  const [outputs, setOutputs] = useState<ConversionFormat[]>(['docx'])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [entries, setEntries] = useState<ConversionEntry[]>([])
  const running = useRef(false)
  const sequence = useRef(0)

  useEffect(() => {
    if (!pending) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [pending])

  function selectFiles(files: File[]) {
    if (running.current || !files.length) return
    if (files.length !== 1) {
      setError('در هر عملیات یک فایل انتخاب کنید. می‌توانید چند فرمت خروجی بگیرید.')
      return
    }
    const selected = files[0]!
    const problem = conversionFileError(selected)
    setError(problem)
    if (!problem) setFile(selected)
  }

  function clearFile() {
    if (running.current) return
    setFile(null)
    setError(null)
  }

  function toggleOutput(output: ConversionFormat) {
    if (running.current) return
    setOutputs((current) => current.includes(output) ? current.filter((item) => item !== output) : [...current, output])
  }

  async function start() {
    if (running.current) return
    if (!file || !outputs.length) {
      setError('یک فایل و حداقل یک فرمت خروجی انتخاب کنید.')
      return
    }
    running.current = true
    setPending(true)
    setError(null)
    const key = ++sequence.current
    const entry: ConversionEntry = {
      key, filename: file.name, outputs: [...outputs], createdAt: new Date().toISOString(), result: null, error: null,
    }
    setEntries((current) => [entry, ...current])
    try {
      const result = await convertFile(file, outputs)
      setEntries((current) => current.map((item) => item.key === key ? { ...item, result } : item))
    } catch (failure) {
      const message = failure instanceof Error ? failure.message : 'تبدیل فایل ناموفق بود.'
      setError(message)
      setEntries((current) => current.map((item) => item.key === key ? { ...item, error: message } : item))
    } finally {
      running.current = false
      setPending(false)
    }
  }

  return (
    <ConversionContext.Provider value={{ file, outputs, pending, error, entries, selectFiles, clearFile, toggleOutput, start }}>
      {children}
    </ConversionContext.Provider>
  )
}
