from flask import Blueprint, render_template, request, session, redirect, url_for, send_file, flash, jsonify, current_app
import io
import zipfile
import json
import uuid
import os
from app.csv_parser import parse_csv, Beneficiary
from app.geocoder import geocode_beneficiaries, geocode_address, export_failed_geocodes
from app.optimizer import create_routes
from app.gpx_generator import generate_gpx, generate_manifest, generate_manifest_json

bp = Blueprint('main', __name__)


def _get_data_file():
    """Get path to current session's data file."""
    data_id = session.get('data_id')
    if not data_id:
        data_id = str(uuid.uuid4())
        session['data_id'] = data_id
        session.modified = True
    return os.path.join(current_app.config['DATA_DIR'], f'{data_id}.json')


def _load_data():
    """Load data from file."""
    data_file = _get_data_file()
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_data(data):
    """Save data to file."""
    data_file = _get_data_file()
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f)


@bp.route('/')
def index():
    """Upload page."""
    return render_template('index.html')


@bp.route('/upload', methods=['POST'])
def upload():
    """Handle CSV file upload."""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('main.index'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.index'))

    if not file.filename.lower().endswith('.csv'):
        flash('Please upload a CSV file', 'error')
        return redirect(url_for('main.index'))

    try:
        content = file.read().decode('utf-8-sig')  # Handle BOM
    except UnicodeDecodeError:
        try:
            file.seek(0)
            content = file.read().decode('latin-1')
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(url_for('main.index'))

    result = parse_csv(content)

    if result.has_errors:
        for error in result.errors:
            flash(error, 'error')
        return redirect(url_for('main.index'))

    # Store data in file
    data = {
        'beneficiaries': [
            {
                'row_number': b.row_number,
                'name': b.name,
                'phone': b.phone,
                'address': b.address,
                'household_size': b.household_size,
                'items_needed': b.items_needed,
                'special_items': b.special_items,
                'notes': b.notes,
                'errors': b.errors,
                'warnings': b.warnings,
                'flagged': b.flagged,
                'latitude': None,
                'longitude': None,
                'geocode_error': ''
            }
            for b in result.beneficiaries
        ],
        'warnings': result.warnings,
        'geocoded': False,
        'depot': {},
        'routes': None
    }
    _save_data(data)

    return redirect(url_for('main.review'))


@bp.route('/review')
def review():
    """Review and flag data page."""
    data = _load_data()
    if not data.get('beneficiaries'):
        flash('Please upload a CSV file first', 'error')
        return redirect(url_for('main.index'))

    return render_template('review.html',
                           beneficiaries=data['beneficiaries'],
                           warnings=data.get('warnings', []),
                           geocoded=data.get('geocoded', False),
                           depot=data.get('depot', {}))


@bp.route('/update', methods=['POST'])
def update():
    """Update beneficiary data from review page."""
    data = _load_data()
    if not data.get('beneficiaries'):
        return redirect(url_for('main.index'))

    beneficiaries = data['beneficiaries']

    # Update excluded status
    excluded = request.form.getlist('exclude')
    for i, b in enumerate(beneficiaries):
        b['excluded'] = str(i) in excluded

    # Save depot address
    depot_address = request.form.get('depot_address', '').strip()
    if depot_address:
        data['depot'] = {'address': depot_address}
    else:
        data['depot'] = {}

    data['beneficiaries'] = beneficiaries
    _save_data(data)

    flash('Data updated successfully', 'success')
    return redirect(url_for('main.review'))


@bp.route('/geocode', methods=['POST'])
def geocode():
    """Geocode all beneficiary addresses."""
    data = _load_data()
    if not data.get('beneficiaries'):
        return jsonify({'error': 'No data loaded'}), 400

    beneficiaries_data = data['beneficiaries']

    # Convert to Beneficiary objects for geocoding
    beneficiaries = []
    for b in beneficiaries_data:
        beneficiary = Beneficiary(
            row_number=b['row_number'],
            name=b['name'],
            phone=b['phone'],
            address=b['address'],
            household_size=b.get('household_size', ''),
            items_needed=b.get('items_needed', ''),
            special_items=b.get('special_items', ''),
            notes=b.get('notes', ''),
            errors=b['errors'],
            warnings=b['warnings'].copy(),
            flagged=b['flagged'],
            excluded=b.get('excluded', False)
        )
        beneficiaries.append(beneficiary)

    # Geocode
    geocode_beneficiaries(beneficiaries)

    # Update data
    for i, b in enumerate(beneficiaries):
        beneficiaries_data[i]['latitude'] = b.latitude
        beneficiaries_data[i]['longitude'] = b.longitude
        beneficiaries_data[i]['geocode_error'] = b.geocode_error
        if b.geocode_error:
            if b.geocode_error not in beneficiaries_data[i]['warnings']:
                beneficiaries_data[i]['warnings'].append(f"Geocoding: {b.geocode_error}")
            beneficiaries_data[i]['flagged'] = True

    # Geocode depot if provided
    depot = data.get('depot', {})
    if depot.get('address'):
        lat, lon, error = geocode_address(depot['address'])
        depot['latitude'] = lat
        depot['longitude'] = lon
        depot['error'] = error
        data['depot'] = depot

    data['beneficiaries'] = beneficiaries_data
    data['geocoded'] = True
    _save_data(data)

    # Count results
    success = sum(1 for b in beneficiaries_data if b['latitude'] is not None and not b.get('excluded'))
    failed = sum(1 for b in beneficiaries_data if b['latitude'] is None and not b.get('excluded') and len(b['errors']) == 0)

    flash(f'Geocoding complete: {success} successful, {failed} failed', 'success' if failed == 0 else 'warning')
    return redirect(url_for('main.review'))


@bp.route('/download/failed-geocodes')
def download_failed_geocodes():
    """Download CSV of addresses that failed geocoding."""
    data = _load_data()
    if not data.get('beneficiaries'):
        flash('No data loaded', 'error')
        return redirect(url_for('main.index'))

    if not data.get('geocoded'):
        flash('Please geocode addresses first', 'error')
        return redirect(url_for('main.review'))

    beneficiaries_data = data['beneficiaries']
    csv_content = export_failed_geocodes(beneficiaries_data)

    # Check if there are any failed geocodes
    failed_count = sum(1 for b in beneficiaries_data
                       if b.get('latitude') is None
                       and not b.get('excluded')
                       and len(b.get('errors', [])) == 0)

    if failed_count == 0:
        flash('No failed geocodes to download', 'info')
        return redirect(url_for('main.review'))

    return send_file(
        io.BytesIO(csv_content.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='failed_geocodes.csv'
    )


@bp.route('/generate', methods=['POST'])
def generate():
    """Generate routes and GPX files."""
    data = _load_data()
    if not data.get('beneficiaries'):
        return redirect(url_for('main.index'))

    if not data.get('geocoded'):
        flash('Please geocode addresses first', 'error')
        return redirect(url_for('main.review'))

    max_stops = int(request.form.get('max_stops', 4))
    min_stops = int(request.form.get('min_stops', 3))
    use_osrm = request.form.get('use_osrm', 'true') == 'true'

    # Ensure min <= max
    if min_stops > max_stops:
        min_stops = max_stops

    beneficiaries_data = data['beneficiaries']
    depot = data.get('depot', {})

    # Convert to Beneficiary objects
    beneficiaries = []
    for b in beneficiaries_data:
        if b.get('excluded') or len(b['errors']) > 0:
            continue
        if b['latitude'] is None:
            continue

        beneficiary = Beneficiary(
            row_number=b['row_number'],
            name=b['name'],
            phone=b['phone'],
            address=b['address'],
            household_size=b.get('household_size', ''),
            items_needed=b.get('items_needed', ''),
            special_items=b.get('special_items', ''),
            notes=b.get('notes', ''),
            latitude=b['latitude'],
            longitude=b['longitude']
        )
        beneficiaries.append(beneficiary)

    if not beneficiaries:
        flash('No valid geocoded beneficiaries to route', 'error')
        return redirect(url_for('main.review'))

    # Get depot coordinates
    depot_lat = depot.get('latitude')
    depot_lon = depot.get('longitude')
    depot_name = depot.get('address', 'Depot')

    # Create optimized routes
    routes = create_routes(
        beneficiaries,
        max_stops=max_stops,
        min_stops=min_stops,
        depot_lat=depot_lat,
        depot_lon=depot_lon,
        use_osrm=use_osrm
    )

    # Store depot info for GPX generation
    data['depot_coords'] = {
        'lat': depot_lat,
        'lon': depot_lon,
        'name': depot_name
    }

    # Store routes data
    data['routes'] = [
        {
            'route_number': r.route_number,
            'stop_count': r.stop_count,
            'total_distance': r.total_distance,
            'estimated_duration': r.estimated_duration,
            'route_geometry': r.route_geometry,  # Road coordinates from OSRM
            'beneficiaries': [
                {
                    'name': b.name,
                    'address': b.address,
                    'phone': b.phone,
                    'latitude': b.latitude,
                    'longitude': b.longitude,
                    'household_size': b.household_size,
                    'items_needed': b.items_needed,
                    'special_items': b.special_items,
                    'notes': b.notes,
                    'sequence': b.route_sequence
                }
                for b in r.beneficiaries
            ]
        }
        for r in routes
    ]
    data['depot_address'] = depot.get('address')
    _save_data(data)

    return redirect(url_for('main.results'))


def _build_route_for_gpx(route_data):
    """Build a route-like object for GPX generation from stored data."""
    class RouteWrapper:
        def __init__(self, data):
            self.route_number = data['route_number']
            self.stop_count = data['stop_count']
            self.total_distance = data['total_distance']
            self.estimated_duration = data['estimated_duration']
            self.route_geometry = data.get('route_geometry', [])  # Road coordinates
            self.beneficiaries = [BeneficiaryWrapper(b) for b in data['beneficiaries']]

    class BeneficiaryWrapper:
        def __init__(self, data):
            self.name = data['name']
            self.address = data['address']
            self.phone = data['phone']
            self.latitude = data['latitude']
            self.longitude = data['longitude']
            self.household_size = data.get('household_size', '')
            self.items_needed = data.get('items_needed', '')
            self.special_items = data.get('special_items', '')
            self.notes = data.get('notes', '')

    return RouteWrapper(route_data)


@bp.route('/results')
def results():
    """Download page."""
    data = _load_data()
    if not data.get('routes'):
        return redirect(url_for('main.index'))

    # Generate GPX file names for display
    gpx_files = [(f"route_{r['route_number']:02d}.gpx", '') for r in data['routes']]

    # Generate manifest on-demand
    routes = [_build_route_for_gpx(r) for r in data['routes']]
    manifest = generate_manifest(routes, data.get('depot_address'))

    return render_template('results.html',
                           routes=data['routes'],
                           gpx_files=gpx_files,
                           manifest=manifest)


@bp.route('/download/gpx/<int:index>')
def download_gpx(index):
    """Download a single GPX file."""
    data = _load_data()
    if not data.get('routes'):
        return redirect(url_for('main.index'))

    routes = data['routes']
    if index >= len(routes):
        flash('File not found', 'error')
        return redirect(url_for('main.results'))

    # Generate GPX on-demand
    route = _build_route_for_gpx(routes[index])
    depot_coords = data.get('depot_coords', {}) or {}
    content = generate_gpx(
        route,
        depot_coords.get('lat'),
        depot_coords.get('lon'),
        depot_coords.get('name', 'Depot')
    )

    filename = f"route_{route.route_number:02d}.gpx"
    return send_file(
        io.BytesIO(content.encode('utf-8')),
        mimetype='application/gpx+xml',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/download/manifest')
def download_manifest():
    """Download route manifest (text format)."""
    data = _load_data()
    if not data.get('routes'):
        return redirect(url_for('main.index'))

    # Generate manifest on-demand
    routes = [_build_route_for_gpx(r) for r in data['routes']]
    manifest = generate_manifest(routes, data.get('depot_address'))

    return send_file(
        io.BytesIO(manifest.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name='route_manifest.txt'
    )


@bp.route('/download/manifest.json')
def download_manifest_json():
    """Download route manifest (JSON format for packing slip generator)."""
    data = _load_data()
    if not data.get('routes'):
        return redirect(url_for('main.index'))

    # Generate JSON manifest on-demand
    routes = [_build_route_for_gpx(r) for r in data['routes']]
    manifest = generate_manifest_json(routes, data.get('depot_address'))

    return send_file(
        io.BytesIO(json.dumps(manifest, indent=2).encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name='route_manifest.json'
    )


@bp.route('/download/all')
def download_all():
    """Download all files as ZIP."""
    data = _load_data()
    if not data.get('routes'):
        return redirect(url_for('main.index'))

    depot_coords = data.get('depot_coords', {}) or {}
    routes_data = data['routes']

    # Generate all GPX files on-demand
    gpx_files = []
    for route_data in routes_data:
        route = _build_route_for_gpx(route_data)
        content = generate_gpx(
            route,
            depot_coords.get('lat'),
            depot_coords.get('lon'),
            depot_coords.get('name', 'Depot')
        )
        filename = f"route_{route.route_number:02d}.gpx"
        gpx_files.append((filename, content))

    # Generate manifests on-demand
    routes = [_build_route_for_gpx(r) for r in routes_data]
    manifest_txt = generate_manifest(routes, data.get('depot_address'))
    manifest_json = generate_manifest_json(routes, data.get('depot_address'))

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in gpx_files:
            zf.writestr(filename, content.encode('utf-8'))
        zf.writestr('manifest.txt', manifest_txt.encode('utf-8'))
        zf.writestr('route_manifest.json', json.dumps(manifest_json, indent=2).encode('utf-8'))

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='delivery_routes.zip'
    )


@bp.route('/reset')
def reset():
    """Clear session and start over."""
    # Delete data file
    data_id = session.get('data_id')
    if data_id:
        data_file = os.path.join(current_app.config['DATA_DIR'], f'{data_id}.json')
        if os.path.exists(data_file):
            os.remove(data_file)
    session.clear()
    return redirect(url_for('main.index'))
