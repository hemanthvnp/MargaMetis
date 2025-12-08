import random
from typing import List, Tuple

class TrafficPredictor:
    """
    Stub for traffic prediction. Replace with real ML model for production.
    """
    def predict_traffic(self, path: List[int], time_of_day: int) -> List[float]:
        # Returns a list of traffic congestion values (0-1) for each segment
        # Deterministic: seed with route and time_of_day
        # Use a stable seed: combine node IDs and time_of_day into a string
        seed_str = ','.join(str(n) for n in path) + f'-{time_of_day}'
        seed = sum(ord(c) for c in seed_str)
        random.seed(seed)
        base = 0.2 + 0.6 * (abs(time_of_day - 17) / 24)  # peak at 5pm
        return [min(1.0, base + random.uniform(-0.1, 0.1)) for _ in path]

    def estimate_travel_time(self, path: List[int], base_time: float, traffic: List[float]) -> float:
        # Increase travel time based on congestion
        return base_time * (1 + sum(traffic) / len(traffic))

    def best_time_for_route(self, path: List[int], base_time: float) -> Tuple[int, float]:
        # Simulate best time of day (hour) for least traffic
        best_hour = min(range(24), key=lambda h: self.estimate_travel_time(path, base_time, self.predict_traffic(path, h)))
        best_time = self.estimate_travel_time(path, base_time, self.predict_traffic(path, best_hour))
        return best_hour, best_time
