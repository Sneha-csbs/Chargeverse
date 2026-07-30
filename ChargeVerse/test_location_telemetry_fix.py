from fleet_agent import FleetEVTelemetry
from app import STATIONS_DEFAULTS, _get_live_stations, DealOptimizerAgent

def test_location_telemetry_fix():
    print("--- 1. Testing FleetEVTelemetry Model Defaults ---")
    telemetry = FleetEVTelemetry()
    print("FleetEVTelemetry Dump:", telemetry.model_dump())

    assert telemetry.vehicle_id == "EV-CV-001"
    assert telemetry.current_lat == 12.9716
    assert telemetry.current_long == 77.5946
    assert telemetry.location_label == "Bengaluru Logistics Corridor, KA"
    print("FleetEVTelemetry Model Defaults OK!")

    print("\n--- 2. Testing Auction Bidding with Bengaluru Telemetry Coordinates ---")
    live = _get_live_stations()
    optimizer = DealOptimizerAgent()

    bids = optimizer.receive_bids(
        vehicle_lat=telemetry.current_lat,
        vehicle_lon=telemetry.current_long,
        sla_urgency=0.80,
        battery_current=42.0,
        battery_required=60.0,
        stations=live,
        cargo_type="Pharmaceuticals / Vaccines",
    )

    assert len(bids) > 0, "Auction bidding with telemetry coordinates should return candidates!"
    top_station = bids[0]
    print(f"Top Recommended Station for {telemetry.location_label}:", top_station["name"], f"({top_station['distance_km']} km away)")
    print("Auction Engine Integration OK!")

    print("\n=== ALL LOCATION TELEMETRY FIX TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_location_telemetry_fix()
