"""
Geocoding functionality with intelligent fallbacks and caching
"""

import logging
import re
from typing import List
from typing import Optional
from typing import Tuple

from geopy.geocoders import Nominatim

from events_scraper.lib.core.orm_models import GeocodeCache as OrmGeocodeCache
from events_scraper.lib.core.orm_session import get_session

logger = logging.getLogger(__name__)


class GeocodeCache:
    """Local SQLite cache for geocoding results using ORM"""

    def get(self, location_query: str) -> Optional[Tuple[float, float]]:
        """Get cached coordinates for a location query using ORM"""
        session = get_session()
        try:
            # Query using ORM
            cached = (
                session.query(OrmGeocodeCache)
                .filter(OrmGeocodeCache.location_query == location_query)
                .first()
            )

            if cached:
                if cached.found:
                    return (cached.latitude, cached.longitude)
                else:
                    return None  # Previously failed lookup
            return None
        finally:
            session.close()

    def set(self, location_query: str, coordinates: Optional[Tuple[float, float]]):
        """Cache coordinates for a location query using ORM"""
        session = get_session()
        try:
            if coordinates:
                lat, lng = coordinates
                cache_entry = OrmGeocodeCache(
                    location_query=location_query, latitude=lat, longitude=lng, found=1
                )
            else:
                # Cache failed lookups to avoid repeated API calls
                cache_entry = OrmGeocodeCache(
                    location_query=location_query, latitude=None, longitude=None, found=0
                )

            # Use merge for upsert behavior (handles existing entries)
            session.merge(cache_entry)
            session.commit()
        finally:
            session.close()


class Geocoder:
    """Geocoding service with local caching and failure tracking"""

    def __init__(
        self,
        city_context: str = "Paris, France",
    ):
        self.cache = GeocodeCache()
        self.city_context = city_context
        self.geolocator = Nominatim(user_agent="events_scraper")

    def _write_failed_location(self, location: str):
        """Store failed location in database for manual review"""
        # Store as a failed geocoding result in the cache (coordinates will be None)
        self.cache.set(location, None)
        logger.info(f"Added failed geocoding location to database: {location}")

    def _clean_location_string(self, location: str) -> List[str]:
        """Generate simplified versions of location string for fallback geocoding"""
        variations = [location]

        cleaned = self._remove_organizational_suffixes(location)
        if cleaned != location:
            variations.append(cleaned)

        cleaned = self._remove_parenthetical_info(cleaned)
        if cleaned not in variations:
            variations.append(cleaned)

        variations.extend(self._extract_separator_parts(cleaned))
        variations.extend(self._extract_district_names(cleaned))

        return self._deduplicate_variations(variations)

    def _remove_organizational_suffixes(self, location: str) -> str:
        """Remove organizational suffixes from location string"""
        suffixes = [" e.V.", " e.v.", " gGmbH", " GmbH", " AG", " KG"]
        cleaned = location
        for suffix in suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        return cleaned

    def _remove_parenthetical_info(self, location: str) -> str:
        """Remove parenthetical information from location string"""
        if "(" in location and ")" in location:
            no_parens = re.sub(r"\s*\([^)]*\)", "", location).strip()
            if no_parens and no_parens != location:
                return no_parens
        return location

    def _extract_separator_parts(self, location: str) -> List[str]:
        """Extract parts before/after separators like slashes and dashes"""
        variations = []
        separators = [" / ", " - ", " Höhe ", " höhe ", " at "]

        for sep in separators:
            if sep in location:
                parts = location.split(sep)
                if len(parts) > 1:
                    first_part = parts[0].strip()
                    if first_part and len(first_part) > 3:
                        variations.append(first_part)
                    last_part = parts[-1].strip()
                    if last_part and len(last_part) > 3:
                        variations.append(last_part)
        return variations

    def _extract_district_names(self, location: str) -> List[str]:
        """Extract district/neighborhood names using German patterns"""
        variations = []
        patterns = [
            r"([A-Z][a-z]+(?:-[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+)\s+(?:Stadtteil|stadtteil)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, location)
            for match in matches:
                if len(match) > 3:
                    variations.append(match)
        return variations

    def _deduplicate_variations(self, variations: List[str]) -> List[str]:
        """Remove duplicates while preserving order"""
        seen = set()
        unique = []
        for var in variations:
            var_clean = var.strip()
            if var_clean and var_clean not in seen and len(var_clean) > 2:
                seen.add(var_clean)
                unique.append(var_clean)
        return unique

    def _try_geocoding_query(self, query: str) -> Optional[Tuple[float, float]]:
        """Try a single geocoding query"""
        try:
            result = self.geolocator.geocode(query, timeout=10)
            if result:
                return (result.latitude, result.longitude)
        except Exception as e:
            logger.debug(f"Geocoding error for '{query}': {e}")
        return None

    def geocode(self, location: str) -> Optional[Tuple[float, float]]:
        """Get coordinates for a location string with intelligent fallbacks"""
        if not location or not location.strip():
            return None

        location = location.strip()
        logger.debug(f"Starting geocoding for: {location}")

        # Check cache first
        cached_result = self.cache.get(location)
        if cached_result is not None:
            logger.debug(f"Geocode cache hit for: {location}")
            return cached_result

        logger.info(f"Geocoding: {location}")

        # Try geocoding with various strategies
        coordinates = self._try_geocoding_strategies(location)

        if coordinates:
            self.cache.set(location, coordinates)
            return coordinates

        # Complete failure
        logger.warning(f"Complete geocoding failure for: {location}")
        self._write_failed_location(location)
        self.cache.set(location, None)
        return None

    def _try_geocoding_strategies(self, location: str) -> Optional[Tuple[float, float]]:
        """Try multiple geocoding strategies in order of preference"""
        location_variations = self._clean_location_string(location)

        # Strategy 1: Try with city context
        coordinates = self._try_with_city_context(location, location_variations)
        if coordinates:
            return coordinates

        # Strategy 2: Try without city context
        coordinates = self._try_without_city_context(location, location_variations)
        if coordinates:
            return coordinates

        # Strategy 3: Final city fallback
        return self._try_city_fallback(location)

    def _try_with_city_context(
        self, original_location: str, variations: List[str]
    ) -> Optional[Tuple[float, float]]:
        """Try geocoding with city context"""
        for variation in variations:
            full_query = f"{variation}, {self.city_context}"
            query_type = "original" if variation == original_location else "simplified"
            logger.debug(f"Trying {query_type}: {full_query}")

            coordinates = self._try_geocoding_query(full_query)
            if coordinates:
                logger.debug(
                    f"Geocoded '{original_location}' to {coordinates} using {query_type}: {full_query}"
                )
                return coordinates
        return None

    def _try_without_city_context(
        self, original_location: str, variations: List[str]
    ) -> Optional[Tuple[float, float]]:
        """Try geocoding without city context as fallback"""
        for variation in variations:
            logger.debug(f"Trying without context: {variation}")
            coordinates = self._try_geocoding_query(variation)
            if coordinates:
                logger.debug(
                    f"Geocoded '{original_location}' to {coordinates} using no context: {variation}"
                )
                return coordinates
        return None

    def _try_city_fallback(
        self, original_location: str
    ) -> Optional[Tuple[float, float]]:
        """Try city-only geocoding as last resort"""
        if not self.city_context:
            return None

        city_only = self.city_context.split(",")[0].strip()
        logger.debug(f"Final fallback to city: {city_only}")
        coordinates = self._try_geocoding_query(city_only)
        if coordinates:
            logger.info(
                f"Geocoded '{original_location}' to city center {coordinates} (fallback)"
            )
            return coordinates
        return None
