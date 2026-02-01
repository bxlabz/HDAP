import requests
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from sklearn.cluster import KMeans


@dataclass
class Route:
    """Represents a delivery route."""
    route_number: int
    beneficiaries: list
    total_distance: float = 0.0
    estimated_duration: float = 0.0  # in minutes
    route_geometry: list = None  # List of [lon, lat] road coordinates from OSRM

    def __post_init__(self):
        if self.route_geometry is None:
            self.route_geometry = []

    @property
    def stop_count(self) -> int:
        return len(self.beneficiaries)


def _cluster_centroid(cluster: list) -> Tuple[float, float]:
    """Calculate the centroid of a cluster."""
    if not cluster:
        return (0.0, 0.0)
    lat = sum(b.latitude for b in cluster) / len(cluster)
    lon = sum(b.longitude for b in cluster) / len(cluster)
    return (lat, lon)


def _distance_between_clusters(cluster1: list, cluster2: list) -> float:
    """Calculate distance between two cluster centroids."""
    from app.geocoder import calculate_distance
    c1 = _cluster_centroid(cluster1)
    c2 = _cluster_centroid(cluster2)
    return calculate_distance(c1[0], c1[1], c2[0], c2[1])


def cluster_beneficiaries(beneficiaries: list, max_stops_per_route: int = 4,
                          min_stops_per_route: int = 3) -> List[List]:
    """
    Cluster beneficiaries geographically using K-Means with min/max constraints.

    Args:
        beneficiaries: List of geocoded Beneficiary objects
        max_stops_per_route: Maximum stops per route
        min_stops_per_route: Minimum stops per route (will merge small clusters)

    Returns:
        List of clusters (each cluster is a list of beneficiaries)
    """
    # Filter to only geocoded beneficiaries
    geocoded = [b for b in beneficiaries if b.is_geocoded() and not b.excluded]

    if not geocoded:
        return []

    if len(geocoded) <= max_stops_per_route:
        return [geocoded]

    # Extract coordinates
    coords = np.array([[b.latitude, b.longitude] for b in geocoded])

    # Calculate number of clusters - aim for clusters around the middle of min/max
    target_size = (min_stops_per_route + max_stops_per_route) // 2
    n_clusters = max(1, len(geocoded) // target_size)

    # Ensure we don't have more clusters than points
    n_clusters = min(n_clusters, len(geocoded))

    # Perform K-Means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(coords)

    # Group beneficiaries by cluster
    clusters = [[] for _ in range(n_clusters)]
    for beneficiary, label in zip(geocoded, labels):
        clusters[label].append(beneficiary)

    # Remove empty clusters
    clusters = [c for c in clusters if c]

    # Split any clusters that exceed max_stops_per_route
    split_clusters = []
    for cluster in clusters:
        if len(cluster) <= max_stops_per_route:
            split_clusters.append(cluster)
        else:
            # Split large cluster into chunks respecting min/max
            remaining = cluster.copy()
            while remaining:
                if len(remaining) <= max_stops_per_route:
                    split_clusters.append(remaining)
                    break
                elif len(remaining) <= max_stops_per_route + min_stops_per_route:
                    # Can't split evenly - divide as evenly as possible
                    half = len(remaining) // 2
                    split_clusters.append(remaining[:half])
                    split_clusters.append(remaining[half:])
                    break
                else:
                    # Take max_stops
                    split_clusters.append(remaining[:max_stops_per_route])
                    remaining = remaining[max_stops_per_route:]

    # Merge small clusters (below min_stops) with nearest neighbor
    final_clusters = []
    small_clusters = [c for c in split_clusters if len(c) < min_stops_per_route]
    large_clusters = [c for c in split_clusters if len(c) >= min_stops_per_route]

    # First, add all large clusters
    final_clusters = large_clusters.copy()

    # Try to merge small clusters
    for small in small_clusters:
        merged = False

        # Find nearest cluster that can absorb this one
        if final_clusters:
            # Sort by distance to find nearest
            candidates = [
                (i, _distance_between_clusters(small, fc))
                for i, fc in enumerate(final_clusters)
                if len(fc) + len(small) <= max_stops_per_route
            ]

            if candidates:
                candidates.sort(key=lambda x: x[1])
                best_idx = candidates[0][0]
                final_clusters[best_idx].extend(small)
                merged = True

        if not merged:
            # Can't merge - check if we can merge with another small cluster
            for i, other_small in enumerate(small_clusters):
                if other_small is not small and len(small) + len(other_small) <= max_stops_per_route:
                    if len(small) + len(other_small) >= min_stops_per_route:
                        # Merge these two small clusters
                        final_clusters.append(small + other_small)
                        small_clusters[i] = []  # Mark as used
                        merged = True
                        break

            if not merged:
                # Geographic outlier - add as its own route
                final_clusters.append(small)

    # Remove any empty clusters
    final_clusters = [c for c in final_clusters if c]

    return final_clusters


def optimize_route_osrm(beneficiaries: list, depot_lat: float = None, depot_lon: float = None) -> Tuple[list, float, float, list]:
    """
    Optimize route order using OSRM trip service (TSP solver).

    Args:
        beneficiaries: List of beneficiaries in the route
        depot_lat: Optional depot latitude (start/end point)
        depot_lon: Optional depot longitude

    Returns:
        Tuple of (ordered_beneficiaries, total_distance_km, duration_minutes, route_geometry)
        route_geometry is a list of [lon, lat] coordinates representing the actual road path
    """
    if len(beneficiaries) <= 1:
        return beneficiaries, 0.0, 0.0, []

    # Build coordinates string
    coords = []
    has_depot = depot_lat is not None and depot_lon is not None

    # Add depot as first point if provided
    if has_depot:
        coords.append(f"{depot_lon},{depot_lat}")

    for b in beneficiaries:
        coords.append(f"{b.longitude},{b.latitude}")

    coords_str = ";".join(coords)

    # OSRM demo server (for production, use your own server)
    # Using roundtrip=true which is well-supported by the demo server
    url = f"http://router.project-osrm.org/trip/v1/driving/{coords_str}"
    params = {
        "roundtrip": "true",
        "geometries": "geojson",
        "overview": "full"  # Get full road geometry for GPX
    }

    # If we have a depot, set it as fixed start point
    if has_depot:
        params["source"] = "first"

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok":
            # OSRM failed, fall back to simple optimization
            return optimize_route_simple(beneficiaries, depot_lat, depot_lon), 0.0, 0.0, []

        # Extract trip info
        trip = data.get("trips", [{}])[0]
        distance_m = trip.get("distance", 0)
        duration_s = trip.get("duration", 0)

        # Extract route geometry (actual road coordinates)
        geometry = trip.get("geometry", {})
        route_coords = geometry.get("coordinates", [])  # List of [lon, lat] pairs

        # Get optimized waypoint order
        waypoints = data.get("waypoints", [])

        if not waypoints:
            return optimize_route_simple(beneficiaries, depot_lat, depot_lon), 0.0, 0.0, []

        # If depot was included, skip it in reordering
        offset = 1 if has_depot else 0

        # Create mapping from original index to optimized position
        # waypoint_index tells us where each point goes in the optimized route
        ordered = [None] * len(beneficiaries)

        for i, wp in enumerate(waypoints):
            original_idx = i - offset  # Original position in beneficiaries list
            optimized_pos = wp.get("waypoint_index", i) - offset  # New position

            if original_idx >= 0 and original_idx < len(beneficiaries):
                if optimized_pos >= 0 and optimized_pos < len(beneficiaries):
                    ordered[optimized_pos] = beneficiaries[original_idx]

        # Fill any gaps and validate
        ordered = [b for b in ordered if b is not None]
        if len(ordered) != len(beneficiaries):
            # Something went wrong, fall back to simple optimization
            return optimize_route_simple(beneficiaries, depot_lat, depot_lon), distance_m / 1000, duration_s / 60, route_coords

        return ordered, distance_m / 1000, duration_s / 60, route_coords

    except requests.RequestException:
        # Network error, fall back to simple optimization
        return optimize_route_simple(beneficiaries, depot_lat, depot_lon), 0.0, 0.0, []
    except (KeyError, IndexError, TypeError):
        # Parsing error, fall back to simple optimization
        return optimize_route_simple(beneficiaries, depot_lat, depot_lon), 0.0, 0.0, []


def optimize_route_simple(beneficiaries: list, depot_lat: float = None, depot_lon: float = None) -> list:
    """
    Simple nearest-neighbor route optimization.
    Fallback when OSRM is unavailable.
    """
    if len(beneficiaries) <= 1:
        return beneficiaries

    from app.geocoder import calculate_distance

    # Start from depot or first point
    if depot_lat and depot_lon:
        current_lat, current_lon = depot_lat, depot_lon
    else:
        current_lat = beneficiaries[0].latitude
        current_lon = beneficiaries[0].longitude

    remaining = beneficiaries.copy()
    ordered = []

    while remaining:
        # Find nearest unvisited
        nearest = min(remaining,
                      key=lambda b: calculate_distance(current_lat, current_lon, b.latitude, b.longitude))
        ordered.append(nearest)
        remaining.remove(nearest)
        current_lat, current_lon = nearest.latitude, nearest.longitude

    return ordered


def create_routes(beneficiaries: list, max_stops: int = 4, min_stops: int = 3,
                  depot_lat: float = None, depot_lon: float = None,
                  use_osrm: bool = True) -> List[Route]:
    """
    Create optimized delivery routes from beneficiary list.

    Args:
        beneficiaries: List of geocoded Beneficiary objects
        max_stops: Maximum stops per route
        min_stops: Minimum stops per route (will try to merge small routes)
        depot_lat: Depot latitude
        depot_lon: Depot longitude
        use_osrm: Whether to use OSRM for optimization

    Returns:
        List of Route objects
    """
    # Cluster beneficiaries with min/max constraints
    clusters = cluster_beneficiaries(beneficiaries, max_stops, min_stops)

    routes = []
    for i, cluster in enumerate(clusters, start=1):
        # Optimize order within cluster
        if use_osrm:
            ordered, distance, duration, geometry = optimize_route_osrm(cluster, depot_lat, depot_lon)
        else:
            ordered = optimize_route_simple(cluster, depot_lat, depot_lon)
            distance, duration, geometry = 0.0, 0.0, []

        # Assign route numbers and sequences
        for seq, beneficiary in enumerate(ordered, start=1):
            beneficiary.route_number = i
            beneficiary.route_sequence = seq

        route = Route(
            route_number=i,
            beneficiaries=ordered,
            total_distance=distance,
            estimated_duration=duration,
            route_geometry=geometry
        )
        routes.append(route)

    return routes
