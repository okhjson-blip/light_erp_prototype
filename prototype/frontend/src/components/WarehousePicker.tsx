import { useState } from 'react'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import type { Warehouse, Plant } from '@/lib/types'

// 출하/입고처리 행 액션 — 기존 static/index.html의 openWarehousePicker/confirmPick/cancelPick 패턴을
// React 상태로 재현. 버튼을 누르면 인라인 드롭다운(공장명 포함)+확인/취소로 바뀐다.
interface Props {
  label: string
  warehouseType: string
  warehouses: Warehouse[]
  plants: Plant[]
  preferredPlantId?: number | null
  onConfirm: (warehouseId: number) => void
}

export function WarehousePicker({ label, warehouseType, warehouses, plants, preferredPlantId, onConfirm }: Props) {
  const [picking, setPicking] = useState(false)
  const [warehouseId, setWarehouseId] = useState<number | null>(null)

  const list = warehouses.filter((w) => w.warehouse_type === warehouseType)
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
        {label}
      </Button>
    )
  }

  return (
    <div className="flex items-center gap-1">
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
      <Button
        type="button"
        size="sm"
        onClick={() => {
          if (warehouseId != null) onConfirm(warehouseId)
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
