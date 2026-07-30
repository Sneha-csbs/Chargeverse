"""
ChargeVerse — Fleet EV System Agent
====================================
Production-grade agent for managing Electric Vehicle fleet operations
using the **Fetch.ai uagents** framework.

──  Architecture  ──────────────────────────────────────────────────────
* Pydantic message models  :  `TelemetryUpdate`, `SLAEvaluation`,
  `AuctionTrigger`.
* `FleetEVSystemAgent`     :  Subclasses ``uagents.Agent`` with an
  embedded **SLA_Guardian** algorithm.
* Interval loop (30 s)     :  Simulates battery discharge, evaluates
  SLA urgency, and autonomously assembles an ``AuctionTrigger`` when
  SoC < 15 %.
* Message handlers         :  Accept external telemetry and respond to
  incoming auction triggers.
* Standalone execution     :  ``python fleet_agent.py`` starts an agent
  with default Ice‑Cream configuration.
"""

from __future__ import annotations

from enum import Enum
import logging
import time
from typing import Any, List, Optional

from pydantic import BaseModel, Field as PydanticField
from uagents import Agent, Context, Field, Model


class FacilityType(str, Enum):
    PUBLIC_STATION = "PUBLIC_STATION"
    PRIVATE_YARD = "PRIVATE_YARD"


class FleetEVTelemetry(BaseModel):
    vehicle_id: str = PydanticField(default="EV-CV-001", description="Unique vehicle ID")
    current_lat: float = PydanticField(default=12.9716, description="Device latitude")
    current_long: float = PydanticField(default=77.5946, description="Device longitude")
    location_label: str = PydanticField(default="Real-time GPS Location", description="Dynamic location label")
    current_soc: float = PydanticField(default=100.0, description="Current Battery SoC")
    required_soc: float = PydanticField(default=100.0, description="Target/Required Battery SoC")

    @property
    def energy_deficit(self) -> float:
        return max(0.0, round(self.required_soc - self.current_soc, 2))

    @property
    def is_auction_required(self) -> bool:
        return self.current_soc < 95.0 and self.energy_deficit > 0.0




class GatePassRequest(BaseModel):
    request_id: str = PydanticField(..., description="Unique access request ID")
    truck_id: str = PydanticField(..., description="Inbound EV Truck ID")
    cargo_type: str = PydanticField(..., description="Cargo type payload")
    cargo_weight: float = PydanticField(..., description="Cargo SLA weight W_cargo")
    urgency_score: float = PydanticField(..., description="SLA urgency score U_SLA")
    status: str = PydanticField(default="PENDING", description="Request status: PENDING, APPROVED, REJECTED")
    pass_code: Optional[str] = PydanticField(default=None, description="Generated digital gate pass code")


class StationConsoleState(BaseModel):
    station_id: str = PydanticField(..., description="Unique station ID")
    facility_name: str = PydanticField(..., description="Facility display name")
    facility_type: FacilityType = PydanticField(..., description="PUBLIC_STATION or PRIVATE_YARD")
    total_capacity_kw: float = PydanticField(default=200.0, description="Total charger capacity in kW")
    tariff_per_kwh: float = PydanticField(default=12.50, description="Base tariff in $/kWh")
    safety_buffer_percent: float = PydanticField(default=70.0, description="Safety buffer percentage [0-90%]")
    queued_vehicles_150m: int = PydanticField(default=0, description="Geofenced queued vehicles count")
    gate_pass_requests: List[GatePassRequest] = PydanticField(default_factory=list, description="List of gate pass requests")

    @property
    def available_p2p_kw(self) -> float:
        if self.facility_type == FacilityType.PRIVATE_YARD:
            return round(self.total_capacity_kw * ((100.0 - self.safety_buffer_percent) / 100.0), 1)
        return self.total_capacity_kw

    @property
    def estimated_queue_delay_mins(self) -> float:
        if self.facility_type == FacilityType.PUBLIC_STATION:
            return round(self.queued_vehicles_150m * 20.0, 1)
        return 0.0

    @property
    def p2p_active(self) -> bool:
        return self.available_p2p_kw >= 15.0




# ======================================================================
# 1.  PYDANTIC MESSAGE MODELS
# ======================================================================


class TelemetryUpdate(Model):
    """Incoming telemetry pushed from a fleet vehicle.

    Attributes:
        vehicle_id:                    Unique vehicle identifier.
        gps_lat / gps_lon:             Current GPS coordinates.
        battery_soc:                   Battery State of Charge [0‑100 %].
        cargo_type:                    Perishability category
                                       (``Ice Cream``, ``Medicines``,
                                       ``Dry Cargo``).
        delivery_window_remaining_minutes:
            Remaining minutes in the contractual delivery window.
    """

    vehicle_id: str = Field(
        ..., description="Unique vehicle identifier"
    )
    gps_lat: float = Field(
        ..., description="Current GPS latitude"
    )
    gps_lon: float = Field(
        ..., description="Current GPS longitude"
    )
    battery_soc: float = Field(
        ..., description="Battery State of Charge (0–100 %)"
    )
    cargo_type: str = Field(
        ..., description="Cargo type: Ice Cream, Medicines, or Dry Cargo"
    )
    delivery_window_remaining_minutes: float = Field(
        ..., description="Remaining minutes in the delivery window"
    )


class SLAEvaluation(Model):
    """Result published by the embedded SLA_Guardian algorithm.

    Attributes:
        vehicle_id:               Vehicle that was evaluated.
        urgency_score:            Composite urgency score [0.0‑1.0].
        cargo_type:               Cargo type at evaluation time.
        delivery_window_remaining_minutes:
            Remaining window at the moment of evaluation.
        timestamp:                Unix epoch seconds of evaluation.
    """

    vehicle_id: str = Field(
        ..., description="Unique vehicle identifier"
    )
    urgency_score: float = Field(
        ..., description="SLA urgency score clamped to [0.0, 1.0]"
    )
    cargo_type: str = Field(
        ..., description="Cargo type evaluated"
    )
    delivery_window_remaining_minutes: float = Field(
        ..., description="Delivery window remaining at evaluation time"
    )
    timestamp: float = Field(
        ..., description="Unix timestamp of the evaluation"
    )


class AuctionTrigger(Model):
    """Payload assembled when an autonomous auction must be triggered.

    Attributes:
        vehicle_id:     Vehicle that requires urgent charging.
        gps_lat/lon:    Last known position.
        battery_level:  Current SoC [0‑100 %].
        sla_urgency:    Urgency score driving the auction.
        cargo_type:     Cargo being carried.
        top3_stations:  Top 3 station IDs selected by Deal_Optimizer.
        timestamp:      Unix epoch seconds of trigger assembly.
    """

    vehicle_id: str = Field(
        ..., description="Unique vehicle identifier"
    )
    gps_lat: float = Field(
        ..., description="Current GPS latitude"
    )
    gps_lon: float = Field(
        ..., description="Current GPS longitude"
    )
    battery_level: float = Field(
        ..., description="Battery level at trigger time [0‑100 %]"
    )
    sla_urgency: float = Field(
        ..., description="SLA urgency score that triggered the auction [0.0‑1.0]"
    )
    cargo_type: str = Field(
        ..., description="Cargo type at trigger time"
    )
    top3_stations: list[str] = Field(
        default_factory=list, description="Top 3 target station IDs"
    )
    timestamp: float = Field(
        ..., description="Unix timestamp of trigger assembly"
    )


class YardHostPayload(Model):
    """Payload representing Yard Host Agent operational controls & capacity.

    Attributes:
        station_id:                 Unique station identifier.
        station_name:               Human-readable station/yard name.
        charger_status:             Operational status (Available, Busy, Offline).
        total_capacity_kw:          Total power capacity of the yard in kW.
        safety_buffer_percentage:   Reserved internal operational safety buffer (10% to 90%).
        listed_idle_capacity_kw:    Available power capacity listed on P2P marketplace in kW.
        available_power_kw:         Calculated available power for public auction.
        timestamp:                  Unix epoch seconds.
    """

    station_id: str = Field(..., description="Unique station identifier")
    station_name: str = Field(..., description="Human-readable station/yard name")
    charger_status: str = Field(..., description="Operational status")
    total_capacity_kw: float = Field(..., description="Total power capacity in kW")
    safety_buffer_percentage: float = Field(..., description="Safety buffer percentage [10.0 - 90.0]")
    listed_idle_capacity_kw: float = Field(..., description="Public idle capacity listed on marketplace in kW")
    available_power_kw: float = Field(..., description="Available charging power for public auction in kW")
    timestamp: float = Field(..., description="Unix timestamp of payload assembly")






# ======================================================================
# 2.  SLA_GUARDIAN — PERISHABILITY MATRIX & W_cargo WEIGHTS
# ======================================================================

_CARGO_PERISHABILITY: dict[str, float] = {
    # Cold Chain & Perishables
    "Pharmaceuticals / Vaccines":       1.00,
    "Medicines":                        1.00,
    "Frozen Foods / Ice Cream":         0.95,
    "Ice Cream":                        0.95,
    "Fresh Produce & Dairy":            0.75,
    # Time-Critical Logistics
    "Hazardous Materials / Chemicals":  0.85,
    "Automotive / Manufacturing Parts": 0.80,
    "Express E-Commerce Parcels":       0.70,
    # Standard / Non-Perishable Cargo
    "General Retail Freight":           0.40,
    "Dry Cargo":                        0.20,
    "Dry Bulk Goods / Grain":           0.20,
    "Construction Materials":           0.15,
}

_DEFAULT_PERISHABILITY: float = 0.50


# ======================================================================
# 3.  FLEET EV SYSTEM AGENT
# ======================================================================


class FleetEVSystemAgent(Agent):
    """Production‑grade Fleet EV System Agent.

    Responsibilities
    ----------------
    • Periodically monitors simulated (or real) battery SoC.
    • Runs the embedded **SLA_Guardian** algorithm that produces a
      dynamic ``urgency_score`` ∈ [0.0, 1.0] based on cargo
      perishability, delivery‑window pressure, and battery depletion.
    • When SoC < 15 % it logs a **critical** warning and autonomously
      assembles an ``AuctionTrigger`` payload.
    • Accepts external ``TelemetryUpdate`` messages and responds to
      incoming ``AuctionTrigger`` messages.

    Configuration is persisted in the agent's internal key‑value store:
    ``vehicle_id``, ``cargo_type``, ``total_window_minutes``,
    ``remaining_window_minutes``, ``battery_soc``, ``gps_lat``,
    ``gps_lon``.
    """

    def __init__(
        self,
        name: str = "fleet_ev_agent",
        seed: str | None = None,
        vehicle_id: str = "EV-001",
        cargo_type: str = "Frozen Foods / Ice Cream",
        total_delivery_window_minutes: float = 120.0,
        port: int = 8000,
        endpoint: str | list[str] | dict[str, dict] | None = None,
        log_level: int | str = logging.INFO,
        **kwargs: Any,
    ) -> None:
        # ── initialise the uagents Agent ────────────────────────────
        super().__init__(
            name=name,
            seed=seed,
            port=port,
            endpoint=endpoint,
            log_level=log_level,
            **kwargs,
        )

        # ── persist configuration for run‑time access ───────────────
        self._init_storage(
            vehicle_id=vehicle_id,
            cargo_type=cargo_type,
            total_window_minutes=total_delivery_window_minutes,
        )

        # ── register message & interval handlers ────────────────────
        self._register_handlers()

        self._logger.info(
            "FleetEVSystemAgent [%s] — online | "
            "vehicle=%s cargo=%s window=%.0f min battery=100%%",
            self.address[:16],
            vehicle_id,
            cargo_type,
            total_delivery_window_minutes,
        )

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _init_storage(
        self,
        vehicle_id: str,
        cargo_type: str,
        total_window_minutes: float,
    ) -> None:
        """Seed the key‑value store with vehicle configuration."""
        self.storage.set("vehicle_id", vehicle_id)
        self.storage.set("cargo_type", cargo_type)
        self.storage.set("total_window_minutes", total_window_minutes)
        self.storage.set("remaining_window_minutes", total_window_minutes)
        self.storage.set("battery_soc", 100.0)
        self.storage.set("gps_lat", 51.5074)  # default: London
        self.storage.set("gps_lon", -0.1278)

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        """Bind interval and message handlers to the agent instance."""

        # ── interval: battery monitoring (every 30 s) ────────────────
        @self.on_interval(period=30.0)
        async def _monitor_battery(ctx: Context) -> None:
            """Simulate battery discharge, check critical threshold,
            and autonomously assemble an ``AuctionTrigger`` if needed."""
            self._run_battery_check(ctx)

        # ── message: incoming telemetry ──────────────────────────────
        @self.on_message(model=TelemetryUpdate)
        async def _on_telemetry(
            ctx: Context,
            sender: str,
            msg: TelemetryUpdate,
        ) -> None:
            """Process external telemetry, persist state, and run an
            SLA evaluation."""
            self._handle_telemetry_update(ctx, sender, msg)

        # ── message: incoming auction trigger ────────────────────────
        @self.on_message(model=AuctionTrigger)
        async def _on_auction_trigger(
            ctx: Context,
            sender: str,
            msg: AuctionTrigger,
        ) -> None:
            """Log and acknowledge an incoming auction trigger."""
            ctx.logger.info(
                "📨 AuctionTrigger received from %s — "
                "vehicle=%s urgency=%.3f battery=%.1f%% cargo=%s",
                sender[:16],
                msg.vehicle_id,
                msg.sla_urgency,
                msg.battery_level,
                msg.cargo_type,
            )

    # ------------------------------------------------------------------
    # SLA_Guardian — urgency scoring algorithm
    # ------------------------------------------------------------------

    def _calculate_urgency_score(
        self,
        cargo_type: str,
        remaining_window_minutes: float,
        battery_soc: float,
    ) -> float:
        """Embedded **SLA_Guardian** algorithm.

        The urgency score equation:
        Urgency Score = (Battery Deficiency %) * 0.4 + (SLA Deadline Proximity) * 0.3 + W_cargo * 0.3

        Clamped to [0.0, 1.0].
        """
        total_window: float = (
            self.storage.get("total_window_minutes") or 120.0
        )

        w_cargo: float = _CARGO_PERISHABILITY.get(
            cargo_type, _DEFAULT_PERISHABILITY
        )

        # 1) SLA Deadline Proximity (0.0 to 1.0)
        elapsed_ratio: float = max(
            0.0, 1.0 - (remaining_window_minutes / max(total_window, 1.0))
        )
        deadline_proximity: float = min(1.0, elapsed_ratio)

        # 2) Battery Deficiency % (0.0 to 1.0)
        battery_deficiency: float = max(0.0, min(1.0, (100.0 - battery_soc) / 100.0))

        # Composite formula
        urgency: float = (battery_deficiency * 0.4) + (deadline_proximity * 0.3) + (w_cargo * 0.3)
        return round(max(0.0, min(1.0, urgency)), 4)


    # ------------------------------------------------------------------
    # Business-logic methods
    # ------------------------------------------------------------------

    def _run_battery_check(self, ctx: Context) -> None:
        """Simulate a battery discharge tick, persist state, evaluate
        SLA urgency, and — if the critical threshold is breached —
        assemble and dispatch an autonomous ``AuctionTrigger``."""

        # ── load current state from storage ──────────────────────────
        vehicle_id: str = str(self.storage.get("vehicle_id") or "EV-001")
        cargo_type: str = str(
            self.storage.get("cargo_type") or "Ice Cream"
        )
        battery_soc: float = float(
            self.storage.get("battery_soc") or 100.0
        )
        gps_lat: float = float(self.storage.get("gps_lat") or 51.5074)
        gps_lon: float = float(self.storage.get("gps_lon") or -0.1278)
        remaining_window: float = float(
            self.storage.get("remaining_window_minutes")
            or self.storage.get("total_window_minutes")
            or 120.0
        )

        # ── simulate discharge (0.5 % per 30 s) ──────────────────────
        battery_soc = max(0.0, battery_soc - 0.5)
        remaining_window = max(0.0, remaining_window - 0.5)
        self.storage.set("battery_soc", battery_soc)
        self.storage.set(
            "remaining_window_minutes", remaining_window
        )

        # ── compute SLA urgency ──────────────────────────────────────
        urgency: float = self._calculate_urgency_score(
            cargo_type=cargo_type,
            remaining_window_minutes=remaining_window,
            battery_soc=battery_soc,
        )

        # Build and persist an SLA evaluation record
        evaluation = SLAEvaluation(
            vehicle_id=vehicle_id,
            urgency_score=urgency,
            cargo_type=cargo_type,
            delivery_window_remaining_minutes=remaining_window,
            timestamp=time.time(),
        )
        self.storage.set(
            "last_sla_evaluation",
            evaluation.dict(),
        )

        ctx.logger.info(
            "📊 SLA evaluation | vehicle=%s SoC=%.1f%% "
            "window=%.0f min urgency=%.3f cargo=%s",
            vehicle_id,
            battery_soc,
            remaining_window,
            urgency,
            cargo_type,
        )

        # ── critical threshold check (SoC <= 50 %) ────────────────────
        if battery_soc <= 50.0:
            trigger = AuctionTrigger(
                vehicle_id=vehicle_id,
                gps_lat=gps_lat,
                gps_lon=gps_lon,
                battery_level=battery_soc,
                sla_urgency=urgency,
                cargo_type=cargo_type,
                timestamp=time.time(),
            )

            ctx.logger.critical(
                "⚠️  CRITICAL — Battery SoC (%.1f%%) at or below 50%% "
                "threshold for vehicle %s | Assembled AuctionTrigger: "
                "urgency=%.3f, pos=(%.4f, %.4f), cargo=%s",
                battery_soc,
                vehicle_id,
                urgency,
                gps_lat,
                gps_lon,
                cargo_type,
            )

            # Persist the trigger for observability
            self.storage.set(
                "last_auction_trigger",
                trigger.dict(),
            )

    def _handle_telemetry_update(
        self,
        ctx: Context,
        sender: str,
        msg: TelemetryUpdate,
    ) -> None:
        """Process an external ``TelemetryUpdate``, persist the fresh
        readings, and immediately run an SLA evaluation."""

        ctx.logger.info(
            "📡 Telemetry from %s | vehicle=%s SoC=%.1f%% "
            "cargo=%s window=%.0f min",
            sender[:16],
            msg.vehicle_id,
            msg.battery_soc,
            msg.cargo_type,
            msg.delivery_window_remaining_minutes,
        )

        # Persist incoming telemetry
        self.storage.set("vehicle_id", msg.vehicle_id)
        self.storage.set("cargo_type", msg.cargo_type)
        self.storage.set("battery_soc", msg.battery_soc)
        self.storage.set("gps_lat", msg.gps_lat)
        self.storage.set("gps_lon", msg.gps_lon)
        self.storage.set(
            "remaining_window_minutes",
            msg.delivery_window_remaining_minutes,
        )

        # Run SLA evaluation
        urgency: float = self._calculate_urgency_score(
            cargo_type=msg.cargo_type,
            remaining_window_minutes=msg.delivery_window_remaining_minutes,
            battery_soc=msg.battery_soc,
        )

        evaluation = SLAEvaluation(
            vehicle_id=msg.vehicle_id,
            urgency_score=urgency,
            cargo_type=msg.cargo_type,
            delivery_window_remaining_minutes=msg.delivery_window_remaining_minutes,
            timestamp=time.time(),
        )
        self.storage.set(
            "last_sla_evaluation",
            evaluation.dict(),
        )

        ctx.logger.info(
            "⚡ SLA evaluation complete | vehicle=%s urgency=%.3f",
            msg.vehicle_id,
            urgency,
        )

        # Trigger auction if SoC <= 50%
        if msg.battery_soc <= 50.0:
            trigger = AuctionTrigger(
                vehicle_id=msg.vehicle_id,
                gps_lat=msg.gps_lat,
                gps_lon=msg.gps_lon,
                battery_level=msg.battery_soc,
                sla_urgency=urgency,
                cargo_type=msg.cargo_type,
                timestamp=time.time(),
            )

            ctx.logger.critical(
                "⚠️  CRITICAL — Incoming telemetry reports SoC "
                "at or below 50%% for %s | Assembled AuctionTrigger: "
                "urgency=%.3f",
                msg.vehicle_id,
                urgency,
            )

            self.storage.set(
                "last_auction_trigger",
                trigger.dict(),
            )



    # ------------------------------------------------------------------
    # Test helper — build a minimal Context mock for smoke tests
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context() -> Context:
        """Return a minimal ``Context``-like object for test usage.

        The production agent's ``Context`` is normally provided by the
        uagents framework inside handler functions.  This static method
        creates a lightweight stand-in that exposes a ``logger`` with
        ``info`` / ``critical`` / ``warning`` methods, enabling unit
        tests (e.g. ``test_fleet_agent.py``) to call business-logic
        methods without a running agent loop.
        """
        import logging

        _logger = logging.getLogger("fleet_ev.test_context")
        _logger.setLevel(logging.DEBUG)

        class _MockContext:
            """Duck-typed stand-in for ``uagents.Context``."""

            logger = _logger
            # Minimal ``storage`` access — delegates to nothing,
            # because the actual storage lives on the agent instance.
            storage = None  # type: ignore[assignment]

        return _MockContext()  # type: ignore[return-value]


# ======================================================================
# 4.  STANDALONE EXECUTION
# ======================================================================

if __name__ == "__main__":
    # ── Instantiate with default Ice‑Cream configuration ──────────────
    agent = FleetEVSystemAgent(
        name="fleet_ev_agent",
        seed="chargeverse-fleet-ev-seed-001",
        vehicle_id="EV-001",
        cargo_type="Ice Cream",
        total_delivery_window_minutes=120.0,
        port=8000,
        log_level=logging.INFO,
    )
    agent.run()

