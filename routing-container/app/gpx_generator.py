import gpxpy
import gpxpy.gpx
from typing import List
from datetime import datetime


def format_phone_simple(phone: str) -> str:
    """Simple phone formatting for GPX description."""
    if not phone:
        return "N/A"
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) >= 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}"
    return phone


def generate_gpx(route, depot_lat: float = None, depot_lon: float = None,
                 depot_name: str = "Depot") -> str:
    """
    Generate OsmAnd-compatible GPX file for a route.

    Args:
        route: Route object with beneficiaries
        depot_lat: Optional depot latitude
        depot_lon: Optional depot longitude
        depot_name: Name for depot waypoint

    Returns:
        GPX file content as string
    """
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "Humanitarian Aid Delivery Router"

    # Add metadata
    gpx.name = f"Delivery Route {route.route_number}"
    gpx.description = f"Route with {route.stop_count} stops"
    gpx.time = datetime.utcnow()

    # Add depot as first waypoint if provided
    if depot_lat is not None and depot_lon is not None:
        depot_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=depot_lat,
            longitude=depot_lon,
            name=f"START: {depot_name}",
            description="Departure point / Punto de salida"
        )
        depot_wpt.symbol = "Flag, Blue"
        gpx.waypoints.append(depot_wpt)

    # Add beneficiary waypoints in order
    for i, beneficiary in enumerate(route.beneficiaries, start=1):
        phone_display = format_phone_simple(beneficiary.phone)

        description_parts = [
            beneficiary.address,
            f"Phone: {phone_display}"
        ]

        if beneficiary.household_size:
            description_parts.append(f"Household: {beneficiary.household_size}")

        if beneficiary.special_items:
            description_parts.append(f"Special: {beneficiary.special_items}")

        if beneficiary.notes:
            description_parts.append(f"Notes: {beneficiary.notes}")

        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=beneficiary.latitude,
            longitude=beneficiary.longitude,
            name=f"{i}. {beneficiary.name}",
            description="\n".join(description_parts)
        )

        # OsmAnd-compatible symbol
        wpt.symbol = "Flag, Green"
        gpx.waypoints.append(wpt)

    # Add depot as last waypoint (return) if provided
    if depot_lat is not None and depot_lon is not None:
        return_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=depot_lat,
            longitude=depot_lon,
            name=f"END: {depot_name}",
            description="Return point / Punto de regreso"
        )
        return_wpt.symbol = "Flag, Blue"
        gpx.waypoints.append(return_wpt)

    # Create a track showing the actual road route
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = f"Route {route.route_number} Track"
    gpx.tracks.append(gpx_track)

    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    # Check if we have OSRM road geometry
    route_geometry = getattr(route, 'route_geometry', None) or []

    if route_geometry:
        # Use actual road coordinates from OSRM
        for coord in route_geometry:
            # OSRM returns [lon, lat], GPX needs (lat, lon)
            lon, lat = coord[0], coord[1]
            gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon))
    else:
        # Fallback: connect waypoints directly (straight lines)
        # Add depot to track if provided
        if depot_lat is not None and depot_lon is not None:
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(depot_lat, depot_lon)
            )

        # Add beneficiary locations to track
        for beneficiary in route.beneficiaries:
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(beneficiary.latitude, beneficiary.longitude)
            )

        # Return to depot if provided
        if depot_lat is not None and depot_lon is not None:
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(depot_lat, depot_lon)
            )

    return gpx.to_xml()


def generate_all_gpx(routes: List, depot_lat: float = None, depot_lon: float = None,
                     depot_name: str = "Depot") -> List[tuple]:
    """
    Generate GPX files for all routes.

    Args:
        routes: List of Route objects
        depot_lat: Optional depot latitude
        depot_lon: Optional depot longitude
        depot_name: Name for depot waypoint

    Returns:
        List of (filename, gpx_content) tuples
    """
    results = []

    for route in routes:
        filename = f"route_{route.route_number:02d}.gpx"
        content = generate_gpx(route, depot_lat, depot_lon, depot_name)
        results.append((filename, content))

    return results


def generate_manifest_json(routes: List, depot_address: str = None) -> dict:
    """
    Generate a JSON manifest with route assignments for use by packing slip generator.

    Args:
        routes: List of Route objects
        depot_address: Optional depot address

    Returns:
        Dictionary with route assignments
    """
    manifest = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'depot_address': depot_address,
        'total_routes': len(routes),
        'total_stops': sum(r.stop_count for r in routes),
        'routes': []
    }

    for route in routes:
        route_data = {
            'route_number': route.route_number,
            'stop_count': route.stop_count,
            'total_distance': route.total_distance,
            'estimated_duration': route.estimated_duration,
            'beneficiaries': []
        }

        for i, b in enumerate(route.beneficiaries, start=1):
            route_data['beneficiaries'].append({
                'sequence': i,
                'name': b.name,
                'phone': b.phone,
                'address': b.address,
                'household_size': b.household_size,
                'items_needed': b.items_needed,
                'special_items': b.special_items,
                'notes': b.notes
            })

        manifest['routes'].append(route_data)

    return manifest


def generate_manifest(routes: List, depot_address: str = None) -> str:
    """
    Generate a text manifest summarizing all routes.

    Args:
        routes: List of Route objects
        depot_address: Optional depot address

    Returns:
        Manifest text content
    """
    lines = [
        "=" * 70,
        "DELIVERY ROUTE MANIFEST / MANIFIESTO DE RUTAS DE ENTREGA",
        "=" * 70,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ""
    ]

    if depot_address:
        lines.extend([
            f"Depot: {depot_address}",
            ""
        ])

    total_stops = sum(r.stop_count for r in routes)
    total_distance = sum(r.total_distance for r in routes)

    lines.extend([
        f"Total Routes: {len(routes)}",
        f"Total Stops: {total_stops}",
        f"Total Distance: {total_distance * 0.621371:.1f} miles" if total_distance > 0 else "",
        "",
        "-" * 70,
        ""
    ])

    for route in routes:
        lines.extend([
            f"ROUTE {route.route_number}",
            f"Stops: {route.stop_count}",
        ])

        if route.total_distance > 0:
            lines.append(f"Distance: {route.total_distance * 0.621371:.1f} miles")
        if route.estimated_duration > 0:
            lines.append(f"Est. Duration: {route.estimated_duration:.0f} min")

        lines.append("")

        for i, b in enumerate(route.beneficiaries, start=1):
            phone_display = format_phone_simple(b.phone)
            lines.append(f"  {i}. {b.name}")
            lines.append(f"     {b.address}")
            lines.append(f"     Phone: {phone_display}")
            if b.special_items:
                lines.append(f"     Special: {b.special_items}")
            lines.append("")

        lines.append("-" * 70)
        lines.append("")

    return "\n".join(lines)
