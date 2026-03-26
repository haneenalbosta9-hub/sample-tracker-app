import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# Page configuration
st.set_page_config(
    page_title="Sample Tracker",
    page_icon="📊",
    layout="wide"
)

st.title("📋 Laboratory Sample Tracker")
st.markdown("---")

@st.cache_data(ttl=300)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1TuoR9NWHk_AEzwHJZH9G609FhEuYLs3OG80ImjDJfR8/edit?usp=sharing"
        df = pd.read_csv(sheet_url)
        df.columns = df.columns.str.strip()
        
        if 'Received Date' in df.columns:
            df['Received Date'] = pd.to_datetime(df['Received Date'], errors='coerce')
        if 'Test Performing Date' in df.columns:
            df['Test Performing Date'] = pd.to_datetime(df['Test Performing Date'], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Please make sure your Google Sheet is publicly accessible")
        return pd.DataFrame()

def calculate_expected_date(test_type, performing_date):
    if pd.isna(performing_date) or performing_date is None:
        return None
    
    performing_date = pd.to_datetime(performing_date)
    test_type_lower = str(test_type).lower()
    
    if 'bioburden' in test_type_lower or 'environmental' in test_type_lower:
        return performing_date + timedelta(days=5)
    elif 'sterility' in test_type_lower:
        return performing_date + timedelta(days=14)
    elif 'endotoxin' in test_type_lower:
        return performing_date
    return None

st.header("🔍 Search Your Sample")

col1, col2 = st.columns(2)
with col1:
    search_by_lab = st.text_input("Search by Sample ID (Lab's):", placeholder="Enter Sample ID...")
with col2:
    search_by_batch = st.text_input("Search by Sample Batch No (Customer's):", placeholder="Enter Batch Number...")

df = load_data()

if not df.empty:
    with st.expander("📊 Database Info"):
        st.write(f"Total records: {len(df)}")
    
    if search_by_lab or search_by_batch:
        if search_by_lab and 'Sample ID' in df.columns:
            result = df[df['Sample ID'].astype(str).str.contains(search_by_lab, case=False, na=False)]
        elif search_by_batch and 'Sample Batch No.' in df.columns:
            result = df[df['Sample Batch No.'].astype(str).str.contains(search_by_batch, case=False, na=False)]
        else:
            result = pd.DataFrame()
        
        if not result.empty:
            for _, row in result.iterrows():
                st.markdown("### 📊 Sample Details")
                st.markdown("---")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**🔬 Basic Information**")
                    st.write(f"**Sample ID:** {row.get('Sample ID', 'N/A')}")
                    st.write(f"**Sample Batch No.:** {row.get('Sample Batch No.', 'N/A')}")
                    st.write(f"**Unit No.:** {row.get('Unit No.', 'N/A')}")
                    st.write(f"**Sample Type:** {row.get('Sample Type', 'N/A')}")
                    st.write(f"**Product Name:** {row.get('Product Name', 'N/A')}")
                
                with col2:
                    st.markdown("**📅 Dates & Status**")
                    received = row.get('Received Date', 'N/A')
                    if pd.notna(received):
                        received = received.strftime('%Y-%m-%d')
                    st.write(f"**Received Date:** {received}")
                    
                    status = str(row.get('Test Status', 'N/A'))
                    if status == 'Released':
                        st.success(f"**Test Status:** ✅ {status}")
                    elif status == 'In Process':
                        st.info(f"**Test Status:** 🔄 {status}")
                    elif status == 'On Hold':
                        st.warning(f"**Test Status:** ⏸️ {status}")
                    else:
                        st.write(f"**Test Status:** {status}")
                    
                    st.write(f"**Type of Test:** {row.get('Type of Test', 'N/A')}")
                    
                    performing = row.get('Test Performing Date', 'N/A')
                    if pd.notna(performing):
                        performing = performing.strftime('%Y-%m-%d')
                        st.write(f"**Test Performing Date:** {performing}")
                    else:
                        st.write(f"**Test Performing Date:** Not Started")
                
                with col3:
                    st.markdown("**👥 Customer Information**")
                    st.write(f"**Customer Name:** {row.get('Customer Name', 'N/A')}")
                    st.write(f"**Customer Name (AR):** {row.get('Customer Name (AR)', 'N/A')}")
                    st.write(f"**Customer Name (EN):** {row.get('Customer Name (EN)', 'N/A')}")
                    st.write(f"**Reference No.:** {row.get('Reference No.', 'N/A')}")
                
                st.markdown("---")
                performing_date = row.get('Test Performing Date')
                test_type = row.get('Type of Test', '')
                
                if pd.notna(performing_date) and performing_date:
                    expected_date = calculate_expected_date(test_type, performing_date)
                    if expected_date:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(f"**Test Started:** {performing_date.strftime('%Y-%m-%d')}")
                            st.write(f"**Expected Result Date:** {expected_date.strftime('%Y-%m-%d')}")
                        with col_b:
                            if datetime.now() > expected_date:
                                st.success("✅ **Status:** Results released - pending report")
                            else:
                                days_left = (expected_date - datetime.now()).days
                                st.info(f"⏳ **Status:** In progress - {days_left} days until expected results")
                else:
                    st.info("📌 Test has not been started yet")
                
                st.markdown("---")
        else:
            st.error("❌ No samples found matching your search criteria.")
    
    st.markdown("---")
    st.header("🌿 Environmental Tests")
    
    if 'Type of Test' in df.columns:
        env_tests = df[df['Type of Test'].astype(str).str.lower().str.contains('environmental', na=False)]
        
        if not env_tests.empty and 'Received Date' in env_tests.columns:
            env_tests['Received Date'] = pd.to_datetime(env_tests['Received Date'], errors='coerce')
            env_tests['Month Year'] = env_tests['Received Date'].dt.strftime('%B %Y')
            available_months = sorted(env_tests['Month Year'].dropna().unique())
            
            if available_months:
                selected_month = st.selectbox("Select Month to View Environmental Tests", available_months)
                
                if selected_month:
                    month_data = env_tests[env_tests['Month Year'] == selected_month]
                    st.subheader(f"📊 Environmental Tests - {selected_month}")
                    st.write(f"**Found {len(month_data)} test(s)**")
                    
                    if not month_data.empty:
                        display_columns = ['Sample ID', 'Sample Batch No.', 'Received Date', 'Test Status', 'Unit No.', 'Product Name']
                        available_display = [col for col in display_columns if col in month_data.columns]
                        display_df = month_data[available_display].copy()
                        if 'Received Date' in display_df.columns:
                            display_df['Received Date'] = display_df['Received Date'].dt.strftime('%Y-%m-%d')
                        st.dataframe(display_df, use_container_width=True)

st.markdown("---")
st.caption(f"🔄 Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
