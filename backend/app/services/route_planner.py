"""Application-level route orchestration scores OSRM candidates and selects one."""

import asyncio
from datetime import UTC, datetime

from app.database.schemas import Coordinate
from app.routing.geometry import encode_polyline
from app.services.route_safety_service import RouteSafetyService
from app.services.routing_service import NoSidewalkRouteError, OSRMRoutingProvider


class RoutePlanner:
    def __init__(self, provider: OSRMRoutingProvider, safety: RouteSafetyService | None = None):
        self.provider = provider
        self.safety = safety

    async def plan(
        self,
        start: Coordinate,
        end: Coordinate,
        preference: str,
        require_sidewalk: bool = False,
        return_alternatives: bool = False,
    ) -> dict:
        candidates = await self.provider.compute_routes(start, end, "foot")
        if self.safety:
            candidates = list(
                await asyncio.gather(
                    *(
                        self.safety.score_route(candidate, datetime.now(UTC))
                        for candidate in candidates
                    )
                )
            )
        if require_sidewalk:
            candidates = [
                route for route in candidates if route.factor_breakdown.get("sidewalk", 0) >= 0.999
            ]
            if not candidates:
                raise NoSidewalkRouteError("No sidewalk-only route connects those points.")

        if return_alternatives:
            # Return all candidates with the selected one marked
            selected = self._select(candidates, preference)
            selected_index = candidates.index(selected)
            routes = [
                {
                    "polyline": encode_polyline(r.coordinates),
                    "coordinates": r.coordinates,
                    "distance_m": r.distance_m,
                    "estimated_walking_time_seconds": r.duration_seconds,
                    "safety_score": r.safety_score,
                    "factor_breakdown": r.factor_breakdown,
                    "warnings": r.warnings,
                }
                for r in candidates
            ]
            return {"routes": routes, "selected_index": selected_index}

        result = self._select(candidates, preference)
        return {
            "polyline": encode_polyline(result.coordinates),
            "coordinates": result.coordinates,
            "distance_m": result.distance_m,
            "estimated_walking_time_seconds": result.duration_seconds,
            "safety_score": result.safety_score,
            "factor_breakdown": result.factor_breakdown,
            "warnings": result.warnings,
        }

    @staticmethod
    def _select(candidates, preference):
        if preference == "fastest":
            return min(candidates, key=lambda route: route.duration_seconds)
        if preference == "safest":
            return max(candidates, key=lambda route: (route.safety_score, -route.duration_seconds))
        fastest = min(route.duration_seconds for route in candidates)
        return max(
            candidates,
            key=lambda route: (
                0.65 * route.safety_score + 0.35 * (fastest / max(route.duration_seconds, 1))
            ),
        )
