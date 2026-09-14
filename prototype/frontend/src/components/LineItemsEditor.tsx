import { Plus, Trash2 } from 'lucide-react'
import { Select } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import type { Material, LineItem } from '@/lib/types'

// SO/PR/PO 등록 폼에서 공통으로 쓰는 라인아이템(품목+수량[+단가]) 편집기 — 기존 static/index.html의
// addLineRow/collectLines를 React 상태 기반으로 재현.
interface Props {
  materials: Material[]
  lines: LineItem[]
  withPrice?: boolean
  onChange: (lines: LineItem[]) => void
}

export function LineItemsEditor({ materials, lines, withPrice, onChange }: Props) {
  function update(i: number, patch: Partial<LineItem>) {
    onChange(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }
  function add() {
    onChange([...lines, { material_id: materials[0]?.material_id ?? 0, qty: 1, ...(withPrice ? { price: 0 } : {}) }])
  }
  function remove(i: number) {
    onChange(lines.filter((_, idx) => idx !== i))
  }

  return (
    <div className="space-y-2">
      {lines.map((line, i) => (
        <div key={i} className="flex items-center gap-2">
          <Select
            className="flex-1"
            value={line.material_id}
            onChange={(e) => update(i, { material_id: Number(e.target.value) })}
          >
            {materials.map((m) => (
              <option key={m.material_id} value={m.material_id}>
                {m.name}
              </option>
            ))}
          </Select>
          <Input
            type="number"
            className="w-24"
            placeholder="수량"
            value={line.qty}
            onChange={(e) => update(i, { qty: Number(e.target.value) })}
          />
          {withPrice && (
            <Input
              type="number"
              className="w-28"
              placeholder="단가"
              value={line.price ?? 0}
              onChange={(e) => update(i, { price: Number(e.target.value) })}
            />
          )}
          <Button type="button" variant="ghost" size="icon" onClick={() => remove(i)} aria-label="라인 삭제">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={add}>
        <Plus className="h-4 w-4" /> 라인 추가
      </Button>
    </div>
  )
}
