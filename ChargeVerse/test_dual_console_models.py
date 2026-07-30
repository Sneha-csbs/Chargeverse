from fleet_agent import FacilityType, GatePassRequest, StationConsoleState

def test_pydantic_station_console_models():
    print("--- 1. Testing FacilityType Enum ---")
    assert FacilityType.PUBLIC_STATION == "PUBLIC_STATION"
    assert FacilityType.PRIVATE_YARD == "PRIVATE_YARD"
    print("FacilityType Enum OK!")

    print("\n--- 2. Testing GatePassRequest Model ---")
    req = GatePassRequest(
        request_id="REQ-808-01",
        truck_id="EV-CV-001",
        cargo_type="Medicines",
        cargo_weight=0.95,
        urgency_score=0.85,
    )
    assert req.status == "PENDING"
    assert req.pass_code is None

    req.status = "APPROVED"
    req.pass_code = "#808-GATE-PASS"
    print("GatePassRequest dump:", req.model_dump())
    assert req.pass_code == "#808-GATE-PASS"
    print("GatePassRequest Model OK!")

    print("\n--- 3. Testing Private Yard Console State & Constraint ---")
    py_state = StationConsoleState(
        station_id="station_a",
        facility_name="[Private] BLR Solar Yard",
        facility_type=FacilityType.PRIVATE_YARD,
        total_capacity_kw=200.0,
        tariff_per_kwh=12.50,
        safety_buffer_percent=70.0,
        queued_vehicles_150m=2,
    )
    print("Private Yard available_p2p_kw (200kW @ 70% buffer):", py_state.available_p2p_kw)
    assert py_state.available_p2p_kw == 60.0
    assert py_state.estimated_queue_delay_mins == 0.0
    assert py_state.p2p_active is True

    # Test P2P < 15 kW Constraint Trigger
    py_state_low = StationConsoleState(
        station_id="station_c",
        facility_name="[Private] Whitefield Tech Hub",
        facility_type=FacilityType.PRIVATE_YARD,
        total_capacity_kw=100.0,
        tariff_per_kwh=12.50,
        safety_buffer_percent=90.0,
    )
    print("Low Capacity Yard available_p2p_kw (100kW @ 90% buffer):", py_state_low.available_p2p_kw)
    assert py_state_low.available_p2p_kw == 10.0
    assert py_state_low.p2p_active is False
    print("Private Yard Console State & <15kW Constraint OK!")

    print("\n--- 4. Testing Public Station Console State & Queue Calculation ---")
    pub_state = StationConsoleState(
        station_id="station_b",
        facility_name="[Public] Hosur EV Point",
        facility_type=FacilityType.PUBLIC_STATION,
        total_capacity_kw=150.0,
        tariff_per_kwh=0.28,
        queued_vehicles_150m=3,
    )
    print("Public Hub available_p2p_kw:", pub_state.available_p2p_kw)
    print("Public Hub estimated_queue_delay_mins (3 queued EVs):", pub_state.estimated_queue_delay_mins)
    assert pub_state.available_p2p_kw == 150.0
    assert pub_state.estimated_queue_delay_mins == 60.0
    assert pub_state.p2p_active is True
    print("Public Station Console State OK!")

    print("\n=== ALL DUAL-FACILITY STATION CONSOLE TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_pydantic_station_console_models()
