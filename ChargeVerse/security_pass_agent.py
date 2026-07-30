"""
ChargeVerse — Security Pass Agent
===================================
Cryptographic Gate Pass & Access Control Engine sitting at Step 7 of the
autonomous 7-agent execution pipeline.

Architecture
------------
* Receives winning auction deal from DealOptimizerAgent.
* Validates cargo safety and hazardous materials clearance for private yards.
* Generates an 8-character SHA-256 security hash token.
* Builds a scannable PNG QR code matching the ChargeVerse cyberpunk UI palette.
* Issues dynamic GatePassPayload object with status GRANTED or DENIED.
"""

from __future__ import annotations

import hashlib
import io
import logging
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

try:
    import qrcode
except ImportError:
    qrcode = None

_log = logging.getLogger("chargeverse.security_pass")


class GatePassPayload(BaseModel):
    pass_id: str = Field(..., description="Cryptographic Pass Identifier")
    vehicle_id: str = Field(..., description="Target vehicle ID")
    station_id: str = Field(..., description="Destination station ID")
    station_name: str = Field(..., description="Destination station facility name")
    assigned_bay: str = Field(..., description="Assigned charger bay designation")
    security_hash: str = Field(..., description="8-character SHA-256 token")
    valid_until: str = Field(..., description="Expiration timestamp string")
    cargo_type: str = Field(..., description="Cargo payload description")
    status: str = Field(..., description="GRANTED | DENIED | PENDING")
    rejection_reason: Optional[str] = Field(default=None, description="Reason if denied")
    timestamp: float = Field(default_factory=time.time, description="Epoch issued")


class SecurityPassAgent:
    """Cryptographic Gate Pass & Security Verification Engine."""

    def __init__(self, secret_key: str = "CHARGEVERSE_SECURE_KEY_2026") -> None:
        self.secret_key = secret_key
        _log.info("SecurityPassAgent initialised.")

    def _generate_security_token(self, vehicle_id: str, station_id: str, timestamp: float) -> str:
        """Generates a dynamic 8-character security hash for gate authentication."""
        raw_string = f"{vehicle_id}:{station_id}:{timestamp}:{self.secret_key}"
        return hashlib.sha256(raw_string.encode()).hexdigest()[:8].upper()

    def generate_qr_code_bytes(self, pass_data: str) -> bytes:
        """Generates a scannable QR Code PNG byte buffer for Streamlit rendering."""
        try:
            if qrcode is not None:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=6,
                    border=2,
                )
                qr.add_data(pass_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#00FF66", back_color="#0E1117")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        except Exception as e:
            _log.error("qrcode module generation error: %s", e)

        # High-reliability fallback generator using PIL
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (160, 160), color='#0E1117')
            d = ImageDraw.Draw(img)
            # Draw cyberpunk QR pattern placeholder
            d.rectangle([10, 10, 150, 150], outline='#00FF66', width=2)
            d.rectangle([20, 20, 50, 50], fill='#00FF66')
            d.rectangle([110, 20, 140, 50], fill='#00FF66')
            d.rectangle([20, 110, 50, 140], fill='#00FF66')
            d.rectangle([65, 65, 95, 95], fill='#00FF66')
            d.text((35, 142), f"SEC: {pass_data[:8]}", fill='#00FF66')
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return b""

    def issue_gate_pass(
        self,
        winning_deal: Dict[str, Any],
        cargo_type: str = "General Retail Freight",
        is_hazard: bool = False
    ) -> GatePassPayload:
        """Validates security compliance and issues digital gate pass clearance."""
        station_id = winning_deal.get("station_id", "UNKNOWN_STATION")
        facility_name = winning_deal.get("name", winning_deal.get("facility_name", station_id))
        facility_type = winning_deal.get("facility_type", "PUBLIC_STATION")
        vehicle_id = winning_deal.get("vehicle_id", "EV-CV-001")

        # Rule 1: Hazardous material security block for unequipped private yards
        if is_hazard and facility_type == "PRIVATE_YARD":
            _log.warning("Security DENIED for %s at %s due to Hazmat policy", vehicle_id, station_id)
            return GatePassPayload(
                pass_id="DENIED-HAZMAT",
                vehicle_id=vehicle_id,
                station_id=station_id,
                station_name=facility_name,
                assigned_bay="NONE",
                security_hash="INVALID",
                valid_until="EXPIRED",
                cargo_type=cargo_type,
                status="DENIED",
                rejection_reason="Private Yard lacks Hazardous Material Containment Clearance"
            )

        # Rule 2: Successful Security Token Generation
        now = time.time()
        token = self._generate_security_token(vehicle_id, station_id, now)
        pass_code = f"#808-GATE-PASS-{token}"
        bay_num = (abs(hash(token)) % 8) + 1
        bay = f"BAY-{bay_num:02d}"
        expiry_str = time.strftime("%H:%M IST", time.localtime(now + 3600))

        _log.info("Gate pass GRANTED: %s for %s at %s", pass_code, vehicle_id, station_id)
        return GatePassPayload(
            pass_id=pass_code,
            vehicle_id=vehicle_id,
            station_id=station_id,
            station_name=facility_name,
            assigned_bay=bay,
            security_hash=token,
            valid_until=expiry_str,
            cargo_type=cargo_type,
            status="GRANTED"
        )
