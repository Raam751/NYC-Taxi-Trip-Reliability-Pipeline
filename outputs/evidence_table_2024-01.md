# Evidence table - Yellow Taxi 2024-01

**Project KPI:** Fleet efficiency & data trust.

- Raw trips ingested: **2,964,624**
- Validated trips used for metrics: **2,686,243**

| Metric | Value | Unit | Supports decision |
|---|---:|---|---|
| M1 Valid trip rate | 90.61 | % | Data trust: is this month usable for decisions? |
| M2 Median trip duration | 11.62 | min | Baseline trip length for planning |
| M3 Median trip speed | 9.63 | mph | Efficiency; low speed signals congestion |
| M4 P90 trip duration | 28.78 | min | Reliability tail: how long are the slow trips |
| M5 Peak-hour trip share | 38.04 | % | Demand concentration for staffing/supply |

See `data_quality_report_2024-01.csv` for per-rule rejections and `trips_by_borough_2024-01.csv` for the geographic breakdown.
