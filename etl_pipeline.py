import sqlite3
import pandas as pd

def run_sql_batching_pipeline():
    """
    Simulates a Data Analyst SQL pipeline using Python's built-in SQLite.
    Processes order data, applies business logic via CASE statements, 
    and ranks clusters using Window Functions.
    """
    print("--- Starting Zomato SQL Data Pipeline ---")
    
    # 1. Connect to an in-memory SQLite database
    conn = sqlite3.connect(":memory:")
    
    # 2. Create sample mock data (or replace with pd.read_csv('your_orders.csv'))
    data = {
        'order_id': [101, 102, 103, 104, 105],
        'restaurant_id': [1, 1, 2, 3, 2],
        'society_name': ['Green Park', 'Green Park', 'Saket', 'Vasant Vihar', 'Saket'],
        'prep_ready_gap': [10, 35, 12, 40, 5],
        'eta_delay': [3, 8, 4, 10, 2],
        'distance_km': [1.5, 4.0, 2.1, 5.2, 1.2],
        'is_priority': [0, 0, 1, 0, 0],
        'is_bulky': [0, 1, 0, 0, 0]
    }
    df = pd.DataFrame(data)
    
    # Load DataFrame into a SQL table named 'raw_orders'
    df.to_sql("raw_orders", conn, index=False, if_exists="replace")
    
    # 3. Write Core SQL Query (Window Functions + CASE Statements)
    sql_query = """
        SELECT 
            order_id,
            restaurant_id,
            society_name,
            prep_ready_gap,
            eta_delay,
            distance_km,
            -- Window Function: Ranks orders per society cluster based on prep speed
            ROW_NUMBER() OVER (PARTITION BY society_name ORDER BY prep_ready_gap ASC) AS cluster_rank,
            -- CASE Statement: Evaluates batch eligibility rules
            CASE 
                WHEN is_priority = 1 THEN 'Rejected: Priority Fee Paid'
                WHEN is_bulky = 1 THEN 'Rejected: Bulky / Fragile Item'
                WHEN prep_ready_gap > 30 THEN 'Rejected: Food Ready Gap'
                WHEN eta_delay > 5 THEN 'Rejected: ETA Delay Exceeded'
                WHEN distance_km > 3.1 THEN 'Rejected: Distance Too Far'
                ELSE 'Eligible Batch'
            END AS batch_routing_status
        FROM raw_orders
    """
    
    # Execute the query and pull results back into Pandas
    processed_df = pd.read_sql_query(sql_query, conn)
    
    print("\nProcessed SQL Output:")
    print(processed_df)
    
    # Close the database connection
    conn.close()
    print("\n--- Pipeline Completed Successfully ---")

if __name__ == "__main__":
    run_sql_batching_pipeline()
    