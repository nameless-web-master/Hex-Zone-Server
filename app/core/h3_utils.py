"""H3 hex zone utilities."""
from typing import List, Tuple, Optional
import h3
from app.core.config import settings


def lat_lng_to_h3_cell(latitude: float, longitude: float, resolution: Optional[int] = None) -> str:
    """Convert latitude/longitude to H3 cell ID."""
    if resolution is None:
        resolution = settings.H3_DEFAULT_RESOLUTION
    
    if not settings.H3_MIN_RESOLUTION <= resolution <= settings.H3_MAX_RESOLUTION:
        raise ValueError(
            f"Resolution must be between {settings.H3_MIN_RESOLUTION} "
            f"and {settings.H3_MAX_RESOLUTION}"
        )
    
    return h3.latlng_to_cell(latitude, longitude, resolution)


def get_h3_cells_in_radius(
    latitude: float,
    longitude: float,
    radius_km: float = 1,
    resolution: Optional[int] = None,
) -> List[str]:
    """Get H3 cells within a radius of a point."""
    if resolution is None:
        resolution = settings.H3_DEFAULT_RESOLUTION
    
    center_cell = lat_lng_to_h3_cell(latitude, longitude, resolution)
    radius_cells = h3.grid_disk(center_cell, int(radius_km))
    return list(radius_cells)


def h3_cell_to_boundary(cell_id: str) -> List[Tuple[float, float]]:
    """Get the boundary coordinates of an H3 cell."""
    boundary = h3.cell_to_latlng(cell_id)
    vertices = h3.cell_to_boundary(cell_id)
    return vertices


def validate_h3_cell(cell_id: str) -> bool:
    """Validate if a string is a valid H3 cell ID."""
    try:
        return h3.is_valid_cell(cell_id)
    except Exception:
        return False


def get_h3_resolution(cell_id: str) -> int:
    """Get the resolution of an H3 cell."""
    try:
        return h3.get_resolution(cell_id)
    except Exception:
        raise ValueError(f"Invalid H3 cell ID: {cell_id}")
