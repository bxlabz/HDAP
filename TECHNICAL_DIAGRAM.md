# Technical Architecture

## System Overview

```
                                    ┌─────────────────────────────────────┐
                                    │         DOCKER ENVIRONMENT          │
                                    │                                     │
┌──────────┐                        │  ┌─────────────────────────────┐   │
│          │                        │  │     TEXT GENERATOR          │   │
│   USER   │───── :8081 ──────────────▶│     (textgen-container)     │   │
│          │                        │  │                             │   │
│  Browser │                        │  │  • CSV Parser               │   │
│          │                        │  │  • Phone Formatter          │   │
│          │                        │  │  • Bilingual Text Gen       │   │
│          │                        │  │  • ZIP Packaging            │   │
│          │                        │  └─────────────────────────────┘   │
│          │                        │                                     │
│          │                        │  ┌─────────────────────────────┐   │
│          │───── :8080 ──────────────▶│     ROUTE GENERATOR         │   │
│          │                        │  │     (routing-container)     │   │
│          │                        │  │                             │   │
└──────────┘                        │  │  • CSV Parser               │   │
     │                              │  │  • Geocoder ─────────────────────────▶ Nominatim API
     │                              │  │  • K-means Clustering       │   │     (OpenStreetMap)
     │                              │  │  • Route Optimizer ──────────────────▶ OSRM API
     │                              │  │  • GPX Generator            │   │     (Routing)
     ▼                              │  └─────────────────────────────┘   │
┌──────────┐                        │                                     │
│  Output  │                        │  ┌─────────────────────────────┐   │
│  Files   │                        │  │     SHARED VOLUME           │   │
├──────────┤                        │  │     (shared/)               │   │
│ .txt     │◀───────────────────────│  │                             │   │
│ .gpx     │                        │  │  • sample_data.csv          │   │
│ .zip     │                        │  │  • User uploads             │   │
│ manifest │                        │  └─────────────────────────────┘   │
└──────────┘                        └─────────────────────────────────────┘
```

---

## Container Details

### Text Generator Container (Port 8081)

**Purpose:** Generate bilingual packing slips for delivery volunteers

```
textgen-container/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py           # Flask app entry
    ├── routes.py         # HTTP endpoints
    ├── csv_parser.py     # Parse uploaded CSV
    ├── phone_formatter.py # Format phone numbers
    ├── text_generator.py # Generate packing slips
    └── templates/
        ├── index.html    # Upload page
        ├── review.html   # Data review page
        └── results.html  # Download page
```

**Dependencies:**
| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0 | Web framework |
| phonenumbers | 8.13.0 | Phone formatting |

---

### Route Generator Container (Port 8080)

**Purpose:** Create optimized delivery routes with GPX export

```
routing-container/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py           # Flask app entry
    ├── routes.py         # HTTP endpoints
    ├── csv_parser.py     # Parse uploaded CSV
    ├── geocoder.py       # Address → coordinates
    ├── optimizer.py      # Route optimization
    ├── gpx_generator.py  # Generate GPX files
    └── templates/
        ├── index.html    # Upload page
        ├── review.html   # Review & geocode
        └── results.html  # Download routes
```

**Dependencies:**
| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0 | Web framework |
| geopy | 2.4.1 | Nominatim geocoding |
| scikit-learn | 1.3.2 | K-means clustering |
| gpxpy | 1.6.1 | GPX file generation |
| requests | 2.31.0 | OSRM API calls |

---

## Data Flow

### Text Generator Flow

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  CSV    │    │  Parse  │    │ Format  │    │Generate │    │ Package │
│ Upload  │───▶│  Data   │───▶│ Phones  │───▶│  Text   │───▶│  ZIP    │
│         │    │         │    │         │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                   │
                   ▼
              ┌─────────┐
              │ Review  │
              │ & Edit  │
              └─────────┘
```

### Route Generator Flow

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  CSV    │    │  Parse  │    │Geocode  │    │ Cluster │    │Optimize │    │Generate │
│ Upload  │───▶│  Data   │───▶│Addresses│───▶│ K-means │───▶│  TSP    │───▶│  GPX    │
│         │    │         │    │         │    │         │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                   │              │
                   ▼              ▼
              ┌─────────┐    ┌─────────┐
              │ Review  │    │Nominatim│
              │ & Edit  │    │   API   │
              └─────────┘    └─────────┘
```

---

## Route Optimization Algorithm

### Step 1: Geocoding

```
Input:  "123 Main St, Minneapolis, MN 55401"
Output: { lat: 44.9778, lon: -93.2650 }

Process:
1. Send address to Nominatim API
2. Parse response for coordinates
3. Handle rate limiting (1 req/sec)
4. Retry with address variations if needed
```

### Step 2: K-means Clustering

```
Input:  List of geocoded locations
Output: Groups of nearby locations

Process:
1. Calculate number of clusters (total ÷ max_stops)
2. Run K-means on lat/lon coordinates
3. Assign each location to nearest centroid
4. Result: Routes with geographically close stops
```

### Step 3: TSP Optimization (per cluster)

```
Input:  Cluster of locations + optional depot
Output: Optimized visit order

Primary: OSRM Trip API
1. Send coordinates to OSRM
2. Receive optimized waypoint order
3. Get distance and duration estimates

Fallback: Nearest Neighbor
1. Start at depot (or first location)
2. Visit nearest unvisited location
3. Repeat until all visited
4. Return to start
```

### Step 4: GPX Generation

```
Input:  Optimized route with coordinates
Output: GPX file with waypoints + track

Structure:
├── <metadata>      # Route name, description
├── <wpt>           # Waypoints (stops)
│   ├── name        # Stop number
│   └── desc        # Address, phone, notes
└── <trk>           # Track
    └── <trkseg>    # Track segment
        └── <trkpt> # Track points
```

---

## External APIs

### Nominatim (OpenStreetMap)

| Attribute | Value |
|-----------|-------|
| Purpose | Geocoding (address → coordinates) |
| Rate Limit | 1 request per second |
| Cost | Free |
| Auth | None required |
| Endpoint | `https://nominatim.openstreetmap.org/search` |

### OSRM (Open Source Routing Machine)

| Attribute | Value |
|-----------|-------|
| Purpose | Route optimization (TSP) |
| Rate Limit | Varies (public demo server) |
| Cost | Free (demo), self-host for production |
| Auth | None required |
| Endpoint | `http://router.project-osrm.org/trip/v1/driving/` |

---

## Docker Configuration

### docker-compose.yml

```yaml
version: '3.8'

services:
  textgen:
    build: ./textgen-container
    ports:
      - "8081:8081"
    volumes:
      - ./shared:/app/shared

  routing:
    build: ./routing-container
    ports:
      - "8080:8080"
    volumes:
      - ./shared:/app/shared
```

### Container Base Image

Both containers use `python:3.11-slim`

---

## File Naming Conventions

### Packing Slips

```
Route_{route_num}_{sequence}_{initials}_{last4phone}.txt

Example: Route_1_01_MG_4567.txt
         │      │  │   │    │
         │      │  │   │    └── Last 4 digits of phone
         │      │  │   └─────── Name initials
         │      │  └─────────── Sequence in route (01, 02...)
         │      └────────────── Route number
         └───────────────────── Prefix
```

### GPX Files

```
route_{route_num}.gpx

Example: route_01.gpx
```

### Manifest

```
route_manifest.txt   # Human-readable summary
route_manifest.json  # Machine-readable data
```
