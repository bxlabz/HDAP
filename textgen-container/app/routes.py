from flask import Blueprint, render_template, request, session, redirect, url_for, send_file, flash, current_app
import io
import zipfile
import json
import uuid
import os
from app.csv_parser import parse_csv, Beneficiary
from app.text_generator import generate_all_slips, generate_all_slips_with_routes, generate_filename, generate_packing_slip
from app.phone_formatter import format_phone

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


def _parse_manifest(manifest_content):
    """Parse the route manifest JSON and create a lookup for beneficiaries."""
    try:
        manifest = json.loads(manifest_content)
        # Create a lookup by name+phone for matching
        route_assignments = {}
        for route in manifest.get('routes', []):
            route_num = route['route_number']
            for ben in route['beneficiaries']:
                # Use name + phone as key for matching
                key = (ben['name'].strip().lower(), ben['phone'].strip())
                route_assignments[key] = {
                    'route_number': route_num,
                    'sequence': ben['sequence'],
                    'name': ben['name'],
                    'phone': ben['phone']
                }
        return route_assignments, None
    except (json.JSONDecodeError, KeyError) as e:
        return None, f"Error parsing manifest: {str(e)}"


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

    # Check for optional manifest file
    route_assignments = None
    manifest_file = request.files.get('manifest')
    if manifest_file and manifest_file.filename:
        try:
            manifest_content = manifest_file.read().decode('utf-8')
            route_assignments, error = _parse_manifest(manifest_content)
            if error:
                flash(f'Warning: {error}. Proceeding without route assignments.', 'warning')
                route_assignments = None
            else:
                flash(f'Route manifest loaded: {len(route_assignments)} beneficiaries mapped to routes', 'success')
        except Exception as e:
            flash(f'Warning: Could not read manifest file: {str(e)}', 'warning')

    # Store in file
    beneficiaries_data = []
    for b in result.beneficiaries:
        ben_data = {
            'row_number': b.row_number,
            'name': b.name,
            'phone': b.phone,
            'address': b.address,
            'household_size': b.household_size,
            'items_needed': b.items_needed,
            'special_items': b.special_items,
            'contact_preference': b.contact_preference,
            'notes': b.notes,
            'errors': b.errors,
            'warnings': b.warnings,
            'flagged': b.flagged,
            'route_number': None,
            'route_sequence': None
        }

        # Try to match with route assignment
        if route_assignments:
            key = (b.name.strip().lower(), b.phone.strip())
            if key in route_assignments:
                assignment = route_assignments[key]
                ben_data['route_number'] = assignment['route_number']
                ben_data['route_sequence'] = assignment['sequence']

        beneficiaries_data.append(ben_data)

    data = {
        'beneficiaries': beneficiaries_data,
        'warnings': result.warnings,
        'generated_slips': None,
        'has_routes': route_assignments is not None
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

    beneficiaries = []
    for b in data['beneficiaries']:
        formatted_phone, phone_valid = format_phone(b['phone'])
        beneficiaries.append({
            **b,
            'formatted_phone': formatted_phone,
            'phone_valid': phone_valid
        })

    return render_template('review.html',
                           beneficiaries=beneficiaries,
                           warnings=data.get('warnings', []))


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

    data['beneficiaries'] = beneficiaries
    _save_data(data)

    flash('Data updated successfully', 'success')
    return redirect(url_for('main.review'))


@bp.route('/generate', methods=['POST'])
def generate():
    """Generate packing slips."""
    data = _load_data()
    if not data.get('beneficiaries'):
        return redirect(url_for('main.index'))

    # Check if we have route assignments from manifest
    has_routes = data.get('has_routes', False)

    # Get valid (non-excluded, no errors) beneficiaries
    valid_beneficiaries = []
    for b in data['beneficiaries']:
        if b.get('excluded'):
            continue
        if len(b['errors']) > 0:
            continue
        valid_beneficiaries.append(b)

    if not valid_beneficiaries:
        flash('No valid beneficiaries to process', 'error')
        return redirect(url_for('main.review'))

    if has_routes:
        # Use route-aware generation
        slips = generate_all_slips_with_routes(valid_beneficiaries)
        flash(f'Generated {len(slips)} packing slips organized by delivery route', 'success')
    else:
        # Fall back to sequential generation
        route_num = int(request.form.get('route_num', 1))

        # Convert to Beneficiary objects for the old function
        beneficiaries = []
        for b in valid_beneficiaries:
            beneficiary = Beneficiary(
                row_number=b['row_number'],
                name=b['name'],
                phone=b['phone'],
                address=b['address'],
                household_size=b['household_size'],
                items_needed=b['items_needed'],
                special_items=b.get('special_items', ''),
                contact_preference=b.get('contact_preference', ''),
                notes=b.get('notes', ''),
                errors=b['errors'],
                warnings=b['warnings'],
                flagged=b['flagged']
            )
            beneficiaries.append(beneficiary)

        slips = generate_all_slips(beneficiaries, route_num)
        data['route_num'] = route_num

    data['generated_slips'] = slips
    _save_data(data)

    return redirect(url_for('main.results'))


@bp.route('/results')
def results():
    """Download page."""
    data = _load_data()
    if not data.get('generated_slips'):
        return redirect(url_for('main.index'))

    slips = data['generated_slips']
    return render_template('results.html',
                           slips=slips,
                           count=len(slips))


@bp.route('/download/<int:index>')
def download_single(index):
    """Download a single packing slip."""
    data = _load_data()
    if not data.get('generated_slips'):
        return redirect(url_for('main.index'))

    slips = data['generated_slips']
    if index >= len(slips):
        flash('File not found', 'error')
        return redirect(url_for('main.results'))

    filename, content = slips[index]
    return send_file(
        io.BytesIO(content.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/download/all')
def download_all():
    """Download all packing slips as ZIP."""
    data = _load_data()
    if not data.get('generated_slips'):
        return redirect(url_for('main.index'))

    slips = data['generated_slips']

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in slips:
            zf.writestr(filename, content.encode('utf-8'))

    zip_buffer.seek(0)

    route_num = data.get('route_num', 1)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'packing_slips_route_{route_num}.zip'
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
