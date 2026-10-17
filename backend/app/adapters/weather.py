from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx

from .base import AdapterError


class NWSAdapter:
    source_id = "noaa-nws"
    endpoint = "https://api.weather.gov"

    def __init__(self, user_agent: str = "CityShield research prototype") -> None:
        self.headers = {"User-Agent": user_agent, "Accept": "application/geo+json"}

    async def fetch_hourly(self, latitude: float, longitude: float) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30, headers=self.headers) as client:
            point = await client.get(f"{self.endpoint}/points/{latitude:.4f},{longitude:.4f}")
            if point.status_code != 200:
                raise AdapterError(f"NWS point lookup failed with HTTP {point.status_code}")
            hourly_url = point.json().get("properties", {}).get("forecastHourly")
            if not hourly_url:
                raise AdapterError("NWS response did not include forecastHourly")
            forecast = await client.get(hourly_url)
            if forecast.status_code != 200:
                raise AdapterError(f"NWS hourly forecast failed with HTTP {forecast.status_code}")
        return self.parse_hourly(forecast.json())

    @staticmethod
    def parse_hourly(payload: dict[str, Any]) -> list[dict[str, Any]]:
        properties = payload.get("properties", {})
        issued_raw = properties.get("updated") or properties.get("updateTime") or properties.get("generatedAt")
        issued_at = (
            datetime.fromisoformat(issued_raw.replace("Z", "+00:00"))
            if issued_raw
            else None
        )
        result = []
        for period in properties.get("periods", []):
            speeds = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", period.get("windSpeed", ""))]
            wind_mph = sum(speeds) / len(speeds) if speeds else None
            result.append(
                {
                    "valid_at": period.get("startTime"),
                    "forecast_issued_at": issued_at.isoformat() if issued_at else None,
                    "temperature": period.get("temperature"),
                    "temperature_unit": period.get("temperatureUnit"),
                    "wind_speed_m_s": round(wind_mph * 0.44704, 3) if wind_mph is not None else None,
                    "wind_direction": period.get("windDirection"),
                    "humidity_pct": (period.get("relativeHumidity") or {}).get("value"),
                    "short_forecast": period.get("shortForecast"),
                    "provider_period_id": period.get("number"),
                }
            )
        return result

