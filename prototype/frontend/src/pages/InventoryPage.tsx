import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '@/components/StatusBadge'
import type {
  InventoryRow,
  InventoryTxn,
  Lot,
  LotTrace,
  SerialNumber,
  SerialTrace,
  LotReconciliation,
} from '@/lib/types'

const SERIAL_STATUSES = ['IN_STOCK', 'SHIPPED', 'DEFECTIVE', 'SCRAPPED']

export default function InventoryPage() {
  const { hasRole } = useAuth()
  const canManageSerial = hasRole('생산담당', '관리자')
  const qc = useQueryClient()
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [serialStatusDraft, setSerialStatusDraft] = useState<Record<number, string>>({})

  const inventory = useQuery({ queryKey: ['inventory'], queryFn: () => apiGet<InventoryRow[]>('/api/inventory') })
  const txns = useQuery({
    queryKey: ['inventory-txns'],
    queryFn: () => apiGet<InventoryTxn[]>('/api/inventory/transactions'),
  })
  const lots = useQuery({ queryKey: ['lots'], queryFn: () => apiGet<Lot[]>('/api/lots') })
  const serials = useQuery({ queryKey: ['serials'], queryFn: () => apiGet<SerialNumber[]>('/api/serials') })
  const reconciliation = useQuery({
    queryKey: ['lot-reconciliation'],
    queryFn: () => apiGet<LotReconciliation[]>('/api/lots/reconciliation'),
  })

  async function traceLot(lotId: number) {
    setError('')
    try {
      const t = await apiGet<LotTrace>(`/api/lots/${lotId}/trace`)
      const cons = t.consumptions.map((c) => `${c.ref_doc_type}#${c.ref_doc_id ?? '-'} ${c.qty}`).join(', ') || '없음'
      setMsg(`LOT ${t.lot.lot_no}: 잔여 ${t.lot.qty} / 소진이력 [${cons}] / 시리얼 ${t.serials.length}건`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '추적 실패')
    }
  }

  async function traceSerial(serialNo: string) {
    setError('')
    try {
      const t = await apiGet<SerialTrace>(`/api/serials/${serialNo}/trace`)
      setMsg(
        `시리얼 ${t.serial.serial_no}: 상태 ${t.serial.status}` +
          (t.lot ? `, 소속 LOT ${t.lot.lot_no}(생성출처 ${t.lot.source_type}#${t.lot.source_ref_id ?? '-'})` : ''),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '추적 실패')
    }
  }

  const changeSerialStatus = useMutation({
    mutationFn: ({ serialNo, status }: { serialNo: string; status: string }) =>
      apiPost(`/api/serials/${serialNo}/status`, { status }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['serials'] })
      setMsg(`시리얼 ${vars.serialNo} 상태를 ${vars.status}(으)로 변경했습니다.`)
    },
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text-primary">재고</h1>
      {error && <p className="text-xs text-danger">{error}</p>}
      {msg && <p className="text-xs text-success">{msg}</p>}

      <Card>
        <CardHeader>
          <CardTitle>현재고</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>코드</TableHead>
              <TableHead>품목</TableHead>
              <TableHead>창고</TableHead>
              <TableHead className="text-right">수량</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(inventory.data ?? []).map((row) => (
              <TableRow key={row.inventory_id}>
                <TableCell>{row.code}</TableCell>
                <TableCell>{row.material_name}</TableCell>
                <TableCell>{row.warehouse_name}</TableCell>
                <TableCell className="text-right">{row.qty}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>재고 이동 이력</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>품목</TableHead>
              <TableHead>구분</TableHead>
              <TableHead className="text-right">수량</TableHead>
              <TableHead>참조문서</TableHead>
              <TableHead>일시</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(txns.data ?? []).map((t) => (
              <TableRow key={t.txn_id}>
                <TableCell>{t.txn_id}</TableCell>
                <TableCell>{t.material_name}</TableCell>
                <TableCell>{t.txn_type}</TableCell>
                <TableCell className="text-right">{t.qty}</TableCell>
                <TableCell>{t.ref_doc_type}</TableCell>
                <TableCell>{t.txn_date}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>LOT 추적 (WMS)</CardTitle>
        </CardHeader>
        <p className="mb-2 text-xs text-text-secondary">
          입고/생산/출하 시 자동 생성·소진되는 LOT 단위 추적입니다. "추적" 버튼으로 해당 LOT의 소진 이력을 확인할 수 있습니다.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>LOT번호</TableHead>
              <TableHead>품목</TableHead>
              <TableHead>창고</TableHead>
              <TableHead className="text-right">잔여수량</TableHead>
              <TableHead>출처</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>생성일시</TableHead>
              <TableHead>액션</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(lots.data ?? []).map((l) => (
              <TableRow key={l.lot_id}>
                <TableCell>{l.lot_no}</TableCell>
                <TableCell>{l.material_name}</TableCell>
                <TableCell>{l.warehouse_name}</TableCell>
                <TableCell className="text-right">{l.qty}</TableCell>
                <TableCell>{l.source_type}</TableCell>
                <TableCell>
                  <StatusBadge status={l.status} />
                </TableCell>
                <TableCell>{l.created_date}</TableCell>
                <TableCell>
                  <Button type="button" size="sm" variant="outline" onClick={() => traceLot(l.lot_id)}>
                    추적
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>시리얼 추적 (선택 기능)</CardTitle>
        </CardHeader>
        <p className="mb-2 text-xs text-text-secondary">생산실적입력 시 "시리얼 생성"을 체크한 경우에만 생성됩니다.</p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시리얼번호</TableHead>
              <TableHead>품목</TableHead>
              <TableHead>소속LOT</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>생성일시</TableHead>
              <TableHead>액션</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(serials.data ?? []).map((s) => (
              <TableRow key={s.serial_id}>
                <TableCell>{s.serial_no}</TableCell>
                <TableCell>{s.material_name}</TableCell>
                <TableCell>{s.lot_no}</TableCell>
                <TableCell>
                  <StatusBadge status={s.status} />
                </TableCell>
                <TableCell>{s.created_date}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {canManageSerial && (
                      <>
                        <Select
                          className="h-8 w-32 text-xs"
                          value={serialStatusDraft[s.serial_id] ?? s.status}
                          onChange={(e) =>
                            setSerialStatusDraft((prev) => ({ ...prev, [s.serial_id]: e.target.value }))
                          }
                        >
                          {SERIAL_STATUSES.map((st) => (
                            <option key={st} value={st}>
                              {st}
                            </option>
                          ))}
                        </Select>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            changeSerialStatus.mutate({
                              serialNo: s.serial_no,
                              status: serialStatusDraft[s.serial_id] ?? s.status,
                            })
                          }
                        >
                          변경
                        </Button>
                      </>
                    )}
                    <Button type="button" size="sm" variant="ghost" onClick={() => traceSerial(s.serial_no)}>
                      추적
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>LOT 정합성 점검</CardTitle>
        </CardHeader>
        <p className="mb-2 text-xs text-text-secondary">
          품목·창고별 활성 LOT 합계와 재고 집계(inventory.qty)를 비교합니다. "미추적수량"이 양수인 것은 과거
          임포트 재고 등 LOT이 없는 정상적인 경우입니다. "부정합"으로 표시된 행은 LOT 합계가 재고 집계를
          초과한 경우로, 실제 오류일 수 있어 확인이 필요합니다.
        </p>
        {(reconciliation.data ?? []).length === 0 ? (
          <p className="text-xs text-text-secondary">LOT 데이터 없음</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>품목</TableHead>
                <TableHead>창고</TableHead>
                <TableHead className="text-right">재고집계</TableHead>
                <TableHead className="text-right">활성LOT합계</TableHead>
                <TableHead className="text-right">미추적수량</TableHead>
                <TableHead>판정</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(reconciliation.data ?? []).map((r) => (
                <TableRow key={`${r.material_id}-${r.warehouse_id}`} className={!r.consistent ? 'bg-danger-soft/40' : undefined}>
                  <TableCell>{r.material_code}</TableCell>
                  <TableCell>{r.material_name}</TableCell>
                  <TableCell>{r.warehouse_name}</TableCell>
                  <TableCell className="text-right">{r.inventory_qty}</TableCell>
                  <TableCell className="text-right">{r.active_lot_qty}</TableCell>
                  <TableCell className="text-right">{r.untracked_qty}</TableCell>
                  <TableCell>
                    <Badge variant={r.consistent ? 'success' : 'danger'}>{r.consistent ? '정상' : '⚠ 부정합'}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  )
}
