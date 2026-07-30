"""
ChargeVerse — Broker / Auctioneer Agent
========================================
Double-blind marketplace clearing engine sitting between the buyer side
(FleetEVSystemAgent + SLAGuardianAgent) and the seller side (YardHostAgents /
Public Charging Stations).

Architecture
------------
* Receives an ``AuctionRequestPayload`` from the SLA Guardian.
* Collects raw ``StationOffer`` objects from all registered Yard Host Agents.
* Executes a **Double-Blind Clearing Algorithm** that:
    1. Rejects stations with available power below a minimum threshold (15 kW).
    2. Rejects Private Yards whose cargo-weight SLA threshold is not met by the buyer.
    3. Applies a small platform market-clearing fee (+2 %) to all eligible tariffs.
* Returns ``List[ClearedBid]`` — a mix of eligible and rejected bids — to the
  Deal Optimizer Agent for final multi-criteria weighted scoring.

Usage
-----
    from broker_agent import AuctionRequestPayload, BrokerAuctioneerAgent

    broker = BrokerAuctioneerAgent(market_fee_percent=2.0)
    cleared = broker.clear_auction(request_payload, station_offers)
    eligible = [b for b in cleared if b.eligible]
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

_log = logging.getLogger("chargeverse.broker")


# ======================================================================
# PYDANTIC DATA MODELS
# ======================================================================


class AuctionRequestPayload(BaseModel):
    """Buyer-side request assembled by the SLA Guardian and handed to the
    Broker Auctioneer for market clearing.

    Attributes:
        vehicle_id:           Unique vehicle identifier.
        current_soc:          Current battery State of Charge [0–100 %].
        urgency_score:        Composite SLA urgency score [0.0–1.0].
        cargo_weight_factor:  Cargo perishability weight W_cargo [0.0–1.0].
        required_kwh:         Estimated kWh needed to reach the charging station
                              and complete an adequate charge cycle.
        timestamp:            Unix epoch seconds when the payload was assembled.
    """

    vehicle_id: str = Field(..., description="Unique vehicle identifier")
    current_soc: float = Field(..., ge=0.0, le=100.0, description="Battery SoC [0–100 %]")
    urgency_score: float = Field(..., ge=0.0, le=1.0, description="SLA urgency score [0–1]")
    cargo_weight_factor: float = Field(
        ..., ge=0.0, le=1.0, description="Cargo perishability weight W_cargo [0–1]"
    )
    required_kwh: float = Field(default=0.0, ge=0.0, description="Estimated kWh required")
    timestamp: float = Field(default_factory=time.time, description="Unix epoch seconds")


class StationOffer(BaseModel):
    """Raw offer submitted by a Yard Host Agent / Public Charging Station.

    Attributes:
        station_id:               Unique station identifier.
        facility_name:            Human-readable name.
        facility_type:            ``PUBLIC_STATION`` or ``PRIVATE_YARD``.
        available_power_kw:       Uncommitted power available for auction [kW].
        tariff_per_kwh:           Base energy tariff before any platform fee [$/kWh].
        queue_delay_mins:         Estimated queue wait time at this station [minutes].
        min_cargo_weight_required:
            Minimum cargo W_cargo required to access a Private Yard.
            Defaults to 0.0 (no restriction — applicable to public stations).
    """

    station_id: str = Field(..., description="Unique station identifier")
    facility_name: str = Field(..., description="Human-readable station name")
    facility_type: str = Field(..., description="PUBLIC_STATION or PRIVATE_YARD")
    available_power_kw: float = Field(..., ge=0.0, description="Available power [kW]")
    tariff_per_kwh: float = Field(..., ge=0.0, description="Base tariff [$/kWh]")
    queue_delay_mins: float = Field(default=0.0, ge=0.0, description="Queue wait [minutes]")
    min_cargo_weight_required: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum W_cargo for Private Yard access",
    )


class ClearedBid(BaseModel):
    """Broker-processed bid result returned after double-blind clearing.

    Attributes:
        station_id:         Unique station identifier.
        facility_name:      Human-readable name.
        facility_type:      ``PUBLIC_STATION`` or ``PRIVATE_YARD``.
        available_power_kw: Available power at this station [kW].
        effective_tariff:   Platform-fee-adjusted tariff [$/kWh] (only valid when
                            ``eligible=True``; equals raw tariff when ``eligible=False``).
        queue_delay_mins:   Queue wait time [minutes].
        eligible:           ``True`` if this station passed all clearing rules.
        rejection_reason:   Human-readable reason string when ``eligible=False``;
                            ``None`` for eligible bids.
    """

    station_id: str = Field(..., description="Unique station identifier")
    facility_name: str = Field(..., description="Human-readable station name")
    facility_type: str = Field(..., description="PUBLIC_STATION or PRIVATE_YARD")
    available_power_kw: float = Field(..., description="Available power [kW]")
    effective_tariff: float = Field(..., description="Platform-fee-adjusted tariff [$/kWh]")
    queue_delay_mins: float = Field(default=0.0, description="Queue wait [minutes]")
    eligible: bool = Field(..., description="True if passed all clearing rules")
    rejection_reason: Optional[str] = Field(
        default=None, description="Rejection reason; None when eligible"
    )


# ======================================================================
# BROKER AUCTIONEER AGENT
# ======================================================================


# Private Yard minimum cargo weight thresholds.
# Any Private Yard not explicitly listed defaults to 0.40 (general contracted cargo).
_PRIVATE_YARD_MIN_CARGO: dict[str, float] = {
    "station_a": 0.40,  # BLR Solar Yard — general contracted access
    "station_c": 0.40,  # Whitefield Tech Hub
    "station_f": 0.40,  # Hosur Freight Terminal
    "station_g": 0.40,  # Peenya EV Logistics Hub
}

# Absolute minimum available power to participate in any auction
_MIN_POWER_KW: float = 15.0


class BrokerAuctioneerAgent:
    """Stateless Double-Blind Market Clearing Engine.

    The broker is intentionally stateless — it does not retain bid history
    between auctions.  Each call to ``clear_auction`` produces a fresh,
    independent clearing result.

    Parameters
    ----------
    market_fee_percent : float
        Platform transaction fee added on top of the station's base tariff
        for all *eligible* bids.  Default: 2.0 %.
    """

    def __init__(self, market_fee_percent: float = 2.0) -> None:
        self.market_fee_percent = market_fee_percent
        _log.info(
            "BrokerAuctioneerAgent initialised — platform fee=%.1f%%",
            self.market_fee_percent,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_auction(
        self,
        request: AuctionRequestPayload,
        station_offers: List[Dict[str, Any]],
    ) -> List[ClearedBid]:
        """Execute the double-blind clearing algorithm.

        Clearing Rules (applied in order):
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        **Rule 1 — Power Availability Check**
            Stations with ``available_power_kw < 15 kW`` are rejected.
            Rationale: A sub-15 kW source cannot meaningfully serve a heavy EV
            cargo truck in an acceptable timeframe.

        **Rule 2 — Private Yard Cargo SLA Protection**
            Private Yards gate access based on cargo urgency.  If the buyer's
            ``cargo_weight_factor`` is below the yard's
            ``min_cargo_weight_required`` threshold, the yard is rejected.
            Rationale: Private yards are reserved for contracted / high-SLA
            cargo operators; low-priority freight must use public stations.

        **Rule 3 — Platform Clearing Fee Application**
            Eligible bids receive a ``market_fee_percent`` surcharge on the
            raw tariff, producing the ``effective_tariff`` that the buyer
            actually pays. This fee funds the ChargeVerse platform operations.

        Parameters
        ----------
        request : AuctionRequestPayload
            Buyer-side auction request from the SLA Guardian.
        station_offers : List[Dict]
            Raw station offer dicts.  Each dict must contain at minimum:
            ``station_id``, ``facility_name``, ``facility_type``,
            ``available_power_kw``, ``tariff_per_kwh``, ``queue_delay_mins``.

        Returns
        -------
        List[ClearedBid]
            All bids (eligible and rejected), ordered: eligible first, then
            rejected.  Within each group, insertion order is preserved.
        """
        eligible_bids: List[ClearedBid] = []
        rejected_bids: List[ClearedBid] = []

        for offer in station_offers:
            sid = offer.get("station_id", "unknown")
            fname = offer.get("facility_name", sid)
            ftype = offer.get("facility_type", "PUBLIC_STATION")
            avail_kw = float(offer.get("available_power_kw", 0.0))
            base_tariff = float(offer.get("tariff_per_kwh", 0.0))
            queue_mins = float(offer.get("queue_delay_mins", 0.0))
            min_cargo = float(
                offer.get(
                    "min_cargo_weight_required",
                    _PRIVATE_YARD_MIN_CARGO.get(sid, 0.40)
                    if ftype == "PRIVATE_YARD"
                    else 0.0,
                )
            )

            # ── Rule 1: Power Availability Check ─────────────────────
            if avail_kw < _MIN_POWER_KW:
                reason = (
                    f"Available power {avail_kw:.1f} kW is below the "
                    f"{_MIN_POWER_KW:.0f} kW minimum threshold"
                )
                _log.info("BROKER REJECT [%s] — %s", sid, reason)
                rejected_bids.append(
                    ClearedBid(
                        station_id=sid,
                        facility_name=fname,
                        facility_type=ftype,
                        available_power_kw=avail_kw,
                        effective_tariff=base_tariff,
                        queue_delay_mins=queue_mins,
                        eligible=False,
                        rejection_reason=reason,
                    )
                )
                continue

            # ── Rule 2: Private Yard Cargo SLA Protection ────────────
            if ftype == "PRIVATE_YARD" and request.cargo_weight_factor < min_cargo:
                reason = (
                    f"Cargo W_cargo {request.cargo_weight_factor:.2f} is below "
                    f"Private Yard SLA threshold {min_cargo:.2f}"
                )
                _log.info("BROKER REJECT [%s] — %s", sid, reason)
                rejected_bids.append(
                    ClearedBid(
                        station_id=sid,
                        facility_name=fname,
                        facility_type=ftype,
                        available_power_kw=avail_kw,
                        effective_tariff=base_tariff,
                        queue_delay_mins=queue_mins,
                        eligible=False,
                        rejection_reason=reason,
                    )
                )
                continue

            # ── Rule 3: Valid Bid — Apply Platform Clearing Fee ───────
            fee_adjusted_tariff = round(
                base_tariff * (1.0 + (self.market_fee_percent / 100.0)), 4
            )
            _log.info(
                "BROKER CLEARED [%s] — power=%.1f kW tariff=$%.4f→$%.4f (%.1f%% fee)",
                sid,
                avail_kw,
                base_tariff,
                fee_adjusted_tariff,
                self.market_fee_percent,
            )
            eligible_bids.append(
                ClearedBid(
                    station_id=sid,
                    facility_name=fname,
                    facility_type=ftype,
                    available_power_kw=avail_kw,
                    effective_tariff=fee_adjusted_tariff,
                    queue_delay_mins=queue_mins,
                    eligible=True,
                    rejection_reason=None,
                )
            )

        _log.info(
            "BrokerAuctioneerAgent clearing complete — eligible=%d rejected=%d "
            "vehicle=%s urgency=%.3f cargo_weight=%.2f",
            len(eligible_bids),
            len(rejected_bids),
            request.vehicle_id,
            request.urgency_score,
            request.cargo_weight_factor,
        )

        # Return eligible first so downstream agents can slice [:n] safely
        return eligible_bids + rejected_bids

    def build_payload(
        self,
        request: AuctionRequestPayload,
        cleared_bids: List[ClearedBid],
    ) -> Dict[str, Any]:
        """Build a serialisable payload dict for UI display and observability.

        Parameters
        ----------
        request : AuctionRequestPayload
            The buyer request that was cleared.
        cleared_bids : List[ClearedBid]
            Output from ``clear_auction()``.

        Returns
        -------
        Dict[str, Any]
            Human-readable clearing summary keyed for Streamlit UI rendering.
        """
        eligible = [b for b in cleared_bids if b.eligible]
        rejected = [b for b in cleared_bids if not b.eligible]

        return {
            "agent": "Broker_Auctioneer Agent",
            "action": "DoubleBlindMarketCleared",
            "vehicle_id": request.vehicle_id,
            "urgency_score": request.urgency_score,
            "cargo_weight_factor": request.cargo_weight_factor,
            "market_fee_percent": self.market_fee_percent,
            "total_offers_received": len(cleared_bids),
            "eligible_count": len(eligible),
            "rejected_count": len(rejected),
            "eligible_stations": [
                {
                    "station_id": b.station_id,
                    "facility_name": b.facility_name,
                    "facility_type": b.facility_type,
                    "available_power_kw": b.available_power_kw,
                    "effective_tariff": b.effective_tariff,
                    "queue_delay_mins": b.queue_delay_mins,
                }
                for b in eligible
            ],
            "rejected_stations": [
                {
                    "station_id": b.station_id,
                    "facility_name": b.facility_name,
                    "facility_type": b.facility_type,
                    "available_power_kw": b.available_power_kw,
                    "rejection_reason": b.rejection_reason,
                }
                for b in rejected
            ],
            "timestamp": round(time.time(), 2),
        }
