"""Straight-line (great-circle) distance. Shared by v1 and, later, the travel-time fallback in v2."""
import numpy as np

EARTH_RADIUS_KM = 6371.0088  # mean Earth radius


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Inputs in degrees; scalars or numpy arrays (they broadcast)."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = phi2 - phi1
    dlam = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))
