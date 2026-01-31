# Installation Guide

## Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Git | 2.30+ | Version control (optional) |

> **Note:** Docker Desktop for Windows/Mac includes Docker Compose.

---

## Project Structure

```
HDAP/
├── app.py              # Flask backend application
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build instructions
├── docker-compose.yml  # Service orchestration
├── nginx.conf          # Reverse proxy configuration
├── .env                # Environment variables (create this)
└── static/
    ├── index.html      # Frontend HTML
    └── app.js          # Frontend JavaScript
```

---

## Installation Steps

### Step 1: Clone the Repository

```bash
git clone https://github.com/bxlabz/HDAP.git
cd HDAP
```

### Step 2: Create Environment Configuration

Create a `.env` file in the project directory:

```bash
# .env file
SECRET_KEY=your-secure-random-secret-key-here
ADMIN_PASSWORD=your-secure-admin-password
```

> **Security Warning:** Use strong, unique values. Never commit `.env` to version control.

Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 3: Build and Start

```bash
# Build and start in detached mode
docker-compose up -d --build

# View logs (optional)
docker-compose logs -f
```

### Step 4: Verify Installation

```bash
docker-compose ps
```

You should see two services running: `route-optimizer` and `nginx`

### Step 5: Access the Application

Open your browser to: **http://localhost:8080**

Login with:
- **Username:** `admin`
- **Password:** (the password you set in .env)

---

## Usage Guide

### Preparing Your Data

Create a CSV file with an **Address** column:

```csv
Name,Address,Phone,Household,Special Items,Notes
Maria Santos,"211 N 1st St, Minneapolis, MN 55401",(612) 555-0101,4,Diapers (size 3),Gate code: 4521
James Johnson,"200 N 1st St, Minneapolis, MN 55401",(651) 555-0102,2,,Apartment 2B
```

### Creating Optimized Routes

1. **Set Start Address** - Enter depot/starting location
2. **Configure Settings:**
   - Maximum stops per route (3-10)
   - Search radius in miles (5-200)
3. **Upload CSV** - Select your address file
4. **Optimize** - Click "Optimize Routes"
5. **Export** - Download GPX files for each route

### Using GPX Files

Import into:
- **OsmAnd** - Open source navigation (recommended)
- **Google Maps** - Import as custom map
- **Garmin devices** - Direct GPX import

---

## Management Commands

| Action | Command |
|--------|---------|
| Start services | `docker-compose up -d` |
| Stop services | `docker-compose down` |
| View logs | `docker-compose logs -f` |
| Rebuild | `docker-compose up -d --build` |
| Check status | `docker-compose ps` |
| Restart | `docker-compose restart` |

---

## Troubleshooting

### Port 8080 Already in Use

Edit `docker-compose.yml` and change the port:
```yaml
ports:
  - "8888:80"  # Change 8080 to another port
```

### Geocoding Failures

- Ensure addresses include city, state, and ZIP code
- Check addresses are within the specified radius
- Large files take time (Nominatim rate limit: 1 req/sec)

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs route-optimizer

# Verify .env file exists
cat .env
```

### Login Issues

- Username is `admin`
- Password is set in `.env` as `ADMIN_PASSWORD`
- Clear browser cookies if having session issues

---

## Technical Specifications

| Component | Technology |
|-----------|------------|
| Backend | Flask 3.0 (Python 3.11) |
| Authentication | Flask-Login with password hashing |
| Geocoding | OpenStreetMap Nominatim |
| Route Optimization | Nearest Neighbor TSP |
| Distance Calculation | Geodesic (Vincenty) × 1.35 |
| Web Server | Nginx (reverse proxy) |
| Container | Docker with Python 3.11-slim |
| Frontend | HTML5, JavaScript, TailwindCSS |
