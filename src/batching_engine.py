import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class Item:
    name: str
    quantity: int
    is_fragile: bool = False  # e.g., Cake (can spill/destroy)
    weight_kg: float = 0.5   # e.g., 5kg Biryani

@dataclass
class Order:
    order_id: str
    customer_name: str
    restaurant_id: str
    restaurant_name: str
    society_id: str          # e.g., "Green_Glen_Layout_Block_A"
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    items: List[Item]
    prep_time_mins: int = 15 # Kitchen preparation time
    is_priority: bool = False # Paid priority delivery fee
    priority_fee_paid: float = 0.0

    @property
    def is_bulky_or_fragile(self) -> bool:
        """Check if order contains fragile items (cakes) or exceeds bag capacity (>4kg)."""
        total_weight = sum(item.weight_kg * item.quantity for item in self.items)
        has_fragile = any(item.is_fragile for item in self.items)
        return has_fragile or total_weight > 4.0

@dataclass
class BatchResult:
    batch_id: str
    rider_id: str
    restaurant_id: str
    society_id: str
    orders: List[Order]
    total_travel_time_mins: float
    assignment_lead_time_mins: float  # How many mins before prep completion to assign rider
    
    # Financial Analysis
    unbatched_cost_zomato: float     # Base pay for individual deliveries
    batched_cost_zomato: float       # Payout + incentive for single rider
    zomato_net_savings: float        # Money saved by Zomato
    rider_incentive_earned: float    # Extra money earned by rider
    
    # Operational & Time Metrics
    max_dropoff_delay_mins: float    # Delay between Person A and Person B (< 5 mins)
    crowd_reduction_riders: int      # Saved rider visits at restaurant counter

class DeliveryBatchEngine:
    def __init__(self, 
                 avg_speed_kmh: float = 20.0,
                 base_rider_payout: float = 40.0,     # Standard single order pay
                 batch_extra_incentive: float = 20.0,  # Bonus paid to rider for taking 2nd order
                 rider_avg_prep_distance_km: float = 1.5): # Distance from rider to restaurant
        
        self.avg_speed_kmh = avg_speed_kmh
        self.base_rider_payout = base_rider_payout
        self.batch_extra_incentive = batch_extra_incentive
        self.rider_avg_prep_distance_km = rider_avg_prep_distance_km

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates distance in kilometers between two GPS coordinates."""
        R = 6371.0
        dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _get_travel_time(self, dist_km: float) -> float:
        """Converts travel distance to minutes."""
        return (dist_km / self.avg_speed_kmh) * 60.0

    def process_orders(self, orders: List[Order], available_riders: List[str]) -> List[BatchResult]:
        results = []
        batchable_groups: Dict[Tuple[str, str], List[Order]] = {}

        # -------------------------------------------------------------
        # STEP 1: PRE-FILTER EXCLUSIONS (Priority & Bulky/Fragile)
        # -------------------------------------------------------------
        for order in orders:
            if order.is_priority or order.is_bulky_or_fragile:
                if available_riders:
                    rider = available_riders.pop(0)
                    dist = self._haversine_distance(
                        order.pickup_lat, order.pickup_lng,
                        order.dropoff_lat, order.dropoff_lng
                    )
                    travel_time = self._get_travel_time(dist)
                    
                    # Rider assignment timing: Assign so rider arrives right when food is ready
                    rider_travel_to_rest = self._get_travel_time(self.rider_avg_prep_distance_km)
                    lead_time = max(0.0, order.prep_time_mins - rider_travel_to_rest)

                    results.append(BatchResult(
                        batch_id=f"SINGLE_{order.order_id}",
                        rider_id=rider,
                        restaurant_id=order.restaurant_id,
                        society_id=order.society_id,
                        orders=[order],
                        total_travel_time_mins=travel_time,
                        assignment_lead_time_mins=round(lead_time, 1),
                        unbatched_cost_zomato=self.base_rider_payout,
                        batched_cost_zomato=self.base_rider_payout,
                        zomato_net_savings=0.0,
                        rider_incentive_earned=0.0,
                        max_dropoff_delay_mins=0.0,
                        crowd_reduction_riders=0
                    ))
            else:
                # Group candidate standard orders by (Restaurant, Society)
                group_key = (order.restaurant_id, order.society_id)
                batchable_groups.setdefault(group_key, []).append(order)

        # -------------------------------------------------------------
        # STEP 2: BATCH STANDARD ORDERS (Same Restaurant + Same Society)
        # -------------------------------------------------------------
        for (rest_id, soc_id), group_orders in batchable_groups.items():
            used_indices = set()

            for i in range(len(group_orders)):
                if i in used_indices or not available_riders:
                    continue

                o1 = group_orders[i]
                best_pair_idx = None

                for j in range(i + 1, len(group_orders)):
                    if j in used_indices:
                        continue
                    o2 = group_orders[j]

                    # Condition A: Kitchen Prep Time Gap <= 5 minutes
                    if abs(o1.prep_time_mins - o2.prep_time_mins) > 5:
                        continue

                    # Condition B: Customer Drop-off Delay <= 5 minutes
                    # Since both are in the same society, extra travel between Flat A and Flat B is ~1-2 mins
                    extra_dropoff_delay = 2.0  # 2 mins for walking/elevator inside society
                    if extra_dropoff_delay <= 5.0:
                        best_pair_idx = j
                        break

                rider = available_riders.pop(0)

                if best_pair_idx is not None:
                    used_indices.add(i)
                    used_indices.add(best_pair_idx)
                    o2 = group_orders[best_pair_idx]
                    
                    # Calculate Batched Travel Details
                    dist_to_soc = self._haversine_distance(
                        o1.pickup_lat, o1.pickup_lng,
                        o1.dropoff_lat, o1.dropoff_lng
                    )
                    batched_travel_time = self._get_travel_time(dist_to_soc) + 2.0 # +2 mins for 2nd drop inside society
                    
                    # Calculate Rider Lead Assignment Time
                    max_prep_time = max(o1.prep_time_mins, o2.prep_time_mins)
                    rider_travel_to_rest = self._get_travel_time(self.rider_avg_prep_distance_km)
                    lead_time = max(0.0, max_prep_time - rider_travel_to_rest)

                    # Financial Metrics
                    unbatched_cost = self.base_rider_payout * 2  # Cost if 2 riders sent (₹40 + ₹40 = ₹80)
                    batched_cost = self.base_rider_payout + self.batch_extra_incentive # Cost for 1 rider (₹40 + ₹20 = ₹60)
                    net_savings = unbatched_cost - batched_cost  # Zomato saves ₹20

                    results.append(BatchResult(
                        batch_id=f"BATCH_{o1.order_id}_{o2.order_id}",
                        rider_id=rider,
                        restaurant_id=rest_id,
                        society_id=soc_id,
                        orders=[o1, o2],
                        total_travel_time_mins=round(batched_travel_time, 1),
                        assignment_lead_time_mins=round(lead_time, 1),
                        unbatched_cost_zomato=unbatched_cost,
                        batched_cost_zomato=batched_cost,
                        zomato_net_savings=net_savings,
                        rider_incentive_earned=self.batch_extra_incentive,
                        max_dropoff_delay_mins=2.0,
                        crowd_reduction_riders=1  # 1 less rider standing at Burger King
                    ))
                else:
                    # Single Order fallback
                    used_indices.add(i)
                    dist = self._haversine_distance(
                        o1.pickup_lat, o1.pickup_lng,
                        o1.dropoff_lat, o1.dropoff_lng
                    )
                    travel_time = self._get_travel_time(dist)
                    rider_travel_to_rest = self._get_travel_time(self.rider_avg_prep_distance_km)
                    lead_time = max(0.0, o1.prep_time_mins - rider_travel_to_rest)

                    results.append(BatchResult(
                        batch_id=f"SINGLE_{o1.order_id}",
                        rider_id=rider,
                        restaurant_id=rest_id,
                        society_id=soc_id,
                        orders=[o1],
                        total_travel_time_mins=round(travel_time, 1),
                        assignment_lead_time_mins=round(lead_time, 1),
                        unbatched_cost_zomato=self.base_rider_payout,
                        batched_cost_zomato=self.base_rider_payout,
                        zomato_net_savings=0.0,
                        rider_incentive_earned=0.0,
                        max_dropoff_delay_mins=0.0,
                        crowd_reduction_riders=0
                    ))

        return results


# -------------------------------------------------------------
# TEST & ANALYTICS EXECUTION
# -------------------------------------------------------------
if __name__ == "__main__":
    engine = DeliveryBatchEngine()

    # Sample Scenario: Burger King orders going to 'Eldeco_Society'
    sample_orders = [
        # Person A: Standard Order
        Order(
            order_id="ORD_101", customer_name="Person A (Flat 101)",
            restaurant_id="BK_01", restaurant_name="Burger King",
            society_id="Eldeco_Society",
            pickup_lat=28.6139, pickup_lng=77.2090,
            dropoff_lat=28.6300, dropoff_lng=77.2200,
            items=[Item("Whopper Burger", 2, is_fragile=False, weight_kg=0.8)],
            prep_time_mins=15, is_priority=False
        ),
        # Person B: Standard Order (Same society & restaurant) -> CAN BE BATCHED WITH PERSON A
        Order(
            order_id="ORD_102", customer_name="Person B (Flat 405)",
            restaurant_id="BK_01", restaurant_name="Burger King",
            society_id="Eldeco_Society",
            pickup_lat=28.6139, pickup_lng=77.2090,
            dropoff_lat=28.6300, dropoff_lng=77.2200,
            items=[Item("Crispy Veg Burger", 1, is_fragile=False, weight_kg=0.4)],
            prep_time_mins=16, is_priority=False
        ),
        # Person C: Ordered 3kg Cake (Fragile) -> CANNOT BE BATCHED
        Order(
            order_id="ORD_103", customer_name="Person C (Cake)",
            restaurant_id="BK_01", restaurant_name="Burger King",
            society_id="Eldeco_Society",
            pickup_lat=28.6139, pickup_lng=77.2090,
            dropoff_lat=28.6300, dropoff_lng=77.2200,
            items=[Item("Chocolate Cake", 1, is_fragile=True, weight_kg=2.0)],
            prep_time_mins=12, is_priority=False
        ),
        # Person D: Paid Priority Fee (₹50) -> CANNOT BE BATCHED
        Order(
            order_id="ORD_104", customer_name="Person D (Priority)",
            restaurant_id="BK_01", restaurant_name="Burger King",
            society_id="Eldeco_Society",
            pickup_lat=28.6139, pickup_lng=77.2090,
            dropoff_lat=28.6300, dropoff_lng=77.2200,
            items=[Item("Fries & Meal", 1, is_fragile=False, weight_kg=0.5)],
            prep_time_mins=10, is_priority=True, priority_fee_paid=50.0
        )
    ]

    riders = ["Rider_1_Ramesh", "Rider_2_Suresh", "Rider_3_Amit", "Rider_4_Vikas"]
    batch_results = engine.process_orders(sample_orders, riders)

    print("\n========================================================")
    print("         ORDER BATCHING & ANALYTICS REPORT              ")
    print("========================================================\n")

    total_zomato_savings = sum(b.zomato_net_savings for b in batch_results)
    total_crowd_reduction = sum(b.crowd_reduction_riders for b in batch_results)

    for res in batch_results:
        order_names = [o.customer_name for o in res.orders]
        print(f"► Batch ID: {res.batch_id}")
        print(f"  Assigned Rider       : {res.rider_id}")
        print(f"  Orders Included      : {order_names}")
        print(f"  Rider Assign Lead    : {res.assignment_lead_time_mins} mins after order placement")
        print(f"  Max Dropoff Delay    : {res.max_dropoff_delay_mins} mins (Person B vs Person A)")
        print(f"  Zomato Cost Saved    : ₹{res.zomato_net_savings}")
        print(f"  Rider Bonus Earned   : ₹{res.rider_incentive_earned}")
        print("--------------------------------------------------------")

    print(f"\nTOTAL ZOMATO COST SAVED       : ₹{total_zomato_savings}")
    print(f"RESTAURANT CROWD REDUCTION     : {total_crowd_reduction} fewer rider(s) waiting at counter")