import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import type { Material, Customer, Vendor } from '@/lib/types'

export default function MdmPage() {
  const { hasRole } = useAuth()
  const canWrite = hasRole('관리자')
  const qc = useQueryClient()
  const [error, setError] = useState('')

  const materials = useQuery({ queryKey: ['materials'], queryFn: () => apiGet<Material[]>('/api/materials') })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => apiGet<Customer[]>('/api/customers') })
  const vendors = useQuery({ queryKey: ['vendors'], queryFn: () => apiGet<Vendor[]>('/api/vendors') })

  const createMaterial = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/materials', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['materials'] }),
  })
  const createCustomer = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/customers', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customers'] }),
  })
  const createVendor = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost('/api/vendors', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  })

  async function handleSubmit(
    e: FormEvent<HTMLFormElement>,
    mutation: { mutateAsync: (body: Record<string, unknown>) => Promise<unknown> },
  ) {
    e.preventDefault()
    setError('')
    const form = e.currentTarget
    const body = Object.fromEntries(new FormData(form))
    try {
      await mutation.mutateAsync(body)
      form.reset()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '등록 실패')
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text-primary">기준정보</h1>
      {error && <p className="text-xs text-danger">{error}</p>}

      <div className={canWrite ? 'grid grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]' : ''}>
        {canWrite && (
          <Card>
            <CardHeader>
              <CardTitle>품목 등록</CardTitle>
            </CardHeader>
            <form onSubmit={(e) => handleSubmit(e, createMaterial)} className="space-y-2">
              <Input name="code" placeholder="코드" required />
              <Input name="name" placeholder="품명" required />
              <Select name="material_type" defaultValue="FG">
                <option value="RM">원자재(RM)</option>
                <option value="SFG">반제품(SFG)</option>
                <option value="FG">완제품(FG)</option>
              </Select>
              <Input name="uom" placeholder="단위" defaultValue="EA" />
              <Button type="submit" className="w-full" disabled={createMaterial.isPending}>
                등록
              </Button>
            </form>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle>품목 목록</CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>품명</TableHead>
                <TableHead>유형</TableHead>
                <TableHead>단위</TableHead>
                <TableHead className="text-right">재발주점</TableHead>
                <TableHead className="text-right">목표재고</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(materials.data ?? []).map((m) => (
                <TableRow key={m.material_id}>
                  <TableCell>{m.code}</TableCell>
                  <TableCell>{m.name}</TableCell>
                  <TableCell>{m.material_type}</TableCell>
                  <TableCell>{m.uom}</TableCell>
                  <TableCell className="text-right">{m.reorder_point}</TableCell>
                  <TableCell className="text-right">{m.target_stock}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>

      <div className={canWrite ? 'grid grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]' : ''}>
        {canWrite && (
          <Card>
            <CardHeader>
              <CardTitle>고객 등록</CardTitle>
            </CardHeader>
            <form onSubmit={(e) => handleSubmit(e, createCustomer)} className="space-y-2">
              <Input name="name" placeholder="고객명" required />
              <Button type="submit" className="w-full" disabled={createCustomer.isPending}>
                등록
              </Button>
            </form>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle>고객 목록</CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>고객명</TableHead>
                <TableHead className="text-right">신용한도</TableHead>
                <TableHead>통화</TableHead>
                <TableHead>결제조건</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(customers.data ?? []).map((c) => (
                <TableRow key={c.customer_id}>
                  <TableCell>{c.code}</TableCell>
                  <TableCell>{c.name}</TableCell>
                  <TableCell className="text-right">{c.credit_limit.toLocaleString()}</TableCell>
                  <TableCell>{c.currency}</TableCell>
                  <TableCell>{c.payment_term}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>

      <div className={canWrite ? 'grid grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]' : ''}>
        {canWrite && (
          <Card>
            <CardHeader>
              <CardTitle>공급사 등록</CardTitle>
            </CardHeader>
            <form onSubmit={(e) => handleSubmit(e, createVendor)} className="space-y-2">
              <Input name="name" placeholder="공급사명" required />
              <Button type="submit" className="w-full" disabled={createVendor.isPending}>
                등록
              </Button>
            </form>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle>공급사 목록</CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>코드</TableHead>
                <TableHead>공급사명</TableHead>
                <TableHead className="text-right">리드타임(일)</TableHead>
                <TableHead>결제조건</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(vendors.data ?? []).map((v) => (
                <TableRow key={v.vendor_id}>
                  <TableCell>{v.code}</TableCell>
                  <TableCell>{v.name}</TableCell>
                  <TableCell className="text-right">{v.lead_time_days}</TableCell>
                  <TableCell>{v.payment_term}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    </div>
  )
}
