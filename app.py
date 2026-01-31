from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, render_template_string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import os
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY')

if not app.secret_key:
    raise ValueError("SECRET_KEY environment variable must be set in .env file")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

admin_password = os.environ.get('ADMIN_PASSWORD')
if not admin_password:
    raise ValueError("ADMIN_PASSWORD environment variable must be set in .env file")

users_db = {
    'admin': {
        'password_hash': generate_password_hash(admin_password),
        'id': 1
    }
}

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    for username, data in users_db.items():
        if data['id'] == int(user_id):
            return User(data['id'], username)
    return None

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Route Optimizer</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen flex items-center justify-center p-6">
    <div class="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
        <h1 class="text-3xl font-bold text-gray-800 mb-6 text-center">Route Optimizer</h1>
        <h2 class="text-xl text-gray-600 mb-6 text-center">Login</h2>
        
        {% if error %}
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <p class="text-red-700 text-sm">{{ error }}</p>
        </div>
        {% endif %}
        
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Username</label>
                <input type="text" name="username" required
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                <input type="password" name="password" required
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
            </div>
            <button type="submit" 
                    class="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700">
                Login
            </button>
        </form>
    </div>
</body>
</html>
'''

def create_address_variations(address):
    """Create multiple variations of an address to try"""
    variations = [address]  # Always try original first
    
    # Remove suite/unit/apt numbers
    no_suite = re.sub(r'\s+(Suite|Ste|Unit|Apt|#)\s*\d+[A-Z]?', '', address, flags=re.IGNORECASE)
    if no_suite != address:
        variations.append(no_suite)
    
    # Expand abbreviations
    expanded = address
    expanded = re.sub(r'\bRd\b', 'Road', expanded, flags=re.IGNORECASE)
    expanded = re.sub(r'\bDr\b', 'Drive', expanded, flags=re.IGNORECASE)
    expanded = re.sub(r'\bAve\b', 'Avenue', expanded, flags=re.IGNORECASE)
    expanded = re.sub(r'\bSt\b', 'Street', expanded, flags=re.IGNORECASE)
    expanded = re.sub(r'\bBlvd\b', 'Boulevard', expanded, flags=re.IGNORECASE)
    expanded = re.sub(r'\bPl\b', 'Place', expanded, flags=re.IGNORECASE)
    if expanded != address:
        variations.append(expanded)
    
    # Try without the street number for vague addresses
    just_street = re.sub(r'^\d+\s+', '', address)
    if just_street != address:
        variations.append(just_street)
    
    return variations

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = users_db.get(username)
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], username)
            login_user(user)
            return redirect(url_for('index'))
        
        return render_template_string(LOGIN_HTML, error='Invalid username or password')
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
@login_required
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/geocode', methods=['POST'])
@login_required
def geocode():
    try:
        data = request.json
        addresses = data.get('addresses', [])
        original_addresses = data.get('originalAddresses', addresses)
        radius_miles = data.get('radiusMiles', 100)
        
        geolocator = Nominatim(user_agent="route_optimizer_v1", timeout=10)
        results = []
        
        start_location = None
        if len(addresses) > 0:
            time.sleep(1.1)
            start_addr = addresses[0]
            print(f"\n=== Geocoding START address ===")
            print(f"Original: {addresses[0]}")
            
            # Try variations for start address
            for variation in create_address_variations(start_addr):
                print(f"Trying: {variation}")
                start_location = geolocator.geocode(variation, exactly_one=True, addressdetails=True)
                if start_location:
                    break
                time.sleep(0.5)
            
            if start_location:
                raw_address = start_location.raw.get('address', {})
                original = original_addresses[0] if len(original_addresses) > 0 else addresses[0]
                
                results.append({
                    'address': addresses[0],
                    'originalAddress': original,
                    'lat': start_location.latitude,
                    'lon': start_location.longitude,
                    'displayName': start_location.address,
                    'state': raw_address.get('state', ''),
                    'country': raw_address.get('country', ''),
                    'distanceFromStart': 0
                })
                
                start_coords = (start_location.latitude, start_location.longitude)
                print(f"✓ FOUND: {start_location.address}")
                print(f"  Coordinates: {start_coords}")
                print(f"  Using {radius_miles} mile radius filter\n")
            else:
                print(f"✗ START ADDRESS NOT FOUND\n")
                results.append({
                    'address': original_addresses[0] if len(original_addresses) > 0 else addresses[0],
                    'error': 'Start address not found'
                })
                return jsonify({'results': results})
        
        for idx in range(1, len(addresses)):
            addr_original = addresses[idx]
            original = original_addresses[idx] if idx < len(original_addresses) else addr_original
            
            try:
                print(f"\n=== Geocoding address {idx}/{len(addresses)-1} ===")
                print(f"Original: {addr_original}")
                
                found_location = None
                variations = create_address_variations(addr_original)
                
                for var_idx, variation in enumerate(variations):
                    if var_idx > 0:
                        print(f"Trying variation {var_idx}: {variation}")
                    
                    time.sleep(1.1)
                    locations = geolocator.geocode(variation, exactly_one=False, limit=5, addressdetails=True)
                    
                    if locations:
                        print(f"Found {len(locations)} candidate(s):")
                        
                        for i, location in enumerate(locations, 1):
                            location_coords = (location.latitude, location.longitude)
                            distance_miles = geodesic(start_coords, location_coords).miles
                            
                            print(f"  {i}. {location.address}")
                            print(f"     Distance: {distance_miles:.1f} mi from start")
                            
                            if distance_miles <= radius_miles:
                                print(f"     ✓ WITHIN RADIUS - ACCEPTING")
                                found_location = location
                                break
                        
                        if found_location:
                            break
                
                if found_location:
                    raw_address = found_location.raw.get('address', {})
                    location_coords = (found_location.latitude, found_location.longitude)
                    distance_miles = geodesic(start_coords, location_coords).miles
                    
                    results.append({
                        'address': addr_original,
                        'originalAddress': original,
                        'lat': found_location.latitude,
                        'lon': found_location.longitude,
                        'displayName': found_location.address,
                        'state': raw_address.get('state', ''),
                        'country': raw_address.get('country', ''),
                        'distanceFromStart': round(distance_miles, 1)
                    })
                else:
                    print(f"✗ No valid location found (tried {len(variations)} variations)")
                    results.append({
                        'address': original,
                        'error': 'Not found'
                    })
                    
            except Exception as e:
                print(f"✗ Error: {e}")
                results.append({
                    'address': original,
                    'error': str(e)
                })
        
        print(f"\n=== GEOCODING COMPLETE ===")
        print(f"Success: {len([r for r in results if 'error' not in r])}/{len(results)}")
        print(f"Failed: {len([r for r in results if 'error' in r])}/{len(results)}\n")
        
        return jsonify({'results': results})
    except Exception as e:
        print(f"Geocode API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/optimize', methods=['POST'])
@login_required
def optimize_route():
    try:
        data = request.json
        locations = data.get('locations', [])
        start = data.get('start')
        max_stops = data.get('maxStops', 10)
        
        if not start or not locations:
            return jsonify({'error': 'Missing required data'}), 400
        
        clusters = cluster_by_proximity(locations, start, max_stops)
        
        routes = []
        for cluster in clusters:
            optimized = nearest_neighbor_tsp(cluster, start)
            distance = calculate_route_distance(optimized)
            
            routes.append({
                'stops': optimized,
                'distance': distance
            })
        
        return jsonify({'routes': routes})
    except Exception as e:
        print(f"Optimize error: {e}")
        return jsonify({'error': str(e)}), 500

def cluster_by_proximity(locations, start, max_stops):
    if not locations:
        return []
    
    unassigned = locations.copy()
    clusters = []
    start_coords = (start['lat'], start['lon'])
    
    while unassigned:
        current_cluster = []
        
        nearest_to_start = min(unassigned, key=lambda loc: 
            geodesic(start_coords, (loc['lat'], loc['lon'])).miles
        )
        current_cluster.append(nearest_to_start)
        unassigned.remove(nearest_to_start)
        
        while len(current_cluster) < max_stops and unassigned:
            last_in_cluster = current_cluster[-1]
            last_coords = (last_in_cluster['lat'], last_in_cluster['lon'])
            
            nearest = min(unassigned, key=lambda loc:
                geodesic(last_coords, (loc['lat'], loc['lon'])).miles
            )
            
            current_cluster.append(nearest)
            unassigned.remove(nearest)
        
        clusters.append(current_cluster)
        print(f"Created cluster with {len(current_cluster)} locations")
    
    return clusters

def nearest_neighbor_tsp(locations, start):
    unvisited = locations.copy()
    route = [start]
    current = start
    
    while unvisited:
        nearest = None
        min_dist = float('inf')
        
        for loc in unvisited:
            dist = geodesic(
                (current['lat'], current['lon']),
                (loc['lat'], loc['lon'])
            ).miles
            
            if dist < min_dist:
                min_dist = dist
                nearest = loc
        
        if nearest:
            route.append(nearest)
            current = nearest
            unvisited.remove(nearest)
    
    route.append(start)
    return route

def calculate_route_distance(route):
    total = 0
    for i in range(len(route) - 1):
        dist = geodesic(
            (route[i]['lat'], route[i]['lon']),
            (route[i + 1]['lat'], route[i + 1]['lon'])
        ).miles
        total += dist
    return total * 1.35

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
