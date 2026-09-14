import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Monitor } from 'lucide-react'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface SessionInfo {
  family_id: string
  user_agent: string | null
  created_at: string
  last_seen_at: string | null
  expires_at: string
}

/* v8: 디바이스별 다중 세션(로그인된 기기) 조회 + 개별 로그아웃. GET /api/auth/sessions,
   POST /api/auth/sessions/{family_id}/logout (app/main.py 참고). 낯선 기기의 로그인을
   사용자 스스로 알아채고 개별 로그아웃할 수 있게 하는 것이 목적이다. */
export function SessionsDialog() {
  const qc = useQueryClient()
  const [error, setError] = useState('')

  const sessions = useQuery({
    queryKey: ['auth-sessions'],
    queryFn: () => apiGet<SessionInfo[]>('/api/auth/sessions'),
  })

  const logoutSession = useMutation({
    mutationFn: (familyId: string) => apiPost(`/api/auth/sessions/${familyId}/logout`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth-sessions'] }),
    onError: (err) => setError(err instanceof ApiError ? err.message : '로그아웃 실패'),
  })

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          title="로그인된 기기 관리"
          className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary"
        >
          <Monitor size={14} />
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>로그인된 기기</DialogTitle>
        </DialogHeader>
        {error && <p className="mb-2 text-xs text-danger">{error}</p>}
        {sessions.isLoading || !sessions.data ? (
          <p className="text-sm text-text-secondary">불러오는 중...</p>
        ) : sessions.data.length === 0 ? (
          <p className="text-sm text-text-secondary">활성 세션이 없습니다.</p>
        ) : (
          <ul className="space-y-2">
            {sessions.data.map((s) => (
              <li
                key={s.family_id}
                className="flex items-center justify-between rounded-control border border-border-default px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm text-text-primary">{s.user_agent || '알 수 없는 기기'}</div>
                  <div className="text-xs text-text-secondary">
                    최근 활동: {s.last_seen_at ? new Date(s.last_seen_at).toLocaleString() : '-'}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={logoutSession.isPending}
                  onClick={() => logoutSession.mutate(s.family_id)}
                >
                  로그아웃
                </Button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  )
}
