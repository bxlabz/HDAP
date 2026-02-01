# Installation Guide

## Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Git | 2.30+ | Clone repository |

> **Note:** Docker Desktop for Windows/Mac includes Docker Compose.

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/bxlabz/HDAP.git
cd HDAP
```

### 2. Start the Services

```bash
docker-compose up --build
```

### 3. Access the Applications

| Service | URL | Purpose |
|---------|-----|---------|
| Text Generator | http://localhost:8081 | Create packing slips |
| Route Generator | http://localhost:8080 | Create delivery routes |

---

## Running Without Docker

### Text Generator

```bash
cd textgen-container
pip install -r requirements.txt
python -m flask run --host=0.0.0.0 --port=8081
```

### Route Generator

```bash
cd routing-container
pip install -r requirements.txt
python -m flask run --host=0.0.0.0 --port=8080
```

---

## Usage Guide

### Text Generator (Port 8081)

Creates bilingual (English/Spanish) packing slips for delivery volunteers.

**Workflow:**
1. **Upload** - Select your CSV file with beneficiary data
2. **Review** - Check parsed data, fix any flagged issues
3. **Generate** - Create packing slips
4. **Download** - Get individual files or ZIP archive

**Output filename format:** `Route_{num}_{seq}_{initials}_{last4phone}.txt`

### Route Generator (Port 8080)

Creates optimized delivery routes with GPX files for navigation apps.

**Workflow:**
1. **Upload** - Select your CSV file with addresses
2. **Review** - Verify data, optionally set depot address
3. **Geocode** - Convert addresses to GPS coordinates
4. **Generate** - Create optimized routes (max 4 stops each)
5. **Download** - Get GPX files + manifest

---

## CSV Format

Both containers accept CSV files with these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Beneficiary's full name |
| `address` | Yes | Full delivery address |
| `phone` | Recommended | Contact phone number |
| `household_size` | No | Number of people |
| `items_needed` | No | Items to deliver |
| `special_items` | No | Diapers, formula, pet food |
| `contact_preference` | No | How to contact |
| `notes` | No | Additional notes |

**Sample file:** `shared/sample_data.csv`

---

## Management Commands

| Action | Command |
|--------|---------|
| Start services | `docker-compose up -d` |
| Start with rebuild | `docker-compose up --build` |
| Stop services | `docker-compose down` |
| View logs | `docker-compose logs -f` |
| View specific logs | `docker-compose logs -f routing-container` |
| Restart | `docker-compose restart` |

---

## Troubleshooting

### Port Already in Use

Edit `docker-compose.yml` to change ports:

```yaml
services:
  textgen:
    ports:
      - "9081:8081"  # Change 8081 to 9081
  routing:
    ports:
      - "9080:8080"  # Change 8080 to 9080
```

### Geocoding Slow or Failing

- Nominatim has a 1 request/second rate limit
- Large files take time - be patient
- Ensure addresses include city, state, ZIP
- Check internet connectivity

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs

# Rebuild from scratch
docker-compose down
docker-compose up --build
```

### Data Not Persisting

Session data is stored in memory. Restarting containers clears all data. For persistence, export your results before stopping.

---

## Output Files

### Packing Slip Example

```
================================================================
                    DELIVERY / ENTREGA
================================================================
ID: Route_1_01_MG_4567
================================================================

TELEFONO / PHONE: (555) 123-4567

----------------------------------------------------------------
HOGAR / HOUSEHOLD
----------------------------------------------------------------
Numero de personas / Number of people: 4

----------------------------------------------------------------
ARTICULOS NECESARIOS / ITEMS NEEDED
----------------------------------------------------------------
Rice Beans Cooking Oil Canned Vegetables

****************************************************************
*                 SPECIAL ITEMS / ARTICULOS ESPECIALES         *
****************************************************************
* Diapers (size 3)                                             *
****************************************************************
================================================================
```

### GPX File

OsmAnd-compatible GPX containing:
- Ordered waypoints for each stop
- Name, address, phone in descriptions
- Track connecting all points
- Depot as start/end (if specified)

---

## Project Structure

```
HDAP/
├── docker-compose.yml
├── README.md
├── routing-container/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── routes.py
│       ├── csv_parser.py
│       ├── geocoder.py
│       ├── optimizer.py
│       ├── gpx_generator.py
│       └── templates/
├── textgen-container/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── routes.py
│       ├── csv_parser.py
│       ├── phone_formatter.py
│       ├── text_generator.py
│       └── templates/
└── shared/
    └── sample_data.csv
```
