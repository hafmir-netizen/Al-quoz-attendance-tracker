import streamlit as st
import pandas as pd

st.set_page_config(page_title="Attendance Dashboard", layout="wide")
st.title("Rider Attendance Dashboard")

# Map of recognized status text -> normalized code
STATUS_MAP = {
    "P": "P", "PRESENT": "P",
    "A": "A", "ABSENT": "A",
    "WO": "WO", "WEEKOFF": "WO", "WEEK OFF": "WO", "WEEK-OFF": "WO",
}


def normalize_status(value):
    """Turn a cell value into 'P', 'A', 'WO', or None if unrecognized/blank."""
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    return STATUS_MAP.get(text)


def detect_status_columns(df, min_match_ratio=0.6):
    """A column is treated as a status column if most of its non-blank
    values look like P / A / WO."""
    status_cols = []
    for col in df.columns:
        series = df[col]
        non_blank = series.dropna()
        if len(non_blank) == 0:
            continue
        recognized = non_blank.apply(lambda v: normalize_status(v) is not None)
        if recognized.mean() >= min_match_ratio:
            status_cols.append(col)
    return status_cols


uploaded_file = st.file_uploader("Upload the attendance Excel file", type=["xlsx", "xls"])

if uploaded_file is None:
    st.info("Upload an Excel file to get started.")
    st.stop()

try:
    excel_file = pd.ExcelFile(uploaded_file)
except Exception as e:
    st.error(f"Could not read this file as Excel: {e}")
    st.stop()

sheet_name = st.selectbox("Which sheet has the attendance data?", excel_file.sheet_names)

df = excel_file.parse(sheet_name)

st.subheader("Preview")
st.dataframe(df.head(10), use_container_width=True)

detected_status_cols = detect_status_columns(df)

st.subheader("1. Confirm the daily status columns")
st.caption("These are the columns that contain P / A / WO for each day. Auto-detected below — adjust if anything looks wrong.")
status_cols = st.multiselect(
    "Status columns (one per day)",
    options=list(df.columns),
    default=detected_status_cols,
)

remaining_cols = [c for c in df.columns if c not in status_cols]

st.subheader("2. Pick the rider identifier column")
st.caption("This is the column used to label each rider in the results (e.g. Name or Employee ID).")
id_col = st.selectbox("Rider identifier column", options=remaining_cols)

if not status_cols:
    st.warning("No status columns selected yet — pick at least one above to see results.")
    st.stop()

# --- Calculate attendance ---
present_counts = []
absent_counts = []
for _, row in df.iterrows():
    p = 0
    a = 0
    for col in status_cols:
        status = normalize_status(row[col])
        if status == "P":
            p += 1
        elif status == "A":
            a += 1
        # WO and unrecognized values are ignored
    present_counts.append(p)
    absent_counts.append(a)

result = pd.DataFrame({
    "Rider": df[id_col],
    "Present": present_counts,
    "Absent": absent_counts,
})
result["Days Counted"] = result["Present"] + result["Absent"]
result["Attendance %"] = result.apply(
    lambda r: round(100 * r["Present"] / r["Days Counted"], 1) if r["Days Counted"] > 0 else None,
    axis=1,
)

st.subheader("3. Attendance results")
st.caption("Week-offs and blank/unrecognized cells are excluded from the percentage calculation.")
result_sorted = result.sort_values("Attendance %", ascending=False, na_position="last")
st.dataframe(result_sorted, use_container_width=True)

csv = result_sorted.to_csv(index=False).encode("utf-8")
st.download_button("Download results as CSV", data=csv, file_name="attendance_results.csv", mime="text/csv")
