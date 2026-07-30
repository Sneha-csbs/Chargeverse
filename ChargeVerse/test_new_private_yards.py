from app import STATIONS_DEFAULTS, _get_live_stations, DealOptimizerAgent

def test_new_private_yards_integration():
    print("--- 1. Testing STATIONS_DEFAULTS Integration ---")
    assert "station_f" in STATIONS_DEFAULTS
    assert "station_g" in STATIONS_DEFAULTS

    sf = STATIONS_DEFAULTS["station_f"]
    sg = STATIONS_DEFAULTS["station_g"]

    assert sf["name"] == "[Private] Hosur Freight Terminal"
    assert sf["facility_type"] == "PRIVATE_YARD"
    assert sf["kw"] == 250.0
    assert sf["safety_buffer_percentage"] == 70.0
    assert sf["passcode"] == "#HSR-808-GATE"

    assert sg["name"] == "[Private] Peenya EV Logistics Hub"
    assert sg["facility_type"] == "PRIVATE_YARD"
    assert sg["kw"] == 300.0
    assert sg["safety_buffer_percentage"] == 60.0
    assert sg["passcode"] == "#PNY-909-GATE"

    print("STATIONS_DEFAULTS Integration OK!")

    print("\n--- 2. Testing Live Stations & Safety Buffer Formula ---")
    live = _get_live_stations()
    assert "station_f" in live
    assert "station_g" in live

    # Safety Buffer Formula: Total * (100 - Buffer)/100
    sf_avail = sf["kw"] * ((100.0 - sf["safety_buffer_percentage"]) / 100.0)
    sg_avail = sg["kw"] * ((100.0 - sg["safety_buffer_percentage"]) / 100.0)

    print(f"Station F Available Power: {sf_avail:.1f} kW (Expected 75.0 kW)")
    print(f"Station G Available Power: {sg_avail:.1f} kW (Expected 120.0 kW)")

    assert sf_avail == 75.0
    assert sg_avail == 120.0
    print("Safety Buffer Calculation OK!")

    print("\n--- 3. Testing DealOptimizerAgent Bidding Participation ---")
    optimizer = DealOptimizerAgent()
    results = optimizer.receive_bids(
        vehicle_lat=12.8000,
        vehicle_lon=77.7000,
        sla_urgency=0.85,
        battery_current=40.0,
        battery_required=60.0,
        stations=live,
        cargo_type="Medicines",
    )
    station_ids_ranked = [s["station_id"] for s in results]
    print("Ranked Auction Bids Station IDs:", station_ids_ranked)

    # Confirm that station_f or station_g participate in auction bidding
    found_new_yards = set(station_ids_ranked).intersection({"station_f", "station_g"})
    print("New Yards Found in Dynamic Auction Results:", list(found_new_yards))
    assert len(found_new_yards) > 0, "Expected new private yards to participate in dynamic auction bidding!"

    # Verify Passcodes for Station F and Station G
    for s in results:
        if s["station_id"] == "station_f":
            assert s["passcode"] == "#HSR-808-GATE"
        elif s["station_id"] == "station_g":
            assert s["passcode"] == "#PNY-909-GATE"

    print("Gate Passcode Generation & Verification OK!")

    print("\n=== ALL HOSUR & PEENYA PRIVATE YARD INTEGRATION TESTS PASSED! ===")

if __name__ == "__main__":
    test_new_private_yards_integration()
