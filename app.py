# Inside app.py
from src.batching_engine import DeliveryBatchEngine, Order

engine = DeliveryBatchEngine(avg_speed_kmh=20.0)
# Pass orders and riders into engine.process_and_batch_orders(...)


import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Zomato Intelligent Order-Batching Engine",
    page_icon="🍔",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .stMetric {
        background-color: #1E293B;
        padding: 18px;
        border-radius: 12px;
        border-left: 5px solid #E23744;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 28px !important; font-weight: bold !important; }
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-size: 11px !important; font-weight: 700 !important; letter-spacing: 0.5px !important; }
    h1, h2, h3, h4 { color: #F8FAFC !important; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🍔 Zomato Real-Time Order Batching Simulator")
st.markdown(
    "Adjust parameters in the sidebar to observe live batching decisions,"
    " customer delay limits, and Zomato savings."
)

st.sidebar.header("⚙️ Real-Time Filters")

max_ready_gap = st.sidebar.slider("Max Food Ready Gap", 0, 60, 15)
max_eta_increase = st.sidebar.slider("Max Allowed Delay (ETA)", 0, 30, 10)
max_distance = st.sidebar.slider(
    "Max Drop-off Distance", 0.5, 8.0, 3.0, step=0.5
)
allow_priority = st.sidebar.toggle("Include Priority Orders", value=False)

data_path = "data/zomato_order_batching_clean_dataset.csv"
if not os.path.exists(data_path):
  data_path = (
      "zomato-order-batching-analysis/data/zomato_order_batching_clean_dataset.csv"
  )

if os.path.exists(data_path):
  df = pd.read_csv(data_path)

  effective_ready_gap = df["food_ready_gap_min"] % 60

  if not allow_priority:
    priority_ok = df["priority_type"] == "Normal"
  else:
    priority_ok = True

  capacity_ok = df["physical_capacity_ok"] == 1
  compatibility_ok = df["item_compatibility_ok"] == 1
  distance_ok = df["customer_to_customer_km"] <= max_distance
  ready_time_ok = effective_ready_gap <= max_ready_gap
  eta_ok = df["max_customer_eta_increase_min"] <= max_eta_increase

  df["custom_batching_eligible"] = (
      capacity_ok
      & compatibility_ok
      & priority_ok
      & distance_ok
      & ready_time_ok
      & eta_ok
  )

  df["dynamic_cost_saving"] = df["custom_batching_eligible"].apply(
      lambda x: 25.0 if x else 0.0
  )
  df["dynamic_riders_saved"] = df["custom_batching_eligible"].apply(
      lambda x: 1 if x else 0
  )

  total_pairs = len(df)
  eligible_df = df[df["custom_batching_eligible"]]
  batched_count = len(eligible_df)
  batch_rate = (batched_count / total_pairs) * 100 if total_pairs > 0 else 0
  total_savings = df["dynamic_cost_saving"].sum()
  riders_saved = df["dynamic_riders_saved"].sum()

  # 4 Metric Header
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("BATCHED ORDERS", f"{batched_count}")
  col2.metric("BATCH RATE", f"{batch_rate:.1f}%")
  col3.metric("NET COST SAVINGS", f"₹{total_savings:,.0f}")
  col4.metric("RIDERS SAVED", f"{int(riders_saved)}")

  st.markdown("---")

  # Navigation Tabs
  tab1, tab2 = st.tabs([
      "🚀 Route & Batching Overview",
      "⏱️ Multi-Customer ETA & Time Management",
  ])

  with tab1:
    col_left, col_right = st.columns(2)
    with col_left:
      st.subheader("🗺️ Animated Delivery Distance & Route Comparison")
      fig_pie = px.pie(
          df,
          names="custom_batching_eligible",
          color="custom_batching_eligible",
          color_discrete_map={True: "#10B981", False: "#E23744"},
          labels={True: "Batched (1 Rider)", False: "Unbatched (2 Riders)"},
      )
      fig_pie.update_layout(
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color="#F8FAFC"),
      )
      st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
      st.subheader("📊 Live Rejection Reason Breakdown")
      df_unbatched = df[~df["custom_batching_eligible"]].copy()

      def get_reason(row):
        if not allow_priority and row["priority_type"] != "Normal":
          return "Priority Protected"
        if row["food_ready_gap_min"] % 60 > max_ready_gap:
          return "Food Ready Gap"
        if row["max_customer_eta_increase_min"] > max_eta_increase:
          return "ETA Delay Exceeded"
        if row["customer_to_customer_km"] > max_distance:
          return "Distance Too High"
        return "Item/Capacity Policy"

      if not df_unbatched.empty:
        df_unbatched["reason"] = df_unbatched.apply(get_reason, axis=1)
        reason_counts = df_unbatched["reason"].value_counts().reset_index()
        fig_bar = px.bar(
            reason_counts,
            x="reason",
            y="count",
            color="reason",
            color_discrete_sequence=[
                "#FFB400",
                "#E23744",
                "#3B82F6",
                "#8B5CF6",
            ],
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F8FAFC"),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

  with tab2:
    st.subheader("⏱️ Customer Wait Time & Multi-Stop Delivery SLA")
    fig_hist = px.histogram(
        df,
        x="max_customer_eta_increase_min",
        color="custom_batching_eligible",
        nbins=20,
        labels={
            "max_customer_eta_increase_min": "Added Delay for Customer B (mins)",
            "custom_batching_eligible": "Batched Status",
        },
        color_discrete_map={True: "#10B981", False: "#E23744"},
        barmode="overlay",
    )
    fig_hist.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F8FAFC"),
    )
    st.plotly_chart(fig_hist, use_container_width=True)

  st.markdown("---")
  st.subheader("📋 Active Candidate Order Pairs Analysis")
  st.dataframe(
      df[[
          "order_id",
          "candidate_order_id",
          "restaurant",
          "society",
          "customer_to_customer_km",
          "max_customer_eta_increase_min",
          "custom_batching_eligible",
          "dynamic_cost_saving",
      ]].rename(
          columns={
              "order_id": "Order A ID",
              "candidate_order_id": "Order B ID",
              "restaurant": "Restaurant",
              "society": "Drop-off Location / Society",
              "customer_to_customer_km": "Distance A-to-B (km)",
              "max_customer_eta_increase_min": "Customer B Delay (mins)",
              "custom_batching_eligible": "Batch Decision",
              "dynamic_cost_saving": "Savings (₹)",
          }
      ),
      use_container_width=True,
  )
else:
  st.error(
      "Dataset not found. Please ensure zomato_order_batching_clean_dataset.csv"
      " is located in the data folder."
  )