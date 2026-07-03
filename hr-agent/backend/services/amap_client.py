import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AMAP_KEY = "85571c830d1789c299a5a3a06aadd039"
BASE_URL = "https://restapi.amap.com/v3"


class AmapClient:
    def __init__(self) -> None:
        self.key = AMAP_KEY
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)

    async def _request(self, method: str, path: str, **kwargs) -> Optional[dict]:
        try:
            resp = await self.client.request(method, path, **kwargs)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                logger.error(
                    "Amap API error — path=%s, info=%s, infocode=%s",
                    path,
                    data.get("info"),
                    data.get("infocode"),
                )
                return None
            return data
        except httpx.HTTPError as exc:
            logger.error("Amap HTTP error — path=%s, error=%s", path, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Amap unexpected error — path=%s, error=%s", path, exc)
            return None

    @staticmethod
    def _split_location(location: str) -> tuple[Optional[float], Optional[float]]:
        try:
            lng, lat = location.split(",", 1)
            return float(lng), float(lat)
        except (ValueError, AttributeError):
            return None, None

    async def geocode(self, address: str, city: str = "") -> Optional[dict]:
        params = {"key": self.key, "address": address}
        if city:
            params["city"] = city

        data = await self._request("POST", "/geocode/geo", params=params)
        if data is None:
            return None

        geocodes = data.get("geocodes", [])
        if not geocodes:
            logger.warning("Geocode returned no results for address=%s", address)
            return None

        first = geocodes[0]
        lng, lat = self._split_location(first.get("location", ""))
        return {
            "lng": lng,
            "lat": lat,
            "formatted_address": first.get("formatted_address", ""),
            "level": first.get("level", ""),
        }

    async def reverse_geocode(self, lng: float, lat: float) -> Optional[dict]:
        params = {"key": self.key, "location": f"{lng},{lat}"}
        data = await self._request("GET", "/geocode/regeo", params=params)
        if data is None:
            return None

        regeo = data.get("regeocode", {})
        address_component = regeo.get("addressComponent", {})
        return {
            "address": regeo.get("formatted_address", ""),
            "province": address_component.get("province", ""),
            "city": address_component.get("city", address_component.get("citycode", "")),
            "district": address_component.get("district", ""),
        }

    async def driving_route(
        self,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
    ) -> Optional[dict]:
        origin = f"{origin_lng},{origin_lat}"
        destination = f"{dest_lng},{dest_lat}"
        params = {"key": self.key, "origin": origin, "destination": destination}

        data = await self._request("GET", "/direction/driving", params=params)
        if data is None:
            return None

        paths = data.get("route", {}).get("paths", [])
        if not paths:
            logger.warning("Driving route returned no paths origin=%s dest=%s", origin, destination)
            return None

        path = paths[0]
        distance_m = int(path.get("distance", 0))
        duration_s = int(path.get("duration", 0))
        return {
            "distance_meters": distance_m,
            "duration_minutes": max(1, duration_s // 60),
            "distance_text": f"{distance_m / 1000:.1f} km",
            "duration_text": f"{max(1, duration_s // 60)} 分钟",
        }

    async def transit_route(
        self,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
        city: str = "",
    ) -> Optional[dict]:
        origin = f"{origin_lng},{origin_lat}"
        destination = f"{dest_lng},{dest_lat}"
        params = {"key": self.key, "origin": origin, "destination": destination}
        if city:
            params["city"] = city

        data = await self._request("GET", "/direction/transit/integrated", params=params)
        if data is None:
            return None

        route = data.get("route", {})
        distance_m = int(route.get("distance", 0))
        transits = route.get("transits", [])
        duration_s = 0
        if transits:
            duration_s = int(transits[0].get("duration", 0))

        return {
            "distance_meters": distance_m,
            "duration_minutes": max(1, duration_s // 60),
            "distance_text": f"{distance_m / 1000:.1f} km",
            "duration_text": f"{max(1, duration_s // 60)} 分钟",
        }

    async def walking_route(
        self,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
    ) -> Optional[dict]:
        origin = f"{origin_lng},{origin_lat}"
        destination = f"{dest_lng},{dest_lat}"
        params = {"key": self.key, "origin": origin, "destination": destination}

        data = await self._request("GET", "/direction/walking", params=params)
        if data is None:
            return None

        paths = data.get("route", {}).get("paths", [])
        if not paths:
            logger.warning("Walking route returned no paths origin=%s dest=%s", origin, destination)
            return None

        path = paths[0]
        distance_m = int(path.get("distance", 0))
        duration_s = int(path.get("duration", 0))
        return {
            "distance_meters": distance_m,
            "duration_minutes": max(1, duration_s // 60),
            "distance_text": f"{distance_m / 1000:.1f} km",
            "duration_text": f"{max(1, duration_s // 60)} 分钟",
        }

    async def poi_search(
        self,
        keywords: str,
        city: str = "",
        location: str = "",
    ) -> list[dict]:
        params = {"key": self.key, "keywords": keywords}
        if city:
            params["city"] = city
        if location:
            params["location"] = location

        data = await self._request("GET", "/place/text", params=params)
        if data is None:
            return []

        pois = data.get("pois", [])
        results: list[dict] = []
        for poi in pois:
            lng, lat = self._split_location(poi.get("location", ""))
            results.append({
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "lng": lng,
                "lat": lat,
                "type": poi.get("type", ""),
                "distance": poi.get("distance", ""),
            })
        return results

    async def close(self) -> None:
        await self.client.aclose()


async def get_amap_client() -> AmapClient:
    return AmapClient()
