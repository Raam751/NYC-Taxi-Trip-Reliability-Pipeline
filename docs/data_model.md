# Workflow & data model

## The trip as a workflow event (Class 7)

Each taxi trip is one business event with a simple lifecycle. Operations cares
about *where* and *when* it starts, and the *outcome* measures it produces.

```mermaid
stateDiagram-v2
    [*] --> InService: pickup at PULocationID (pickup_ts)
    InService --> Completed: dropoff at DOLocationID (dropoff_ts)
    Completed --> [*]

    note right of InService
        Outcome measures derived on completion:
        duration_min = dropoff_ts - pickup_ts
        speed_mph    = trip_distance / duration
    end note
```

A raw trip is only admitted to the model after it passes validation; otherwise
it is routed to quarantine with a reason (see the data-quality report).

```mermaid
flowchart LR
    RAW[raw trip row] --> V{passes all<br/>business rules?}
    V -- yes --> FACT[fact_trips]
    V -- no --> Q[quarantine + reject_reason]
```

## Relational model (star schema)

```mermaid
erDiagram
    DIM_ZONE ||--o{ FACT_TRIPS : "pickup zone"
    FACT_TRIPS {
        int    VendorID
        ts     pickup_ts
        ts     dropoff_ts
        int    PULocationID
        int    DOLocationID
        string pickup_borough
        string pickup_zone
        int    passenger_count
        double trip_distance
        double fare_amount
        double total_amount
        double duration_min
        double speed_mph
        int    pickup_hour
        bool   is_peak
    }
    DIM_ZONE {
        int    LocationID
        string Borough
        string Zone
        string service_zone
    }
```

- **Grain of `fact_trips`:** one validated trip (event).
- **Join:** `fact_trips.PULocationID = dim_zone.LocationID` (pickup location),
  so demand and efficiency can be read by borough — the grain operations plan
  around.
- **Derived fields:** `duration_min`, `speed_mph`, `pickup_hour`, `is_peak`
  are computed once during validation/modelling and reused by all metrics.

## Metrics linked to the KPI

**KPI: Fleet efficiency & data trust.**

| Metric | Built from | Decision it supports |
|---|---|---|
| M1 Valid trip rate | validation summary | Is this month usable at all? |
| M2 Median trip duration | `fact_trips.duration_min` | Baseline trip length |
| M3 Median trip speed | `fact_trips.speed_mph` | Congestion / efficiency |
| M4 P90 trip duration | `fact_trips.duration_min` | Reliability tail |
| M5 Peak-hour trip share | `fact_trips.is_peak` | Staffing / supply timing |
