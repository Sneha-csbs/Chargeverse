from fleet_agent import FleetEVTelemetry
from app import _reverse_geocode, DealOptimizerAgent, STATIONS_DEFAULTS, _get_live_stations

def test_auto_gps_detection():
    print("--- 1. Testing Dynamic Reverse Geocoding Worldwide ---")
    chennai_loc = _reverse_geocode(13.0827, 80.2707)
    print("Chennai Coordinates (13.0827, 80.2707) Reverse Geocoded Label:", chennai_loc)
    assert "Chennai" in chennai_loc or "Tamil" in chennai_loc or "India" in chennai_loc

    blr_loc = _reverse_geocode(12.9716, 77.5946)
    print("Bengaluru Coordinates (12.9716, 77.5946) Reverse Geocoded Label:", blr_loc)
    assert "Bengaluru" in blr_loc or "Karnataka" in blr_loc or "India" in blr_loc
    print("Dynamic Reverse Geocoding OK!")

    print("\n--- 2. Testing FleetEVTelemetry Dynamic Instantiation ---")
    telemetry = FleetEVTelemetry(
        vehicle_id="EV-CV-001",
        current_lat=13.0827,
        current_long=80.2707,
        location_label=chennai_loc,
        current_soc=45.0,
    )
    print("Live FleetEVTelemetry Dump:", telemetry.model_dump())

    assert telemetry.current_lat == 13.0827
    assert telemetry.current_long == 80.2707
    assert telemetry.location_label == chennai_loc
    print("FleetEVTelemetry Dynamic Instantiation OK!")

    print("\n--- 3. Testing Dynamic Auction Bidding with Live GPS Location ---")
    live = _get_live_stations()
    optimizer = DealOptimizerAgent()

    bids = optimizer.receive_bids(
        vehicle_lat=telemetry.current_lat,
        vehicle_lon=telemetry.current_long,
        sla_urgency=0.85,
        battery_current=45.0,
        battery_required=65.0,
        stations=live,
        cargo_type="Pharmaceuticals / Vaccines",
    )

    assert len(bids) > 0, "Auction bidding with live device GPS should return valid station candidates!"
    top_station = bids[0]
    print(f"Top Recommended Station for Live GPS Location ({telemetry.location_label}):", top_station["name"], f"({top_station['distance_km']} km away)")

    print("\n=== ALL DYNAMIC HTML5 DEVICE GPS TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_auto_gps_detection()
