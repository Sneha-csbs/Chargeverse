"""
ChargeVerse — Station Reputation Agent
========================================
Software-only Historical Quality & Trust Accounting Engine sitting between
the Broker Auctioneer and Deal Optimizer in the autonomous pipeline.

Architecture
------------
* Evaluates station user ratings and operational uptime percentage stored in stations_db.json.
* Computes dynamic trust multiplier:
    Reputation Multiplier = 1.0 + Rating Adjustment + Uptime Penalty
* Multipliers:
    - Rating >= 4.5★: +5% Reliability Bonus (+0.05)
    - Rating 3.5★ - 4.4★: Neutral (0.00)
    - Rating < 3.5★: -10% Trust Penalty (-0.10)
    - Uptime < 90%: -5% Charger Failure Penalty (-0.05)
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from pydantic import BaseModel, Field

_log = logging.getLogger("chargeverse.reputation")


class ReputationScorePayload(BaseModel):
    station_id: str = Field(..., description="Target station ID")
    facility_name: str = Field(..., description="Station facility name")
    user_rating: float = Field(..., description="Historical user rating (1.0 to 5.0)")
    uptime_pct: float = Field(..., description="Charger operational uptime percentage")
    reputation_multiplier: float = Field(..., description="Final combined trust score multiplier")
    badge_label: str = Field(..., description="User-facing badge label")
    explanation: str = Field(..., description="Human-readable breakdown explanation")


class StationReputationAgent:
    """Software-only Historical Quality & Trust Accounting Engine."""

    def evaluate_station_reputation(self, station_data: Dict[str, Any]) -> ReputationScorePayload:
        sid = str(station_data.get("station_id", station_data.get("id", "ST-000")))
        name = str(station_data.get("facility_name", station_data.get("name", "Charging Station")))
        rating = float(station_data.get("rating", station_data.get("user_rating", 4.2)))
        uptime = float(station_data.get("uptime_pct", station_data.get("uptime", 98.0)))

        rating_adj = 0.0
        uptime_adj = 0.0

        # 1. Evaluate User Rating
        if rating >= 4.5:
            rating_adj = 0.05
            label = "⭐ HIGH-RELIABILITY HOST (+5% Score Boost)"
            desc = f"Excellent track record ({rating:.1f}★). Prioritized in auction ranking."
        elif rating < 3.5:
            rating_adj = -0.10
            label = "⚠️ LOW-RATING HOST (-10% Trust Penalty)"
            desc = f"Historical quality issues reported ({rating:.1f}★). Bid score penalized."
        else:
            rating_adj = 0.00
            label = "👍 STANDARD VERIFIED HOST"
            desc = f"Reliable operational rating ({rating:.1f}★)."

        # 2. Evaluate Uptime Metric
        if uptime < 90.0:
            uptime_adj = -0.05
            desc += f" Warning: Reduced charger uptime ({uptime:.1f}%)."

        total_multiplier = round(1.0 + rating_adj + uptime_adj, 2)

        _log.info(
            "Station Reputation Evaluated [%s]: Rating=%.1f★ Uptime=%.1f%% Multiplier=%.2fx",
            sid, rating, uptime, total_multiplier
        )

        return ReputationScorePayload(
            station_id=sid,
            facility_name=name,
            user_rating=rating,
            uptime_pct=uptime,
            reputation_multiplier=total_multiplier,
            badge_label=label,
            explanation=desc
        )
