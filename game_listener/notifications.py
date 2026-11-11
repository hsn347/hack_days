"""Live castle memory store and incoming server notification handling."""

from typing import Any, Dict


class LiveMemory:
    """In-memory snapshot and live state mirror of the player's castle."""

    def __init__(self) -> None:
        self.snapshot_loaded = False
        self.state: Dict[str, Any] = {}

    def load_snapshot(self, retdata: Dict[str, Any]) -> None:
        """Store the initial 1000/1 retdata dictionary as the base live state."""
        self.state = dict(retdata)
        self.snapshot_loaded = True

    def summary(self) -> Dict[str, Any]:
        """Return a compact, safe overview of the loaded castle modules."""
        lord = self.state.get("lordInfoCtrl", {})
        city = self.state.get("cityCtrl", {})
        return {
            "modules_count": len(self.state),
            "modules_sample": sorted(self.state.keys())[:15],
            "lord_keys": sorted(lord.keys())[:10] if isinstance(lord, dict) else [],
            "city_keys": sorted(city.keys())[:10] if isinstance(city, dict) else [],
        }
