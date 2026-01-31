# HDAP - Humanitarian Aid Delivery Router

A web-based route optimization tool for humanitarian aid delivery operations. Upload addresses, generate optimized multi-stop routes, and export GPX files for navigation.

## Features

- **CSV/TSV Import** - Upload address lists with beneficiary information
- **Geocoding** - Automatic address-to-coordinate conversion via OpenStreetMap
- **Route Optimization** - Nearest neighbor TSP algorithm with proximity clustering
- **Multi-Route Support** - Configurable max stops per route (3-10)
- **Radius Filtering** - Exclude addresses outside service area
- **GPX Export** - Download routes for OsmAnd, Garmin, and other GPS apps
- **Secure Access** - Password-protected admin interface

## Quick Start

### Prerequisites
- Docker & Docker Compose

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/bxlabz/HDAP.git
   cd HDAP
   ```

2. Create a `.env` file with your credentials:
   ```
   SECRET_KEY=your-secure-random-key
   ADMIN_PASSWORD=your-admin-password
   ```

3. Build and run:
   ```bash
   docker-compose up -d
   ```

4. Open http://localhost:8080 and login with username `admin`

## Documentation

- [Installation Guide](INSTALLATION_GUIDE.md) - Detailed setup instructions
- [Technical Architecture](TECHNICAL_DIAGRAM.md) - System design and diagrams

> HTML versions with styled visuals available in [docs/html/](docs/html/)

## Tech Stack

- **Backend**: Python 3.11, Flask 3.0
- **Frontend**: HTML5, JavaScript, TailwindCSS
- **Geocoding**: OpenStreetMap Nominatim
- **Containerization**: Docker, Nginx

## License

MIT
