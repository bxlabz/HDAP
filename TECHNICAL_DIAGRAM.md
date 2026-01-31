# Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOCKER ENVIRONMENT                                 │
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐   │
│   │             │      │             │      │      FLASK APP          │   │
│   │   NGINX     │      │   NGINX     │      │                         │   │
│   │   :8080     │─────▶│   :80       │─────▶│  • Authentication       │   │
│   │             │      │   (proxy)   │      │  • Geocoding API        │   │
│   │             │      │             │      │  • Route Optimization   │   │
│   └─────────────┘      └─────────────┘      │  • Static Files         │   │
│         ▲                                    │                         │   │
│         │                                    └───────────┬─────────────┘   │
│         │                                                │                  │
└─────────│────────────────────────────────────────────────│──────────────────┘
          │                                                │
          │                                                ▼
    ┌─────┴─────┐                                 ┌─────────────────┐
    │           │                                 │   NOMINATIM     │
    │   USER    │                                 │   (External)    │
    │  BROWSER  │                                 │                 │
    │           │◀────── GPX Download ────────────│  OpenStreetMap  │
    └───────────┘                                 └─────────────────┘
```

---

## Data Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  CSV     │    │  PARSE   │    │ GEOCODE  │    │ CLUSTER  │    │ OPTIMIZE │    │   GPX    │
│  Upload  │───▶│  CSV     │───▶│ Addresses│───▶│ Locations│───▶│  Routes  │───▶│  Export  │
│          │    │          │    │          │    │          │    │          │    │          │
│ Raw Text │    │ String[] │    │ {lat,lon}│    │ Groups[] │    │ Route[]  │    │ XML File │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

---

## Component Details

### 1. Nginx Reverse Proxy

**Purpose:** Entry point for all HTTP requests

| Feature | Configuration |
|---------|---------------|
| Rate Limiting | 10 req/sec, burst of 20 |
| Max Upload | 10MB |
| Read Timeout | 300 seconds |
| Connect Timeout | 75 seconds |

### 2. Flask Application Server

**Purpose:** Core backend handling all business logic

**Modules:**
- `flask-login` - Session management & authentication
- `geopy` - Geocoding via Nominatim
- `werkzeug` - Password hashing (PBKDF2)

**Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/login` | GET/POST | No | User authentication |
| `/logout` | GET | Yes | End session |
| `/` | GET | Yes | Main application |
| `/api/geocode` | POST | Yes | Address → coordinates |
| `/api/optimize` | POST | Yes | Generate routes |

### 3. Geocoding Service

**Purpose:** Convert street addresses to latitude/longitude

**Process:**
1. Try original address
2. Try variations (expand abbreviations, remove suite numbers)
3. Filter results by radius from start point
4. Return first match within radius

**Rate Limit:** 1 request per second (Nominatim requirement)

### 4. Route Optimization Engine

**Purpose:** Create efficient delivery routes

**Algorithm:** Nearest Neighbor TSP with Proximity Clustering

### 5. GPX Export

**Purpose:** Generate GPS-compatible route files

**Format:** GPX 1.1 (GPS Exchange Format)

**Contents:**
- Waypoints with names/descriptions
- Track segments for navigation
- Metadata (route name, distance)

---

## Route Optimization Algorithm

### Step 1: Proximity Clustering

```
Input: List of geocoded locations, max stops per route

Algorithm:
1. Start with location nearest to depot
2. Add nearest unassigned location to cluster
3. Repeat until cluster reaches max stops
4. Start new cluster with remaining locations
5. Repeat until all locations assigned
```

### Step 2: Nearest Neighbor TSP

```
Input: Cluster of locations, depot

Algorithm:
1. Start at depot
2. Visit nearest unvisited location
3. Repeat until all locations visited
4. Return to depot

Output: Ordered route
```

### Step 3: Distance Calculation

```
Method: Geodesic (Vincenty formula)
Adjustment: × 1.35 (approximates road vs straight-line distance)
```

---

## Security Features

| Feature | Implementation |
|---------|----------------|
| Password Storage | PBKDF2 hash (Werkzeug) |
| Session Management | Flask-Login with secure cookies |
| Environment Secrets | `.env` file (not in repo) |
| Rate Limiting | Nginx limit_req_zone |

---

## Technology Stack

```
┌─────────────────────────────────────────────┐
│                 FRONTEND                     │
│  HTML5 • JavaScript • TailwindCSS           │
├─────────────────────────────────────────────┤
│                 BACKEND                      │
│  Python 3.11 • Flask 3.0 • Gunicorn         │
├─────────────────────────────────────────────┤
│              WEB SERVER                      │
│  Nginx (Alpine)                             │
├─────────────────────────────────────────────┤
│             CONTAINERIZATION                 │
│  Docker • Docker Compose                    │
├─────────────────────────────────────────────┤
│            EXTERNAL SERVICES                 │
│  OpenStreetMap Nominatim (Geocoding)        │
└─────────────────────────────────────────────┘
```

---

## File Descriptions

| File | Purpose |
|------|---------|
| `app.py` | Flask application with all routes and logic |
| `requirements.txt` | Python package dependencies |
| `Dockerfile` | Container image build instructions |
| `docker-compose.yml` | Multi-container orchestration |
| `nginx.conf` | Reverse proxy configuration |
| `static/index.html` | Frontend user interface |
| `static/app.js` | Frontend JavaScript logic |
| `.env.example` | Template for environment variables |
