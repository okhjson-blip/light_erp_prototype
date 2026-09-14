import { useState } from 'react'
import { Select } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import type { Warehouse, Plant } from '@/lib/types'

// 생산실적입력 행 액션 — 기존 static/index.html의 openResultPicker/confirmResultPick 패턴 재현.
// WarehousePicker와 달리 수량 입력값 + 시리얼 생성 체크박스가 추가로 필요해 별도 컴포넌트로 분리했다.
interface Props {
  warehouses: Warehouse[]
  plants: Plant[]
  preferredPlantId?: number | null
  onConfirm: (qty: number, warehouseId: number, generateSerials: boolean) => void
}

export function ProductionResultPicker({ warehouses, plants, preferredPlantId, onConfirm }: Props) {
  const [picking, setPicking] = useState(false)
  const [qty, setQty] = useState(10)
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [generateSerials, setGenerateSerials] = useState(false)

  const list = warehouses.filter((w) => w.warehouse_type === 'FG')
  const sorted =
    preferredPlantId != null
      ? [...list.filter((w) => w.plant_id === preferredPlantId), ...list.filter((w) => w.plant_id !== preferredPlantId)]
      : list

  function labelFor(w: Warehouse) {
    const plant = plants.find((p) => p.plant_id === w.plant_id)
    return (plant ? `${plant.name} · ` : '') + w.name
  }

  if (!picking) {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => {
          setPicking(true)
          setWarehouseId(sorted[0]?.warehouse_id ?? null)
        }}
      >
        실적입력
      </Button>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      <Input
        type="number"
        className="h-8 w-16 text-xs"
        value={qty}
        onChange={(e) => setQty(Number(e.target.value))}
      />
      <Select
        className="h-8 w-40 text-xs"
        value={warehouseId ?? ''}
        onChange={(e) => setWarehouseId(Number(e.target.value))}
      >
        {sorted.map((w) => (
          <option key={w.warehouse_id} value={w.warehouse_id}>
            {labelFor(w)}
          </option>
        ))}
      </Select>
      <label className="flex items-center gap-1 text-xs text-text-secondary">
        <input type="checkbox" checked={generateSerials} onChange={(e) => setGenerateSerials(e.target.checked)} />
        시리얼 생성
      </label>
      <Button
        type="button"
        size="sm"
        onClick={() => {
          if (warehouseId != null) onConfirm(qty, warehouseId, generateSerials)
          setPicking(false)
        }}
      >
        확인
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={() => setPicking(false)}>
        취소
      </Button>
    </div>
  )
}
