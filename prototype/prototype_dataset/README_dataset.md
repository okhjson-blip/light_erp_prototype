# AX ERP Prototype Dataset

대상 URL: `http://127.0.0.1:8000/`

## 구성 목적
전자부품 및 소형소비가전 제조/판매 회사의 AX 플랫폼 프로토타입에 바로 연결할 수 있는 샘플 데이터셋입니다.

## 파일별 행 수

| 파일 | 행 수 |
|---|---:|
| companies.csv | 4 |
| plants.csv | 5 |
| warehouses.csv | 8 |
| customers.csv | 6 |
| vendors.csv | 8 |
| materials.csv | 15 |
| bom_items.csv | 25 |
| demand_forecast.csv | 60 |
| sales_orders.csv | 216 |
| purchase_orders.csv | 264 |
| inventory_snapshot.csv | 45 |
| production_orders.csv | 180 |
| production_results.csv | 180 |
| quality_inspections.csv | 180 |
| shipments.csv | 124 |
| finance_summary.csv | 12 |
| kpi_monthly.csv | 12 |
| ai_recommendations.csv | 5 |

## 추천 화면 매핑

| 화면 | 사용 데이터 |
|---|---|
| CEO Dashboard | `kpi_monthly.csv`, `finance_summary.csv`, `ai_recommendations.csv` |
| SCM Control Tower | `demand_forecast.csv`, `inventory_snapshot.csv`, `purchase_orders.csv` |
| Production Control Tower | `production_orders.csv`, `production_results.csv` |
| Quality Dashboard | `quality_inspections.csv` |
| Warehouse Dashboard | `inventory_snapshot.csv`, `shipments.csv` |
| AI Copilot | `ai_recommendations.csv`, `kpi_monthly.csv` |

## FastAPI 연동 예시
```python
import pandas as pd
from fastapi import FastAPI

app = FastAPI()
DATA_DIR = 'data'

@app.get('/api/kpis/monthly')
def get_kpis():
    return pd.read_csv(f'{DATA_DIR}/kpi_monthly.csv').to_dict(orient='records')

@app.get('/api/ai/recommendations')
def get_ai_recommendations():
    return pd.read_csv(f'{DATA_DIR}/ai_recommendations.csv').to_dict(orient='records')
```