"""
ChargeVerse — Dynamic Pricing Agent
=====================================
Real-time Time-of-Use (ToU) & Congestion Tariff Engine sitting between the
SLA Guardian and the Broker Auctioneer in the 6-agent pipeline.

Architecture
------------
* Receives raw base tariffs + live station metrics (queue length, charger count,
  available power) for every station entering the auction.
* Computes a dynamic price adjusted for:
    1. **Time-of-Use (ToU)** — Peak / Off-Peak / Standard multiplier.
    2. **Bay Utilisation Congestion Surcharge** — High-utilisation surge (+20 %)
       or idle Private Yard discount (−10 %).
* Enforces regulatory upper (₹ 25 / kWh) and lower (₹ 8 / kWh) price bounds.
* Classifies each adjusted tariff into a Pricing Tier:
    ``PEAK_SURGE`` · ``STANDARD`` · ``OFF_PEAK_DISCOUNT``
* Returns ``List[DynamicTariffOutput]`` to be injected into the station-offer
  payloads consumed by the ``BrokerAuctioneerAgent`` and ``DealOptimizerAgent``.

Usage
-----
    from dynamic_pricing_agent import DynamicPricingAgent, DynamicTariffOutput

    agent  = DynamicPricingAgent(min_tariff_floor=8.0, max_tariff_cap=25.0)
    results = agent.compute_dynamic_tariffs(station_bids)
    tariff_map = {r.station_id: r.dynamic_tariff for r in results}
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

_log = logging.getLogger("chargeverse.dynamic_pricing")


# ======================================================================
# PYDANTIC DATA MODELS
# ======================================================================


class PricingInputPayload(BaseModel):
    """Input payload describing a single station's current market state.

    Attributes:
        station_id:           Unique station identifier.
        facility_name:        Human-readable name.
        facility_type:        ``PUBLIC_STATION`` or ``PRIVATE_YARD``.
        base_tariff:          Raw base price [$/kWh or ₹/kWh] from stations_db.
        current_queue_length: Number of vehicles currently queued.
        total_chargers:       Total charger bays at the station.
        available_power_kw:   Available uncommitted power [kW].
    """

    station_id: str = Field(..., description="Unique station identifier")
    facility_name: str = Field(..., description="Human-readable station name")
    facility_type: str = Field(..., description="PUBLIC_STATION or PRIVATE_YARD")
    base_tariff: float = Field(..., ge=0.0, description="Base price [$/kWh]")
    current_queue_length: int = Field(default=0, ge=0, description="Queued vehicles")
    total_chargers: int = Field(default=5, ge=1, description="Total charger bays")
    available_power_kw: float = Field(..., ge=0.0, description="Available power [kW]")


class DynamicTariffOutput(BaseModel):
    """Broker-ready tariff result after dynamic pricing adjustment.

    Attributes:
        station_id:           Unique station identifier.
        facility_name:        Human-readable station name.
        facility_type:        ``PUBLIC_STATION`` or ``PRIVATE_YARD``.
        base_tariff:          Original base tariff before any adjustment.
        dynamic_tariff:       Final price-adjusted tariff (clamped to bounds).
        tou_multiplier:       Time-of-Use multiplier applied (0.85 / 1.00 / 1.25).
        congestion_surcharge: Surcharge (positive) or discount (negative) in $/kWh.
        utilization_rate:     Bay utilisation ratio [0.0–1.0] at time of pricing.
        pricing_tier:         ``OFF_PEAK_DISCOUNT`` · ``STANDARD`` · ``PEAK_SURGE``
        timestamp:            Unix epoch when pricing was computed.
    """

    station_id: str = Field(..., description="Unique station identifier")
    facility_name: str = Field(..., description="Human-readable station name")
    facility_type: str = Field(..., description="PUBLIC_STATION or PRIVATE_YARD")
    base_tariff: float = Field(..., description="Original base tariff [$/kWh]")
    dynamic_tariff: float = Field(..., description="Final adjusted tariff [$/kWh]")
    tou_multiplier: float = Field(..., description="ToU multiplier applied")
    congestion_surcharge: float = Field(..., description="Congestion delta [$/kWh]")
    utilization_rate: float = Field(default=0.0, description="Bay utilisation [0–1]")
    pricing_tier: str = Field(
        ..., description="OFF_PEAK_DISCOUNT | STANDARD | PEAK_SURGE"
    )
    timestamp: float = Field(default_factory=time.time, description="Unix epoch")


# ======================================================================
# TIME-OF-USE SCHEDULE
# ======================================================================

# (start_hour_inclusive, end_hour_inclusive, multiplier, label)
_TOU_SCHEDULE: list[tuple[int, int, float, str]] = [
    (0,  6,  0.85, "OFF_PEAK"),   # Midnight → 06:00 — cheap overnight grid
    (9,  12, 1.25, "PEAK"),       # Morning peak — grid demand surge
    (18, 22, 1.25, "PEAK"),       # Evening peak — commuter + AC load spike
]
_TOU_STANDARD_MULTIPLIER = 1.00

# Congestion thresholds
_HIGH_UTIL_THRESHOLD    = 0.80   # Bay utilisation above which surge applies
_HIGH_UTIL_SURCHARGE_PC = 0.20   # +20 % on base tariff
_IDLE_YARD_DISCOUNT_PC  = 0.10   # −10 % on base tariff for idle private yards


# ======================================================================
# DYNAMIC PRICING AGENT
# ======================================================================


class DynamicPricingAgent:
    """Stateless Time-of-Use & Congestion Dynamic Tariff Engine.

    Parameters
    ----------
    min_tariff_floor : float
        Absolute lower bound for any published tariff.  Default: 8.0 $/kWh.
    max_tariff_cap : float
        Absolute upper bound (regulatory ceiling).  Default: 25.0 $/kWh.
    """

    def __init__(
        self,
        min_tariff_floor: float = 8.0,
        max_tariff_cap: float = 25.0,
    ) -> None:
        self.min_tariff_floor = min_tariff_floor
        self.max_tariff_cap   = max_tariff_cap
        _log.info(
            "DynamicPricingAgent initialised — floor=%.2f cap=%.2f",
            self.min_tariff_floor,
            self.max_tariff_cap,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_tou_multiplier(
        self, hour: Optional[int] = None
    ) -> tuple[float, str]:
        """Return (multiplier, band_label) for the given hour.

        Parameters
        ----------
        hour : int | None
            Hour of day [0-23].  If ``None``, uses ``datetime.datetime.now().hour``.
        """
        h = hour if hour is not None else datetime.datetime.now().hour
        for start, end, mult, label in _TOU_SCHEDULE:
            if start <= h <= end:
                return mult, label
        return _TOU_STANDARD_MULTIPLIER, "STANDARD"

    def compute_dynamic_tariffs(
        self,
        station_bids: List[Dict[str, Any]],
        hour: Optional[int] = None,
    ) -> List[DynamicTariffOutput]:
        """Compute dynamic tariff for every station in *station_bids*.

        Pricing Rules (applied in order)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        **Rule 1 — Time-of-Use Multiplier**
            Apply ToU schedule multiplier to the base tariff.

        **Rule 2 — Bay Congestion Surcharge / Idle Discount**
            * Utilisation > 80 % → +20 % surcharge on base tariff.
            * Utilisation == 0 AND ``PRIVATE_YARD`` → −10 % idle yard discount.

        **Rule 3 — Bounds Clamping**
            ``final = clamp(calculated, min_tariff_floor, max_tariff_cap)``

        **Rule 4 — Tier Classification**
            * ``PEAK_SURGE``       — final > base × 1.15
            * ``OFF_PEAK_DISCOUNT``— final < base
            * ``STANDARD``         — otherwise

        Parameters
        ----------
        station_bids : list[dict]
            Each dict must contain: ``station_id``, ``facility_name``,
            ``facility_type``, ``tariff_per_kwh``, ``queue_length``,
            ``available_power_kw``.  Optional: ``total_chargers``.
        hour : int | None
            Override hour for unit-testing.  ``None`` uses wall-clock hour.

        Returns
        -------
        List[DynamicTariffOutput]
            One result per input bid, preserving insertion order.
        """
        tou_mult, _tou_band = self.calculate_tou_multiplier(hour)
        results: List[DynamicTariffOutput] = []

        for bid in station_bids:
            sid       = bid.get("station_id", "unknown")
            fname     = bid.get("facility_name", sid)
            ftype     = bid.get("facility_type", "PUBLIC_STATION")
            base_rate = float(bid.get("tariff_per_kwh", 12.0))
            queue     = int(bid.get("queue_length", bid.get("current_queue_length", 0)))
            capacity  = int(bid.get("total_chargers", 5))

            # ── Rule 1: Time-of-Use ───────────────────────────────────
            tou_adjusted = base_rate * tou_mult

            # ── Rule 2: Congestion / Idle Surcharge ───────────────────
            util_rate = queue / max(capacity, 1)
            congestion_surcharge = 0.0

            if util_rate > _HIGH_UTIL_THRESHOLD:
                congestion_surcharge = base_rate * _HIGH_UTIL_SURCHARGE_PC
            elif util_rate == 0.0 and ftype == "PRIVATE_YARD":
                congestion_surcharge = -(base_rate * _IDLE_YARD_DISCOUNT_PC)

            calculated_tariff = tou_adjusted + congestion_surcharge

            # ── Rule 3: Bounds Clamping ───────────────────────────────
            final_tariff = round(
                max(self.min_tariff_floor, min(calculated_tariff, self.max_tariff_cap)),
                4,
            )

            # ── Rule 4: Tier Classification ───────────────────────────
            if final_tariff > base_rate * 1.15:
                tier = "PEAK_SURGE"
            elif final_tariff < base_rate:
                tier = "OFF_PEAK_DISCOUNT"
            else:
                tier = "STANDARD"

            _log.info(
                "DYNAMIC PRICE [%s] base=%.4f tou=×%.2f surge=%.4f → final=%.4f [%s]",
                sid, base_rate, tou_mult, congestion_surcharge, final_tariff, tier,
            )

            results.append(
                DynamicTariffOutput(
                    station_id=sid,
                    facility_name=fname,
                    facility_type=ftype,
                    base_tariff=round(base_rate, 4),
                    dynamic_tariff=final_tariff,
                    tou_multiplier=tou_mult,
                    congestion_surcharge=round(congestion_surcharge, 4),
                    utilization_rate=round(util_rate, 4),
                    pricing_tier=tier,
                )
            )

        _log.info(
            "DynamicPricingAgent complete — %d stations priced | ToU=×%.2f",
            len(results),
            tou_mult,
        )
        return results

    def build_payload(
        self,
        results: List[DynamicTariffOutput],
        tou_multiplier: float,
    ) -> Dict[str, Any]:
        """Build a serialisable summary payload for UI display & observability.

        Parameters
        ----------
        results : List[DynamicTariffOutput]
            Output from ``compute_dynamic_tariffs()``.
        tou_multiplier : float
            The ToU multiplier that was applied this cycle.

        Returns
        -------
        Dict[str, Any]
            Human-readable pricing summary keyed for Streamlit UI rendering.
        """
        tier_counts = {"PEAK_SURGE": 0, "STANDARD": 0, "OFF_PEAK_DISCOUNT": 0}
        for r in results:
            tier_counts[r.pricing_tier] = tier_counts.get(r.pricing_tier, 0) + 1

        # Determine current hour band label
        h = datetime.datetime.now().hour
        _, band_label = self.calculate_tou_multiplier(h)

        return {
            "agent": "Dynamic_Pricing Agent",
            "action": "DynamicTariffComputed",
            "tou_multiplier": tou_multiplier,
            "tou_band": band_label,
            "current_hour": h,
            "min_tariff_floor": self.min_tariff_floor,
            "max_tariff_cap": self.max_tariff_cap,
            "total_stations_priced": len(results),
            "tier_counts": tier_counts,
            "station_pricing": [
                {
                    "station_id":         r.station_id,
                    "facility_name":      r.facility_name,
                    "facility_type":      r.facility_type,
                    "base_tariff":        r.base_tariff,
                    "dynamic_tariff":     r.dynamic_tariff,
                    "tou_multiplier":     r.tou_multiplier,
                    "congestion_surcharge": r.congestion_surcharge,
                    "utilization_rate":   r.utilization_rate,
                    "pricing_tier":       r.pricing_tier,
                }
                for r in results
            ],
            "timestamp": round(time.time(), 2),
        }
