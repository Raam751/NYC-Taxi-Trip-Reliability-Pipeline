"""Streamlit dashboard - a read-only VIEW over the pipeline's trusted outputs.

Important design choice: this app never recomputes metrics or touches raw data.
It only reads the files the pipeline already produced in outputs/. The pipeline
stays the single source of truth; the dashboard is just a lens on it. That keeps
the "trustworthy path" intact - what you see here is exactly what was validated.

Run:
    .venv/bin/streamlit run app.py
"""
from __future__ import annotations

import glob
import os
import re

import altair as alt
import pandas as pd
import streamlit as st

OUTPUTS = os.path.join(os.path.dirname(__file__), "outputs")

st.set_page_config(page_title="NYC Taxi Trip Reliability", page_icon="🚕", layout="wide")


def available_periods() -> list[str]:
    """Discover periods from the metric files the pipeline has written."""
    periods = []
    for path in glob.glob(os.path.join(OUTPUTS, "metrics_*.csv")):
        m = re.search(r"metrics_(\d{4}-\d{2})\.csv$", os.path.basename(path))
        if m:
            periods.append(m.group(1))
    return sorted(periods, reverse=True)


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(OUTPUTS, name))


# --------------------------------------------------------------------------- #
# Header + period picker
# --------------------------------------------------------------------------- #
st.title("🚕 NYC Yellow Taxi — Trip Reliability")
st.caption(
    "A read-only view of pipeline outputs. **KPI: fleet efficiency & data trust** — "
    "can we rely on this month's data, and where/when is the fleet slow?"
)

periods = available_periods()
if not periods:
    st.error(
        "No pipeline outputs found. Run the pipeline first:\n\n"
        "`.venv/bin/python -m src.pipeline --period 2024-01`"
    )
    st.stop()

period = st.sidebar.selectbox("Period", periods)
st.sidebar.markdown(
    "This dashboard reads `outputs/` only. To refresh the numbers, rerun the "
    "pipeline for a period, then reload this page."
)

metrics = load_csv(f"metrics_{period}.csv")
dq = load_csv(f"data_quality_report_{period}.csv")
borough = load_csv(f"trips_by_borough_{period}.csv")

# --------------------------------------------------------------------------- #
# Row 1 - the five KPI metrics as headline cards
# --------------------------------------------------------------------------- #
st.subheader(f"Headline metrics — {period}")
cols = st.columns(len(metrics))
for col, (_, row) in zip(cols, metrics.iterrows()):
    col.metric(
        label=f"{row['metric_id']} · {row['metric_name']}",
        value=f"{row['value']} {row['unit']}",
        help=row["supports_decision"],
    )

# Data-trust callout driven by the valid-trip rate (M1).
valid_rate = float(metrics.loc[metrics["metric_id"] == "M1", "value"].iloc[0])
if valid_rate >= 90:
    st.success(f"Data trust: {valid_rate:.1f}% of raw trips passed all rules — usable.")
elif valid_rate >= 80:
    st.warning(f"Data trust: {valid_rate:.1f}% valid — usable, but inspect rejections.")
else:
    st.error(f"Data trust: only {valid_rate:.1f}% valid — investigate before deciding.")

left, right = st.columns(2)

# --------------------------------------------------------------------------- #
# Left - data quality: why rows were rejected
# --------------------------------------------------------------------------- #
with left:
    st.subheader("Why rows were quarantined")
    rules = dq[~dq["rule_id"].str.startswith("_SUMMARY")].copy()
    rules = rules[rules["rows_failed"] > 0].sort_values("rows_failed", ascending=False)
    chart = (
        alt.Chart(rules)
        .mark_bar(color="#C87917")
        .encode(
            x=alt.X("rows_failed:Q", title="rows failed"),
            y=alt.Y("rule_id:N", sort="-x", title=None),
            tooltip=["rule_id", "description", "rows_failed", "pct_of_total"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption("Rejected rows are quarantined with a reason, never silently dropped.")

# --------------------------------------------------------------------------- #
# Right - the judgement call: speed hides two regimes by borough
# --------------------------------------------------------------------------- #
with right:
    st.subheader("The judgement call: speed varies by borough")
    b = borough.copy()
    scatter = (
        alt.Chart(b)
        .mark_circle()
        .encode(
            x=alt.X("median_speed_mph:Q", title="median speed (mph)"),
            y=alt.Y("median_duration_min:Q", title="median duration (min)"),
            size=alt.Size("trips:Q", title="trips", scale=alt.Scale(range=[60, 1600])),
            color=alt.Color("pickup_borough:N", title="pickup borough"),
            tooltip=["pickup_borough", "trips", "median_duration_min", "median_speed_mph"],
        )
        .properties(height=320)
    )
    st.altair_chart(scatter, use_container_width=True)
    st.caption(
        "A single citywide speed conflates slow Manhattan trips with fast Queens "
        "airport runs — so the headline is always paired with this breakdown."
    )

# --------------------------------------------------------------------------- #
# Detail tables
# --------------------------------------------------------------------------- #
with st.expander("Metric definitions"):
    st.dataframe(
        metrics[["metric_id", "metric_name", "value", "unit", "definition",
                 "supports_decision"]],
        hide_index=True,
        use_container_width=True,
    )
with st.expander("Trips by pickup borough"):
    st.dataframe(borough, hide_index=True, use_container_width=True)
with st.expander("Full data-quality report"):
    st.dataframe(dq, hide_index=True, use_container_width=True)
