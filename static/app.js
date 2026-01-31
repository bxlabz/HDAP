let addresses = [];

const startAddressInput = document.getElementById('startAddress');
const maxStopsSlider = document.getElementById('maxStops');
const maxStopsLabel = document.getElementById('maxStopsLabel');
const radiusSlider = document.getElementById('radiusMiles');
const radiusLabel = document.getElementById('radiusLabel');
const csvFileInput = document.getElementById('csvFile');
const fileStatus = document.getElementById('fileStatus');
const optimizeBtn = document.getElementById('optimizeBtn');
const errorBox = document.getElementById('errorBox');
const errorText = document.getElementById('errorText');
const progressBox = document.getElementById('progressBox');
const progressText = document.getElementById('progressText');
const progressBar = document.getElementById('progressBar');
const results = document.getElementById('results');

maxStopsSlider.addEventListener('input', (e) => {
    maxStopsLabel.textContent = e.target.value;
});

radiusSlider.addEventListener('input', (e) => {
    radiusLabel.textContent = e.target.value;
});

// Proper CSV parser that handles quoted fields with commas
function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        const nextChar = line[i + 1];
        
        if (char === '"') {
            if (inQuotes && nextChar === '"') {
                // Escaped quote
                current += '"';
                i++; // Skip next quote
            } else {
                // Toggle quote mode
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            // Field separator (only when not in quotes)
            result.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }
    
    // Add last field
    result.push(current.trim());
    return result;
}

csvFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            const text = event.target.result;
            const lines = text.split(/\r?\n/).filter(line => line.trim());
            
            if (lines.length === 0) {
                showError('CSV file is empty');
                return;
            }
            
            console.log('First line (header):', lines[0]);
            
            // Parse header using proper CSV parser
            const headers = parseCSVLine(lines[0]).map(h => h.trim().toLowerCase());
            console.log('Parsed headers:', headers);
            
            const addressIndex = headers.findIndex(h => 
                h.includes('address') || h.includes('location') || h.includes('street') || h.includes('addr')
            );
            
            if (addressIndex === -1) {
                showError('Could not find address column. Headers: ' + headers.join(', '));
                return;
            }
            
            console.log('Address column index:', addressIndex);
            
            addresses = [];
            for (let i = 1; i < lines.length; i++) {
                const cols = parseCSVLine(lines[i]);
                let addr = cols[addressIndex]?.trim();
                
                if (addr && addr.length > 0) {
                    // Remove any remaining quotes
                    addr = addr.replace(/^["']|["']$/g, '');
                    addresses.push(addr);
                    console.log(`Address ${i}: "${addr}"`);
                }
            }
            
            if (addresses.length === 0) {
                showError('No valid addresses found');
                return;
            }
            
            console.log(`Total addresses loaded: ${addresses.length}`);
            
            fileStatus.textContent = `✓ Loaded ${addresses.length} addresses`;
            fileStatus.className = 'text-sm text-green-600 mt-2';
            hideError();
        } catch (err) {
            showError('Error parsing file: ' + err.message);
            console.error(err);
        }
    };
    reader.readAsText(file);
});

optimizeBtn.addEventListener('click', async () => {
    const startAddress = startAddressInput.value.trim();
    const maxStops = parseInt(maxStopsSlider.value);
    const radiusMiles = parseInt(radiusSlider.value);
    
    if (!startAddress) {
        showError('Please enter a start/end address');
        return;
    }
    
    if (addresses.length === 0) {
        showError('Please upload a file');
        return;
    }
    
    optimizeBtn.disabled = true;
    hideError();
    results.classList.add('hidden');
    
    try {
        showProgress('Preparing addresses...', 5);
        
        const allAddresses = [startAddress, ...addresses];
        
        console.log('Sending to geocoder:', allAddresses);
        
        showProgress(`Geocoding ${allAddresses.length} addresses with ${radiusMiles} mile radius filter...`, 10);
        
        const geocodeRes = await fetch('/api/geocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                addresses: allAddresses,
                originalAddresses: allAddresses,
                radiusMiles: radiusMiles
            })
        });
        
        if (geocodeRes.status === 401) {
            window.location.href = '/login';
            return;
        }
        
        const geocodeData = await geocodeRes.json();
        
        if (geocodeData.error) {
            throw new Error(geocodeData.error);
        }
        
        const geocoded = geocodeData.results.filter(r => !r.error);
        const failed = geocodeData.results.filter(r => r.error);
        
        console.log('Geocoded:', geocoded);
        console.log('Failed:', failed);
        
        if (geocoded.length === 0) {
            throw new Error('Failed to geocode any addresses');
        }
        
        showProgress(`Geocoded ${geocoded.length}/${allAddresses.length} addresses. Optimizing routes...`, 60);
        
        const start = geocoded[0];
        const locations = geocoded.slice(1);
        
        const optimizeRes = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, locations, maxStops })
        });
        
        if (optimizeRes.status === 401) {
            window.location.href = '/login';
            return;
        }
        
        const optimizeData = await optimizeRes.json();
        
        if (optimizeData.error) {
            throw new Error(optimizeData.error);
        }
        
        showProgress('Complete!', 100);
        displayRoutes(optimizeData.routes);
        
        if (failed.length > 0) {
            const failedDetails = failed.map(f => `• ${f.address}: ${f.error}`).join('<br>');
            showError(`Could not geocode ${failed.length} address(es):<br><small>${failedDetails}</small>`);
        }
    } catch (err) {
        showError(err.message);
        console.error(err);
    } finally {
        optimizeBtn.disabled = false;
    }
});

window.routesData = [];

function displayRoutes(routeData) {
    window.routesData = routeData;
    results.innerHTML = '<h2 class="text-2xl font-bold text-gray-800 mb-4">Optimized Routes</h2>';
    
    routeData.forEach((route, idx) => {
        const routeDiv = document.createElement('div');
        routeDiv.className = 'bg-gray-50 rounded-lg p-6 border border-gray-200 mb-4';
        
        const header = `
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h3 class="text-lg font-semibold text-gray-800">Route ${idx + 1}</h3>
                    <p class="text-sm text-gray-600">
                        ${route.stops.length - 1} stops • ${route.distance.toFixed(2)} mi (estimated)
                    </p>
                </div>
                <button onclick="exportGPX(${idx})" 
                        class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors">
                    Export GPX
                </button>
            </div>
        `;
        
        const stops = route.stops.map((stop, stopIdx) => {
            const icon = stopIdx === 0 || stopIdx === route.stops.length - 1 ? '🏠' : stopIdx;
            const originalAddr = stop.originalAddress || stop.address;
            const distInfo = stop.distanceFromStart ? ` • ${stop.distanceFromStart} mi from start` : '';
            return `
                <div class="text-sm text-gray-700 flex items-start gap-2 mb-2">
                    <span class="font-semibold text-indigo-600 min-w-[30px]">${icon}</span>
                    <div>
                        <div class="font-medium">${originalAddr}${distInfo}</div>
                        <div class="text-xs text-gray-500">${stop.displayName}</div>
                    </div>
                </div>
            `;
        }).join('');
        
        routeDiv.innerHTML = header + '<div class="max-h-96 overflow-y-auto">' + stops + '</div>';
        results.appendChild(routeDiv);
    });
    
    results.classList.remove('hidden');
}

function exportGPX(routeIndex) {
    const routeData = window.routesData[routeIndex];
    
    const escapeXml = (str) => {
        return String(str || '').replace(/[<>&'"]/g, (c) => {
            const map = {'<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;'};
            return map[c];
        });
    };
    
    const waypoints = routeData.stops.map((stop, idx) => {
        const name = idx === 0 || idx === routeData.stops.length - 1 ? 'Start/End' : `Stop ${idx}`;
        const desc = stop.originalAddress || stop.address;
        return `  <wpt lat="${stop.lat}" lon="${stop.lon}">
    <name>${escapeXml(name)}</name>
    <desc>${escapeXml(desc)}</desc>
  </wpt>`;
    }).join('\n');
    
    const trackpoints = routeData.stops.map(stop => 
        `      <trkpt lat="${stop.lat}" lon="${stop.lon}"></trkpt>`
    ).join('\n');
    
    const gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Route Optimizer" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>Route ${routeIndex + 1}</name>
    <desc>Optimized route with ${routeData.stops.length - 1} stops, ${routeData.distance.toFixed(2)} mi</desc>
  </metadata>
  <trk>
    <name>Route ${routeIndex + 1}</name>
    <trkseg>
${trackpoints}
    </trkseg>
  </trk>
${waypoints}
</gpx>`;
    
    const dataUrl = 'data:application/gpx+xml;charset=utf-8,' + encodeURIComponent(gpx);
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `route_${routeIndex + 1}.gpx`;
    a.click();
}

function showError(msg) {
    errorText.innerHTML = msg;
    errorBox.classList.remove('hidden');
}

function hideError() {
    errorBox.classList.add('hidden');
}

function showProgress(msg, percent = 0) {
    progressText.textContent = msg;
    progressBar.style.width = percent + '%';
    progressBox.classList.remove('hidden');
}