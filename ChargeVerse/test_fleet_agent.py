"""Quick smoke-test for fleet_agent.py — validates models, SLA logic,
and the critical SoC threshold trigger (50% SoC)."""

import sys
import time

sys.path.insert(0, ".")

from fleet_agent import (
    FleetEVSystemAgent,
    TelemetryUpdate,
    SLAEvaluation,
    AuctionTrigger,
)

print("=== All imports OK ===")

# ── 1. SLA_Guardian logic ────────────────────────────────────────────
agent = FleetEVSystemAgent(
    name="test_ev",
    seed="test-seed-42",
    vehicle_id="EV-TEST",
    cargo_type="Ice Cream",
    total_delivery_window_minutes=120.0,
    log_level=40,
)

print(f"Agent created: {agent.name} | address={agent.address[:16]}...")
print(f"Storage vehicle_id: {agent.storage.get('vehicle_id')}")
print(f"Storage cargo_type: {agent.storage.get('cargo_type')}")

# Test urgency calculation
score = agent._calculate_urgency_score("Ice Cream", 10.0, 14.0)
print(
    f"Ice Cream urgency (10min left, 14% battery): {score:.4f} [expected high near 1.0]"
)

score2 = agent._calculate_urgency_score("Dry Cargo", 100.0, 90.0)
print(
    f"Dry Cargo urgency (100min left, 90% battery): {score2:.4f} [expected low]"
)

score3 = agent._calculate_urgency_score("Medicines", 5.0, 5.0)
print(
    f"Medicines urgency (5min left, 5% battery): {score3:.4f} [expected very high]"
)

# ── 2. Pydantic model serialisation ──────────────────────────────────
t = TelemetryUpdate(
    vehicle_id="EV-002",
    gps_lat=48.8566,
    gps_lon=2.3522,
    battery_soc=12.5,
    cargo_type="Medicines",
    delivery_window_remaining_minutes=15.0,
)
print(f"TelemetryUpdate model: {t.model_dump_json()}")

a = AuctionTrigger(
    vehicle_id="EV-002",
    gps_lat=48.8566,
    gps_lon=2.3522,
    battery_level=12.5,
    sla_urgency=0.92,
    cargo_type="Medicines",
    timestamp=time.time(),
)
print(f"AuctionTrigger model: {a.model_dump_json()}")

s = SLAEvaluation(
    vehicle_id="EV-002",
    urgency_score=0.92,
    cargo_type="Medicines",
    delivery_window_remaining_minutes=15.0,
    timestamp=time.time(),
)
print(f"SLAEvaluation model: {s.model_dump_json()}")

# ── 3. Critical threshold trigger (SoC <= 50%) ────────────────────
agent.storage.set("battery_soc", 45.0)
agent.storage.set("remaining_window_minutes", 5.0)
print("\nRunning battery check with SoC = 45.0 % ...")
agent._run_battery_check(agent._build_context())

trigger_data = agent.storage.get("last_auction_trigger")
assert trigger_data is not None, "Expected AuctionTrigger to be stored for 45% SoC!"
print(f"AuctionTrigger persisted: {trigger_data}")
print("  -> battery_level  =", trigger_data["battery_level"])
print("  -> sla_urgency    =", trigger_data["sla_urgency"])
print("  -> cargo_type     =", trigger_data["cargo_type"])
print("  -> vehicle_id     =", trigger_data["vehicle_id"])

# ── 4. Test that healthy battery (>50%) does NOT trigger ──────────────
agent.storage.set("battery_soc", 85.0)
agent.storage.set("remaining_window_minutes", 100.0)
agent.storage.remove("last_auction_trigger")
agent._run_battery_check(agent._build_context())
assert agent.storage.get("last_auction_trigger") is None, (
    "Expected NO AuctionTrigger for healthy battery (85% SoC > 50%)!"
)
print("\n[OK] No false trigger for healthy battery (85 % SoC)")
print("=== All tests passed successfully! ===")
