import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth-context'

export default function LoginPage() {
  const { user, loading, login } = useAuth()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && user) {
    return <Navigate to="/dashboard" replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(password)
    } catch (err) {
      setError(err instanceof Error ? err.message : '접속에 실패했습니다')
      setBusy(false)
      return
    }
    setBusy(false)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <section className="w-full max-w-sm rounded-card border border-border-default bg-card p-8 shadow-sm">
        <div className="mb-1 text-lg font-semibold text-brand">AX ERP</div>
        <p className="mb-6 text-sm font-medium text-text-primary">Light ERP Prototype</p>
        <p className="mb-4 text-xs text-text-secondary">접속 비밀번호를 입력하세요.</p>
        <form onSubmit={onSubmit} className="space-y-3">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="접속 비밀번호"
            autoFocus
            autoComplete="current-password"
            className="w-full rounded-md border border-border-default bg-canvas px-3 py-2.5 text-sm outline-none focus:border-brand"
          />
          {error ? <p className="text-xs text-danger">{error}</p> : null}
          <button
            type="submit"
            disabled={busy || !password}
            className="block w-full rounded-md bg-brand px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-60"
          >
            {busy ? '접속 중…' : '접속'}
          </button>
        </form>
      </section>
    </div>
  )
}
