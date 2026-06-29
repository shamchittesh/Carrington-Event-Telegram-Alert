"""NOAA Space Weather data collector for CarringtonWatch Bot.

Fetches and parses data from NOAA SWPC public endpoints:
- Solar wind speed
- Interplanetary magnetic field (Bz component)
- Planetary K-index
- X-ray flare classifications
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


@dataclass
class SpaceWeatherData:
    """A single snapshot of collected NOAA space weather measurements."""

    timestamp: str  # ISO 8601 UTC
    kp_index: float | None
    solar_wind_speed: float | None
    bz_component: float | None
    xray_flare: str | None  # e.g. "X2.1", "M5.3", "C1.0"


class NOAACollector:
    """Fetches and parses NOAA SWPC data."""

    ENDPOINTS = {
        "solar_wind": "https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json",
        "mag_field": "https://services.swpc.noaa.gov/products/summary/solar-wind-mag-field.json",
        "kp_index": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
        "xray_flares": "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json",
    }

    def collect(self) -> SpaceWeatherData:
        """Fetch all endpoints and return structured data.

        Partial failures return None for unavailable fields.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        solar_wind_speed = self._parse_solar_wind()
        bz_component = self._parse_bz_component()
        kp_index = self._parse_kp_index()
        xray_flare = self._parse_xray_flare()

        return SpaceWeatherData(
            timestamp=timestamp,
            kp_index=kp_index,
            solar_wind_speed=solar_wind_speed,
            bz_component=bz_component,
            xray_flare=xray_flare,
        )

    def _fetch_json(self, url: str, timeout: int = 30) -> dict | list | None:
        """HTTP GET with error handling. Returns None on failure."""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("Timeout fetching %s", url)
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error fetching %s", url)
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP error fetching %s: %s", url, e)
            return None
        except requests.exceptions.RequestException as e:
            logger.warning("Request error fetching %s: %s", url, e)
            return None
        except ValueError as e:
            # JSON decode error
            logger.warning("Invalid JSON from %s: %s", url, e)
            return None

    def _parse_solar_wind(self) -> float | None:
        """Parse solar wind speed from NOAA summary endpoint.

        Expected format: {"WindSpeed": "450", "TimeStamp": "...", ...}
        """
        data = self._fetch_json(self.ENDPOINTS["solar_wind"])
        if data is None:
            return None

        try:
            speed_str = data.get("WindSpeed")
            if speed_str is None:
                logger.warning("Missing 'WindSpeed' field in solar wind data")
                return None
            return float(speed_str)
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning("Failed to parse solar wind speed: %s", e)
            return None

    def _parse_bz_component(self) -> float | None:
        """Parse Bz component from NOAA magnetic field summary endpoint.

        Expected format: {"Bz": "-5.2", "TimeStamp": "...", ...}
        """
        data = self._fetch_json(self.ENDPOINTS["mag_field"])
        if data is None:
            return None

        try:
            bz_str = data.get("Bz")
            if bz_str is None:
                logger.warning("Missing 'Bz' field in magnetic field data")
                return None
            return float(bz_str)
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning("Failed to parse Bz component: %s", e)
            return None

    def _parse_kp_index(self) -> float | None:
        """Parse Kp index from NOAA planetary K-index endpoint.

        Expected format: list of records, each with "kp" field.
        Uses the most recent (last) entry.
        """
        data = self._fetch_json(self.ENDPOINTS["kp_index"])
        if data is None:
            return None

        try:
            if not isinstance(data, list) or len(data) < 2:
                logger.warning("Unexpected Kp index data format")
                return None

            # First row is header, data rows follow; use last entry
            last_entry = data[-1]

            if isinstance(last_entry, list):
                # Format: [timestamp, kp_value, ...]
                kp_str = last_entry[1]
            elif isinstance(last_entry, dict):
                # Format: {"time_tag": "...", "kp": "5.33", ...}
                kp_str = last_entry.get("kp") or last_entry.get("Kp")
                if kp_str is None:
                    logger.warning("Missing 'kp' field in Kp index data")
                    return None
            else:
                logger.warning("Unexpected Kp index entry format")
                return None

            return float(kp_str)
        except (TypeError, ValueError, IndexError, KeyError) as e:
            logger.warning("Failed to parse Kp index: %s", e)
            return None

    def _parse_xray_flare(self) -> str | None:
        """Parse X-ray flare classification from NOAA endpoint.

        Expected format: list of flare event objects with "classType" field.
        Uses the most recent flare event.
        """
        data = self._fetch_json(self.ENDPOINTS["xray_flares"])
        if data is None:
            return None

        try:
            if not isinstance(data, list) or len(data) == 0:
                logger.warning("Unexpected X-ray flare data format or empty list")
                return None

            # Use the most recent (last) flare event
            last_flare = data[-1]

            if not isinstance(last_flare, dict):
                logger.warning("Unexpected X-ray flare entry format")
                return None

            class_type = last_flare.get("classType")
            if class_type is None or not isinstance(class_type, str):
                logger.warning("Missing or invalid 'classType' in flare data")
                return None

            # Return the classification string (e.g., "X2.1", "M5.3", "C1.0")
            return class_type if class_type.strip() else None
        except (TypeError, IndexError, KeyError) as e:
            logger.warning("Failed to parse X-ray flare: %s", e)
            return None
