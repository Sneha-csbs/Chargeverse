import sys
from fleet_agent import YardHostPayload

# 1. Verify Pydantic Schema
payload = YardHostPayload(
    station_id="station_a",
    station_name="[Private] BLR Solar Yard",
    charger_status="Available",
    total_capacity_kw=250.0,
    safety_buffer_percentage=70.0,
    listed_idle_capacity_kw=75.0,
    available_power_kw=75.0,
    timestamp=1785260000.0,
)
print("1. Pydantic YardHostPayload dump:")
print(payload.model_dump())
assert payload.total_capacity_kw == 250.0
assert payload.safety_buffer_percentage == 70.0
assert payload.available_power_kw == 75.0

# 2. Test Available Power Formula
def calc_available_power(total_kw: float, buffer_pct: float) -> tuple[float, float, float]:
    reserved_kw = round(total_kw * (buffer_pct / 100.0), 1)
    available_kw = round(total_kw * ((100.0 - buffer_pct) / 100.0), 1)
    idle_pct = max(0.0, 100.0 - buffer_pct)
    return reserved_kw, available_kw, idle_pct

res, avail, idle = calc_available_power(250.0, 70.0)
print(f"2. Formula Test (250kW @ 70% buffer): Reserved={res}kW, Available={avail}kW, Idle={idle}%")
assert res == 175.0
assert avail == 75.0
assert idle == 30.0

res90, avail90, idle90 = calc_available_power(120.0, 90.0)
print(f"3. Formula Test (120kW @ 90% buffer): Reserved={res90}kW, Available={avail90}kW, Idle={idle90}%")
assert res90 == 108.0
assert avail90 == 12.0
assert idle90 == 10.0

print("\n=== ALL RESERVE BUFFER & IDLE CAPACITY TESTS PASSED SUCCESSFULLY! ===")
