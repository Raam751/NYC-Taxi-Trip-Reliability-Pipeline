# Evidence table - Yellow Taxi 2024-02

**Project KPI:** Fleet efficiency & data trust.

- Raw trips ingested: **3,007,526**
- Validated trips used for metrics: **2,685,058**

| Metric | Value | Unit | Supports decision |
|---|---:|---|---|
| M1 Valid trip rate | 89.28 | % | Data trust: is this month usable for decisions? |
| M2 Median trip duration | 11.92 | min | Baseline trip length for planning |
| M3 Median trip speed | 9.43 | mph | Efficiency; low speed signals congestion |
| M4 P90 trip duration | 29.45 | min | Reliability tail: how long are the slow trips |
| M5 Peak-hour trip share | 38.24 | % | Demand concentration for staffing/supply |

See `data_quality_report_2024-02.csv` for per-rule rejections and `trips_by_borough_2024-02.csv` for the geographic breakdown.
