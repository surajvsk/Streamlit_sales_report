import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="Sales Report Dashboard", layout="wide", initial_sidebar_state="expanded")

# ----------------------------
# Helper: generate sample JSON data
# ----------------------------
@st.cache_data
def generate_sample_data(n_days=180, n_records=1200, seed=42):
    np.random.seed(seed)
    start_date = datetime.today() - timedelta(days=n_days)
    products = ["Alpha", "Beta", "Gamma", "Delta"]
    regions = ["North", "South", "East", "West"]
    sales_reps = ["Asha", "Ravi", "Sunil", "Meera", "Kavita"]

    rows = []
    for i in range(n_records):
        order_date = start_date + timedelta(days=int(np.random.rand() * n_days))
        product = np.random.choice(products, p=[0.3, 0.25, 0.25, 0.2])
        region = np.random.choice(regions)
        rep = np.random.choice(sales_reps)
        qty = int(np.random.poisson(3) + 1)
        price = float(np.round(np.random.uniform(50, 500) * (1 + (products.index(product) * 0.1)), 2))
        amount = float(np.round(qty * price, 2))
        order_id = f"ORD{100000 + i}"

        rows.append({
            "order_id": order_id,
            "order_date": order_date.strftime("%Y-%m-%d"),
            "product": product,
            "region": region,
            "sales_rep": rep,
            "quantity": qty,
            "unit_price": price,
            "amount": amount
        })

    return rows

# Write sample JSON file if it doesn't exist
SAMPLE_JSON = "sales_report.json"
if not st.session_state.get("data_loaded"):
    try:
        with open(SAMPLE_JSON, "r") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raw = generate_sample_data()
        with open(SAMPLE_JSON, "w") as f:
            json.dump(raw, f, indent=2)
    st.session_state["raw_json"] = raw
    st.session_state["data_loaded"] = True

# Load into DataFrame
@st.cache_data
def load_df(raw_json):
    df = pd.DataFrame(raw_json)
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df

df = load_df(st.session_state["raw_json"])

# ----------------------------
# Sidebar filters
# ----------------------------
st.sidebar.header("Filters")
min_date = df["order_date"].min().date()
max_date = df["order_date"].max().date()

date_range = st.sidebar.date_input("Order date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = map(pd.to_datetime, date_range)
else:
    start_d = pd.to_datetime(min_date)
    end_d = pd.to_datetime(max_date)

regions = st.sidebar.multiselect("Region", options=sorted(df["region"].unique()), default=sorted(df["region"].unique()))
products = st.sidebar.multiselect("Product", options=sorted(df["product"].unique()), default=sorted(df["product"].unique()))
reps = st.sidebar.multiselect("Sales rep", options=sorted(df["sales_rep"].unique()), default=sorted(df["sales_rep"].unique()))

min_amount, max_amount = float(df["amount"].min()), float(df["amount"].max())
amount_range = st.sidebar.slider("Amount range", min_value=0.0, max_value=max_amount, value=(min_amount, max_amount))

# Quick KPI toggles
show_raw_json = st.sidebar.checkbox("Show raw JSON", value=False)

# ----------------------------
# Filtering Data
# ----------------------------
filtered = df[
    (df["order_date"] >= start_d) &
    (df["order_date"] <= end_d) &
    (df["region"].isin(regions)) &
    (df["product"].isin(products)) &
    (df["sales_rep"].isin(reps)) &
    (df["amount"] >= amount_range[0]) &
    (df["amount"] <= amount_range[1])
]

# ----------------------------
# Top-level metrics
# ----------------------------
total_sales = filtered["amount"].sum()
orders = filtered.shape[0]
avg_order = filtered["amount"].mean() if orders else 0

col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1])
col1.metric("Total Sales", f"₹ {total_sales:,.2f}", delta=None)
col2.metric("Orders", f"{orders}")
col3.metric("Avg Order Value", f"₹ {avg_order:,.2f}")
col4.metric("Date Range", f"{start_d.date()} → {end_d.date()}")

st.markdown("---")

# ----------------------------
# Charts layout (creative UI)
# ----------------------------
left, middle, right = st.columns([1.2, 1, 1])

# Pie chart: sales by product
with left:
    st.subheader("Sales by Product")
    prod_agg = filtered.groupby("product")["amount"].sum().reset_index().sort_values("amount", ascending=False)
    if prod_agg.empty:
        st.info("No data for selected filters")
    else:
        fig_pie = px.pie(prod_agg, names="product", values="amount", title="Share by Product", hole=0.35)
        st.plotly_chart(fig_pie, use_container_width=True)

# Bar chart: sales by region
with middle:
    st.subheader("Sales by Region")
    reg_agg = filtered.groupby("region")["amount"].sum().reset_index().sort_values("amount", ascending=False)
    fig_bar = px.bar(reg_agg, x="region", y="amount", title="Sales by Region", text_auto=True)
    st.plotly_chart(fig_bar, use_container_width=True)

# Time series: sales over time
with right:
    st.subheader("Sales Over Time")
    ts = filtered.set_index("order_date").resample("W")["amount"].sum().reset_index()
    if ts.empty:
        st.info("No time-series data")
    else:
        fig_line = px.line(ts, x="order_date", y="amount", title="Weekly Sales Trend", markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

st.markdown("---")

# ----------------------------
# Additional visualisations
# ----------------------------
st.subheader("Breakdowns & Details")

colA, colB = st.columns(2)
with colA:
    st.markdown("**Top 10 Orders**")
    st.dataframe(filtered.sort_values("amount", ascending=False).head(10)[["order_id","order_date","product","region","sales_rep","quantity","amount"]])

with colB:
    st.markdown("**Quantity distribution**")
    if not filtered.empty:
        fig_hist = px.histogram(filtered, x="quantity", nbins=10, title="Quantity Distribution")
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No data to show")

# Treemap: region -> product sales
st.subheader("Treemap: Region and Product")
if not filtered.empty:
    treemap = filtered.groupby(["region","product"])['amount'].sum().reset_index()
    fig_treemap = px.treemap(treemap, path=["region","product"], values="amount", title="Sales Treemap")
    st.plotly_chart(fig_treemap, use_container_width=True)
else:
    st.info("No data for treemap")

# ----------------------------
# JSON download and raw view
# ----------------------------
if show_raw_json:
    st.subheader("Raw JSON (filtered)")
    st.json(filtered.to_dict(orient="records"))

st.markdown("---")

# Download filtered JSON
@st.cache_data
def to_json_bytes(df_to_export):
    return df_to_export.to_json(orient="records", date_format="iso").encode("utf-8")

st.download_button(
    label="Download filtered JSON",
    data=to_json_bytes(filtered),
    file_name="filtered_sales_report.json",
    mime="application/json"
)

# Small tips and footer
with st.expander("About this demo"):
    st.write(
        "This demo generates sample sales data (orders with order_id, date, product, region, sales_rep, quantity, unit_price and amount) and provides interactive filters. Use the sidebar to narrow down the view. You can replace `sales_report.json` with your own JSON file format (same schema) by uploading or writing over the file in the app directory."
    )

st.markdown("---")
st.caption("Made with ❤️ — Streamlit + Plotly")
