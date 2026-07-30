"""
ChargeVerse — FinTech Settlement Agent
========================================
Software-only Financial Escrow & GST Tax Invoicing Engine sitting at Step 8
of the autonomous execution pipeline.

Architecture
------------
* Receives winning auction deal payload and GatePassPayload.
* Computes itemized financial ledger:
    - Base Energy Cost (Energy kWh × Dynamic Tariff per kWh)
    - Platform Clearing Fee (2% of base energy cost)
    - GST Tax (18% tax on base energy cost + platform fee)
    - Total Pre-Authorization Amount
* Manages virtual fleet wallet escrow balance.
* Generates an itemized Pydantic v2 InvoiceBreakdown record.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

_log = logging.getLogger("chargeverse.fintech")


class InvoiceBreakdown(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction ID")
    pass_id: str = Field(..., description="Gate pass ID")
    vehicle_id: str = Field(..., description="Vehicle ID")
    station_name: str = Field(..., description="Charging station facility name")
    energy_kwh: float = Field(..., description="Required energy [kWh]")
    tariff_per_kwh: float = Field(..., description="Effective tariff [₹/kWh]")
    base_energy_cost: float = Field(..., description="Base energy cost [₹]")
    platform_fee: float = Field(..., description="2% platform clearing fee [₹]")
    tax_gst_18_percent: float = Field(..., description="18% GST tax amount [₹]")
    total_charged: float = Field(..., description="Total pre-authorized amount [₹]")
    wallet_balance_remaining: float = Field(..., description="Fleet wallet balance remaining [₹]")
    escrow_status: str = Field(default="SETTLED_IN_ESCROW", description="Escrow status")
    timestamp: str = Field(..., description="Formatted timestamp string")


class FinTechSettlementAgent:
    """Non-breaking software-only FinTech Escrow & Invoicing Engine."""

    def __init__(self, initial_wallet_balance: float = 15000.00) -> None:
        self.tax_rate = 0.18  # 18% GST for EV Charging Services in India
        self.initial_wallet_balance = initial_wallet_balance
        _log.info("FinTechSettlementAgent initialised.")

    def execute_settlement(
        self,
        gate_pass_data: Dict[str, Any],
        winning_deal: Dict[str, Any],
        current_wallet_balance: float = 15000.00
    ) -> InvoiceBreakdown:
        """Calculates itemized financial ledger and executes virtual wallet payment."""
        # Extract vehicle and station data safely
        pass_id = gate_pass_data.get("pass_id", "#808-GATE-PASS")
        vehicle_id = gate_pass_data.get("vehicle_id", winning_deal.get("vehicle_id", "EV-CV-001"))
        station_name = winning_deal.get("facility_name", winning_deal.get("name", "Charging Station"))

        required_kwh = float(winning_deal.get("required_kwh", 45.0))
        tariff = float(winning_deal.get("effective_tariff", winning_deal.get("price_per_kwh", winning_deal.get("tariff_per_kwh", 12.0))))

        # 1. Financial Arithmetic
        base_cost = round(required_kwh * tariff, 2)
        platform_fee = round(base_cost * 0.02, 2)  # 2% platform transaction fee
        tax_gst = round((base_cost + platform_fee) * self.tax_rate, 2)
        total_amount = round(base_cost + platform_fee + tax_gst, 2)

        # 2. Virtual Wallet Ledger Processing
        new_balance = round(current_wallet_balance - total_amount, 2)
        tx_id = f"TXN-BLR-{random.randint(100000, 999999)}"
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S IST", time.localtime())

        _log.info("FinTech Settlement Executed: TxID=%s Total=₹%.2f Balance=₹%.2f", tx_id, total_amount, new_balance)

        return InvoiceBreakdown(
            transaction_id=tx_id,
            pass_id=pass_id,
            vehicle_id=vehicle_id,
            station_name=station_name,
            energy_kwh=required_kwh,
            tariff_per_kwh=tariff,
            base_energy_cost=base_cost,
            platform_fee=platform_fee,
            tax_gst_18_percent=tax_gst,
            total_charged=total_amount,
            wallet_balance_remaining=max(0.0, new_balance),
            escrow_status="SETTLED_IN_ESCROW",
            timestamp=timestamp_str
        )
