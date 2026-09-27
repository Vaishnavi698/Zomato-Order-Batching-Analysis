import pandas as pd


def load_dataset(file_path="data/zomato_order_batching_clean_dataset.csv"):
    """Loads and returns the cleaned Zomato order batching dataset."""
    return pd.read_csv(file_path)


def evaluate_batch_eligibility(
    df,
    max_ready_gap_min=15,
    max_eta_increase_min=10,
    max_customer_distance_km=3.0,
    allow_priority_batching=False,
):
    """Evaluates candidate order pairs against configurable business constraints.

    Parameters:
    -----------
    df : pandas.DataFrame
        Clean order batching dataset.
    max_ready_gap_min : float
        Maximum allowed difference in food preparation completion time between two orders.
    max_eta_increase_min : float
        Maximum acceptable delay added to a customer's delivery window.
    max_customer_distance_km : float
        Maximum distance between two delivery destinations.
    allow_priority_batching : bool
        If False, priority/express delivery orders are excluded from batching.

    Returns:
    --------
    pandas.DataFrame : Processed DataFrame with custom eligibility flags and calculated metrics.
    """
    data = df.copy()

    # Priority check
    if not allow_priority_batching:
        priority_ok = data["priority_type"] == "Normal"
    else:
        priority_ok = True

    # Physical and distance checks
    capacity_ok = data["physical_capacity_ok"] == 1
    compatibility_ok = data["item_compatibility_ok"] == 1
    distance_ok = (
        data["customer_to_customer_km"] <= max_customer_distance_km
    )

    # Time window constraints
    ready_time_ok = data["food_ready_gap_min"] <= max_ready_gap_min
    eta_ok = data["max_customer_eta_increase_min"] <= max_eta_increase_min

    # Master Eligibility Condition
    data["custom_batching_eligible"] = (
        capacity_ok
        & compatibility_ok
        & priority_ok
        & distance_ok
        & ready_time_ok
        & eta_ok
    )

    # Determine dynamic rejection reasons for unbatched pairs
    rejection_conditions = [
        (~priority_ok, "Priority Order Excluded"),
        (~capacity_ok | ~compatibility_ok, "Physical / Capacity Violation"),
        (~distance_ok, "Customer Distance Exceeds Limit"),
        (~ready_time_ok, "Food Ready Gap Too High"),
        (~eta_ok, "Customer ETA Delay Exceeds Limit"),
    ]

    data["custom_rejection_reason"] = "Eligible for Batching"
    for condition, reason in rejection_conditions:
        data.loc[
            condition & (~data["custom_batching_eligible"]),
            "custom_rejection_reason",
        ] = reason

    return data


def compute_key_metrics(df):
    """Computes high-level business KPIs for Zomato, Riders, and Restaurants."""
    total_orders = len(df)
    eligible_orders = df["custom_batching_eligible"].sum()
    batch_rate = (eligible_orders / total_orders) * 100 if total_orders > 0 else 0

    eligible_df = df[df["custom_batching_eligible"]]

    total_cost_savings = eligible_df["estimated_cost_saving_inr"].sum()
    riders_saved = eligible_df["riders_saved"].sum()
    pickup_reduction = eligible_df["pickup_visits_reduced"].sum()

    return {
        "total_orders": total_orders,
        "eligible_orders": eligible_orders,
        "batch_rate_pct": round(batch_rate, 2),
        "total_cost_savings_inr": round(total_cost_savings, 2),
        "riders_saved": int(riders_saved),
        "pickup_reduction_visits": int(pickup_reduction),
    }