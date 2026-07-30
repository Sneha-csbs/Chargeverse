"""
ChargeVerse — Weather Impact Agent
===================================
Software-only Environmental Weather & Battery Strain Accounting Engine sitting at Step 1 of the
autonomous 9-agent execution pipeline.

Architecture
------------
* Fetches live API weather data from Open-Meteo API or fallback simulation parameters.
* Evaluates environmental strain factors:
    - Rain/Precipitation: +15% rolling resistance
    - Extreme Heat (>35°C) or Cold (<15°C): +10% thermal/HVAC load
    - High Wind (>20 km/h): +5% aerodynamic drag
* Dynamically calculates Adjusted kWh Deficit using:
    Adjusted kWh Deficit = Base kWh Needed * (1 + Rain Factor + Temp Factor + Wind Factor)
"""

from __future__ import annotations

import logging
import requests
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

_log = logging.getLogger("chargeverse.weather")


class WeatherImpactPayload(BaseModel):
    temperature_c: float = Field(..., description="Current temperature in Celsius")
    is_raining: bool = Field(..., description="Active rain status flag")
    wind_speed_kmh: float = Field(..., description="Wind speed in km/h")
    rain_factor: float = Field(..., description="Rain strain factor (0.15 or 0.0)")
    temp_factor: float = Field(..., description="Temperature strain factor (0.10 or 0.0)")
    wind_factor: float = Field(..., description="Wind drag factor (0.05 or 0.0)")
    impact_multiplier: float = Field(..., description="Total combined strain multiplier e.g. 1.25")
    weather_condition_summary: str = Field(..., description="Human-readable condition breakdown")
    base_kwh_needed: float = Field(..., description="Unadjusted base kWh deficit")
    adjusted_kwh_needed: float = Field(..., description="Weather-adjusted kWh deficit required")


class WeatherImpactAgent:
    """Software-only Environmental Weather & Battery Strain Accounting Engine."""

    def __init__(self, api_url: str = "https://api.open-meteo.com/v1/forecast") -> None:
        self.api_url = api_url
        _log.info("WeatherImpactAgent initialized with API: %s", api_url)

    def fetch_live_weather(self, lat: float = 12.9716, lon: float = 77.5946) -> Dict[str, Any]:
        """Fetches live weather data from Open-Meteo API (Free, No Key required)."""
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": ["temperature_2m", "rain", "wind_speed_10m"]
            }
            res = requests.get(self.api_url, params=params, timeout=3)
            if res.status_code == 200:
                curr = res.json().get("current", {})
                return {
                    "temp": float(curr.get("temperature_2m", 36.0)),
                    "rain": bool(curr.get("rain", 0.0) > 0.0),
                    "wind": float(curr.get("wind_speed_10m", 15.0))
                }
        except Exception as e:
            _log.warning("Open-Meteo API fetch failed gracefully: %s. Using fallback simulation.", e)

        # Fallback to simulated Bangalore weather if offline or API timeout
        return {"temp": 38.0, "rain": True, "wind": 22.5}

    def evaluate_weather_impact(
        self,
        base_kwh: float,
        lat: float = 12.9716,
        lon: float = 77.5946,
        override_temp: Optional[float] = None,
        override_rain: Optional[bool] = None
    ) -> WeatherImpactPayload:
        """Calculates environmental strain factors and returns weather-adjusted kWh requirement."""

        # 1. Fetch or Override weather values
        weather = self.fetch_live_weather(lat, lon)
        temp = override_temp if override_temp is not None else weather["temp"]
        rain = override_rain if override_rain is not None else weather["rain"]
        wind = weather["wind"]

        # 2. Compute Strain Factors
        rain_factor = 0.15 if rain else 0.0
        temp_factor = 0.10 if (temp > 35.0 or temp < 15.0) else 0.0
        wind_factor = 0.05 if wind > 20.0 else 0.0

        total_multiplier = round(1.0 + rain_factor + temp_factor + wind_factor, 2)
        adjusted_kwh = round(base_kwh * total_multiplier, 2)

        # 3. Summary String Generation
        conds = []
        if rain:
            conds.append("Heavy Rain (+15% Rolling Resistance)")
        if temp > 35.0:
            conds.append("Extreme Heat (+10% Battery Cooling Load)")
        elif temp < 15.0:
            conds.append("Cold Temp (+10% Thermal Strain)")
        if wind > 20.0:
            conds.append("High Headwind (+5% Drag)")

        summary = " | ".join(conds) if conds else "CLEAR & OPTIMAL DRIVING CONDITIONS"

        _log.info(
            "Weather Impact Evaluated: Base=%.1f kWh -> Adjusted=%.1f kWh (Multiplier=%.2fx)",
            base_kwh, adjusted_kwh, total_multiplier
        )

        return WeatherImpactPayload(
            temperature_c=temp,
            is_raining=rain,
            wind_speed_kmh=wind,
            rain_factor=rain_factor,
            temp_factor=temp_factor,
            wind_factor=wind_factor,
            impact_multiplier=total_multiplier,
            weather_condition_summary=summary,
            base_kwh_needed=base_kwh,
            adjusted_kwh_needed=adjusted_kwh
        )
