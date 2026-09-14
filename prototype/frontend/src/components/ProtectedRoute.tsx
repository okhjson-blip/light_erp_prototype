import { Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth-context'
import AppShell from './AppShell'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-text-secondary">확인 중...</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <AppShell />
}
