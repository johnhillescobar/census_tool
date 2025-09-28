"""
Benchmark geocoding performance with caching
"""

import os
import sys
import logging
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.census_geocoding import CensusGeocodingService

logger = logging.getLogger(__name__)


def benchmark_performance():
    """Benchmark geocoding performance with caching"""

    service = CensusGeocodingService()

    print("=== Performance Benchmark ===")

    # Test cases
    test_places = [
        ("Chicago", "Illinois"),
        ("New York City", "New York"),
        ("Los Angeles", "California"),
        ("Chicago", "Illinois"),  # Repeat to test caching
    ]

    print("\n1. Place Geocoding Performance:")
    for i, (place, state) in enumerate(test_places):
        start_time = time.time()
        result = service.geocode_place(place, state)
        end_time = time.time()

        duration = (end_time - start_time) * 1000
        cache_status = (
            "🔥 CACHED" if i == 3 else "🌐 API"
        )  # Last Chicago should be cached
        status = "✅" if result.level != "error" else "❌"

        print(f"{status} {place:15} -> {duration:6.1f}ms {cache_status}")

    print("\n2. Cache Statistics:")
    stats = service.get_cache_stats()
    for cache_name, info in stats.items():
        hit_rate = (
            info["hits"] / (info["hits"] + info["misses"]) * 100
            if (info["hits"] + info["misses"]) > 0
            else 0
        )
        print(
            f"   {cache_name:20} -> Hits: {info['hits']:2d}, Misses: {info['misses']:2d}, Hit Rate: {hit_rate:5.1f}%"
        )


if __name__ == "__main__":
    benchmark_performance()
