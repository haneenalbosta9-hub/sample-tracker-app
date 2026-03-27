import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sample Tracker",
    page_icon="🔬",
    layout="wide"
)

# ── Constants ─────────────────────────────────────────────────────────────────
SPREADSHEET_ID = "1EXiXsOQ0VsfIbZlUpN3r6g0-aRNUUEKZDVZHh_xZnEY"
SHEET_SAMPLES  = "Samples"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
COLUMNS = [
    "Received Date", "Sample ID", "Unit No.", "Sample Type", "Sample Batch No.",
    "Customer Name", "Reference No.", "Type of Test",
    "Test Performing Date", "Test Status", "Product Name",
    "Customer Name (AR)", "Customer Name (EN)",
]

# Test durations (days until expected result)
TEST_DURATIONS = {
    "bioburden":     5,
    "environmental": 5,
    "sterility":     14,
    "endotoxin":     0,   # same-day result
}

# ── Google Sheets loader ───────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    """
    Reads the Samples sheet via gspread using the service-account credentials
    stored in .streamlit/secrets.toml — same approach as the main lab app.
    Uses FORMATTED_VALUE so Google Sheets returns display strings, not date
    serial integers.
    """
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc   = gspread.authorize(creds)
        ws   = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_SAMPLES)
        records = ws.get_all_records(value_render_option="FORMATTED_VALUE")

        if not records:
            return pd.DataFrame(columns=COLUMNS)

        df = pd.DataFrame(records)
        # Ensure all expected columns exist
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""

        # ── Robust date parsing (handles YYYY-MM-DD, DD/MM/YYYY, M/D/YYYY) ──
        def _parse_dates(series: pd.Series) -> pd.Series:
            parsed = pd.to_datetime(series, errors="coerce",
                                    dayfirst=False, format="%Y-%m-%d")
            leftover = parsed.isna() & series.astype(str).str.strip().ne("")
            if leftover.any():
                parsed[leftover] = pd.to_datetime(
                    series[leftover], errors="coerce", dayfirst=True)
            return parsed

        df["Received Date"]      = _parse_dates(df["Received Date"])
        df["Test Performing Date"] = _parse_dates(df["Test Performing Date"])
        df["Unit No."] = pd.to_numeric(df["Unit No."], errors="coerce").fillna(1).astype(int)

        return df

    except Exception as e:
        st.error(f"❌ Error loading data from Google Sheets: {e}")
        return pd.DataFrame(columns=COLUMNS)


# ── Helpers ───────────────────────────────────────────────────────────────────
def expected_result_date(test_type: str, performing_date) -> datetime | None:
    if pd.isna(performing_date):
        return None
    tt = str(test_type).lower()
    for key, days in TEST_DURATIONS.items():
        if key in tt:
            return pd.Timestamp(performing_date) + timedelta(days=days)
    return None


def fmt_date(val) -> str:
    if pd.isna(val) or val == "" or val is None:
        return "—"
    try:
        return pd.Timestamp(val).strftime("%d/%m/%Y")
    except Exception:
        return str(val)


def status_badge(status: str):
    s = str(status).strip()
    if s == "Released":
        st.success(f"✅  {s}")
    elif s == "In Progress":
        st.info(f"🔄  {s}")
    elif s == "On Hold":
        st.warning(f"⏸️  {s}")
    else:
        st.write(f"**Status:** {s or '—'}")


def show_sample_card(row: pd.Series, idx: int):
    """Renders one sample as an expandable card."""
    sample_id  = row.get("Sample ID", "")
    unit_no    = row.get("Unit No.", "")
    test_type  = str(row.get("Type of Test", ""))
    status     = str(row.get("Test Status", ""))
    performing = row.get("Test Performing Date")
    expected   = expected_result_date(test_type, performing)
    now        = datetime.now()

    label = f"🔬  {sample_id}  —  Unit {unit_no}  |  {test_type}  |  {status}"
    with st.expander(label, expanded=(idx == 0)):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("**🔬 Sample Info**")
            st.write(f"**Sample ID:** {sample_id or '—'}")
            st.write(f"**Unit No.:** {unit_no or '—'}")
            st.write(f"**Sample Type:** {row.get('Sample Type', '—') or '—'}")
            st.write(f"**Sample Batch No.:** {row.get('Sample Batch No.', '—') or '—'}")
            st.write(f"**Product Name:** {row.get('Product Name', '—') or '—'}")
            st.write(f"**Reference No.:** {row.get('Reference No.', '—') or '—'}")

        with c2:
            st.markdown("**📅 Dates**")
            st.write(f"**Received:** {fmt_date(row.get('Received Date'))}")
            st.write(f"**Test Started:** {fmt_date(performing)}")
            st.write(f"**Expected Result:** {fmt_date(expected)}")
            st.markdown("**⚗️ Test**")
            st.write(f"**Type:** {test_type or '—'}")
            status_badge(status)

        with c3:
            st.markdown("**👤 Customer**")
            st.write(f"**Name:** {row.get('Customer Name', '—') or '—'}")
            st.write(f"**Arabic:** {row.get('Customer Name (AR)', '—') or '—'}")
            st.write(f"**English:** {row.get('Customer Name (EN)', '—') or '—'}")

            # Timeline indicator
            if expected is not None and pd.notna(performing):
                st.markdown("**⏱️ Timeline**")
                if now >= expected:
                    st.success("Results ready — pending report")
                else:
                    days_left = (expected - now).days + 1
                    pct = max(0, min(100, int(
                        (now - pd.Timestamp(performing)).days /
                        max((expected - pd.Timestamp(performing)).days, 1) * 100
                    )))
                    st.progress(pct / 100)
                    st.info(f"⏳ {days_left} day(s) remaining")
            elif pd.isna(performing):
                st.markdown("**⏱️ Timeline**")
                st.warning("Test not started yet")


# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("🔬 Laboratory Sample Tracker")
st.markdown("---")

df = load_data()

if df.empty:
    st.warning("⚠️ No data loaded. Check your Google Sheets connection.")
    st.stop()

# Show quick stats
total   = len(df)
on_hold = (df["Test Status"] == "On Hold").sum()
in_prog = (df["Test Status"] == "In Progress").sum()
released = (df["Test Status"] == "Released").sum()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Samples", total)
m2.metric("On Hold",       on_hold)
m3.metric("In Progress",   in_prog)
m4.metric("Released",      released)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
#  TAB 1 — Bioburden / Endotoxin / Sterility  (search by ID or Batch)
#  TAB 2 — Environmental (by month)
# ═══════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["🔬 Bioburden / Endotoxin / Sterility", "🌿 Environmental"])

# ── TAB 1 ──────────────────────────────────────────────────────
with tab1:
    st.subheader("Search Samples")

    col_a, col_b = st.columns(2)
    with col_a:
        search_id    = st.text_input("Sample ID", placeholder="e.g. MIC-0042-03-2026")
    with col_b:
        search_batch = st.text_input("Batch No.", placeholder="e.g. B001")

    # Filter to non-environmental tests
    NON_ENV = ["Bioburden", "Endotoxin", "Sterility",
               "Total Coliforms & E. Coli", "Pseudomonas aeruginosa",
               "Total heterotrophic bacterial count", "Legionella",
               "Fungi", "Other (Not Listed)"]

    df_non_env = df[~df["Type of Test"].astype(str).str.lower().str.contains("environmental", na=False)]

    if search_id or search_batch:
        if search_id:
            result = df_non_env[
                df_non_env["Sample ID"].astype(str).str.contains(
                    search_id.strip(), case=False, na=False)]
        else:
            result = df_non_env[
                df_non_env["Sample Batch No."].astype(str).str.contains(
                    search_batch.strip(), case=False, na=False)]

        if result.empty:
            st.error("❌ No samples found. Check the ID or Batch No.")
        else:
            st.success(f"✅ Found {len(result)} record(s)")
            for i, (_, row) in enumerate(result.iterrows()):
                show_sample_card(row, i)
    else:
        st.info("👆 Enter a Sample ID or Batch No. above to search.")

        # Show recent samples as a quick reference table
        st.markdown("#### Recent Samples (latest 20)")
        recent = df_non_env.sort_values("Received Date", ascending=False).head(20)
        disp = recent[["Sample ID", "Unit No.", "Received Date",
                        "Sample Batch No.", "Customer Name",
                        "Type of Test", "Test Status"]].copy()
        disp["Received Date"] = disp["Received Date"].apply(fmt_date)
        st.dataframe(disp, use_container_width=True, hide_index=True)


# ── TAB 2 ──────────────────────────────────────────────────────
with tab2:
    st.subheader("Environmental Tests by Month")

    df_env = df[df["Type of Test"].astype(str).str.lower().str.contains("environmental", na=False)].copy()

    if df_env.empty:
        st.info("No Environmental test records found.")
        st.stop()

    # Build month list from Received Date
    df_env["_month_label"] = df_env["Received Date"].dt.strftime("%B %Y")
    months = (
        df_env.dropna(subset=["Received Date"])
        ["_month_label"]
        .unique()
    )
    # Sort chronologically
    months_sorted = sorted(
        months,
        key=lambda m: datetime.strptime(m, "%B %Y"),
        reverse=True
    )

    if not months_sorted:
        st.warning("No dated Environmental records found.")
        st.stop()

    selected_month = st.selectbox("Select Month", months_sorted)
    month_df = df_env[df_env["_month_label"] == selected_month].copy()

    st.markdown(f"### 📅 {selected_month} — {len(month_df)} Environmental Sample(s)")

    # Summary metrics for the month
    e1, e2, e3 = st.columns(3)
    e1.metric("Total",       len(month_df))
    e2.metric("In Progress", (month_df["Test Status"] == "In Progress").sum())
    e3.metric("Released",    (month_df["Test Status"] == "Released").sum())

    st.markdown("---")

    # Full detail table
    show_cols = ["Sample ID", "Unit No.", "Product Name", "Received Date",
                 "Test Performing Date", "Test Status",
                 "Customer Name", "Sample Batch No."]
    avail_cols = [c for c in show_cols if c in month_df.columns]
    disp_env = month_df[avail_cols].copy()
    disp_env["Received Date"]       = disp_env["Received Date"].apply(fmt_date)
    disp_env["Test Performing Date"] = disp_env["Test Performing Date"].apply(fmt_date)
    st.dataframe(disp_env, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Sample Details")
    for i, (_, row) in enumerate(month_df.iterrows()):
        show_sample_card(row, i)

st.markdown("---")
st.caption(f"🔄 Data refreshes every 60 s  ·  Last loaded: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
