# Source map — business questions to source systems

This is the Class 4 artifact: it traces each business question down to the
information required, the source system that holds it, who owns that source, the
grain of the data, and the gaps we have to work around.

## Business questions → required information → sources

| Business question | Information required | Source system | Retrieval mode |
|---|---|---|---|
| Can we trust this month's trip data? | Every trip's timestamps, distance, amounts, locations | TLC Yellow Taxi trip records | File (Parquet over HTTP) + SQL |
| How long / fast is a typical trip? | Pickup & dropoff time, trip distance | TLC Yellow Taxi trip records | File + SQL |
| Where does demand concentrate? | Pickup location → borough/zone | TLC Yellow Taxi trip records + Taxi Zone lookup | File (CSV) + SQL |
| When does demand peak? | Pickup timestamp (hour of day) | TLC Yellow Taxi trip records | File + SQL |

## Source systems

| Source | Owner | Grain | Format | Notes / gaps |
|---|---|---|---|---|
| Yellow Taxi trip records | NYC Taxi & Limousine Commission (TLC) | **One row per completed trip** | Parquet, one file per month | Self-reported by vendors' meter systems; contains meter/GPS errors, stray out-of-month rows, and placeholder location IDs |
| Taxi Zone lookup | NYC TLC | **One row per LocationID** (265 rows) | CSV | IDs 1–263 are real zones; 264 = "Unknown", 265 = "N/A" |

## Known source gaps (feed the validation rules and limitations)

- **No trip identifier.** The trip records have no primary key, so exact
  duplicates cannot be distinguished from two genuinely similar trips. We treat
  rows as events and do not dedupe blindly.
- **Self-reported measures.** Distance, fare, and passenger count come from
  meters/drivers and include impossible values (zero distance, negative fare,
  0 or 9 passengers).
- **Timestamp leakage.** Monthly files include a small number of trips whose
  pickup falls in a different month/year; these are quarantined, not trusted.
- **Placeholder locations.** LocationIDs 264/265 mean the zone is unknown; we
  cannot map those to a borough.
- **No weather/traffic context.** Speed is explained here only structurally
  (borough, hour); external causes are out of scope.
