# Humanitarian Aid Delivery System

A two-container system for managing humanitarian aid deliveries:

1. **Text Generator** - Creates bilingual packing slips for delivery volunteers
2. **Route Generator** - Creates optimized delivery routes with GPX files for OsmAnd navigation

## Quick Start

### Using Docker Compose (Recommended)

```bash
git clone https://github.com/bxlabz/HDAP.git
cd HDAP
docker-compose up --build
```

Services will be available at:
- **Text Generator**: http://localhost:8081
- **Route Generator**: http://localhost:8080

### Running Individually

#### Text Generator Container
```bash
cd textgen-container
pip install -r requirements.txt
python -m flask run --host=0.0.0.0 --port=8081
```

#### Route Generator Container
```bash
cd routing-container
pip install -r requirements.txt
python -m flask run --host=0.0.0.0 --port=8080
```

## Usage

### Text Generator (Port 8081)

1. **Upload** your CSV file with beneficiary data
2. **Review** the parsed data - fix any flagged issues
3. **Generate** packing slips with bilingual format
4. **Download** individual files or all as ZIP

Output files are named: `Route_{num}_{seq}_{initials}_{last4}.txt`

### Route Generator (Port 8080)

1. **Upload** your CSV file with beneficiary addresses
2. **Review** data and optionally set a depot address
3. **Geocode** all addresses (converts to GPS coordinates)
4. **Generate** optimized routes (max 4 stops per route)
5. **Download** GPX files for OsmAnd + manifest

## CSV Format

Both containers accept CSV files with these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Beneficiary's full name |
| `address` | Yes | Full delivery address |
| `phone` | Recommended | Contact phone number |
| `household_size` | No | Number of people in household |
| `items_needed` | No | Items to deliver |
| `special_items` | No | Diapers, formula, pet food |
| `contact_preference` | No | How to contact |
| `notes` | No | Additional notes |

Sample data is provided in `shared/sample_data.csv`.

## Output Formats

### Packing Slip (Text Generator)

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

----------------------------------------------------------------
CONTACTO / CONTACT PREFERENCE
----------------------------------------------------------------
Call before delivery

================================================================
```

### GPX File (Route Generator)

OsmAnd-compatible GPX with:
- Ordered waypoints for each stop
- Name, address, phone in waypoint descriptions
- Track connecting all points
- Optional depot as start/end point

### Manifest

Text summary of all routes with:
- Route numbers and stop counts
- Distance and duration estimates (when available)
- Full stop details for each route

## Technical Details

### Route Optimization

1. **Geocoding**: Uses OpenStreetMap Nominatim (1 req/sec rate limit)
2. **Clustering**: K-means algorithm groups nearby addresses
3. **Optimization**: OSRM trip service for TSP solving
4. **Fallback**: Nearest-neighbor algorithm if OSRM unavailable

### Dependencies

**Text Generator:**
- Flask 3.0.0
- phonenumbers 8.13.0

**Route Generator:**
- Flask 3.0.0
- geopy 2.4.1 (Nominatim geocoding)
- scikit-learn 1.3.2 (clustering)
- gpxpy 1.6.1 (GPX generation)
- requests 2.31.0 (OSRM API)

## File Structure

```
delivery-system/
├── docker-compose.yml
├── README.md
├── routing-container/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── routes.py
│   │   ├── csv_parser.py
│   │   ├── geocoder.py
│   │   ├── optimizer.py
│   │   ├── gpx_generator.py
│   │   └── templates/
│   └── static/
├── textgen-container/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── routes.py
│   │   ├── csv_parser.py
│   │   ├── phone_formatter.py
│   │   ├── text_generator.py
│   │   └── templates/
│   └── static/
└── shared/
    └── sample_data.csv
```

## Notes

- Geocoding uses free Nominatim service - be respectful of rate limits
- OSRM uses public demo server - for production, deploy your own
- Session data is stored server-side - restart clears data
- For large datasets, consider adding database persistence

## License

For humanitarian use.
