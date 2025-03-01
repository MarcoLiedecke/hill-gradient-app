# Denmark Hill Gradient Analyzer

A web application for visualizing and analyzing hill gradients in Denmark using elevation data and road network information.

## Features

- Interactive map visualization of hills and gradients
- Filtering of hills based on gradient, length, and category
- Detailed hill information including elevation profiles
- Advanced terrain visualization with 3D and heatmap options
- Top hills listing with sorting by different criteria

## Prerequisites

- Python 3.8+
- Flask
- NumPy, Pandas, Geopandas
- Rasterio for handling elevation data
- Shapely for geometric operations
- SQLite for the database

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/denmark-hill-gradient-analyzer.git
cd denmark-hill-gradient-analyzer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables (optional):
```bash
export FLASK_ENV=development
export MAPBOX_TOKEN=your_mapbox_token_here
```

## Data Requirements

This project requires elevation and road data that is not included in the repository due to size constraints. You need to:

1. Obtain Denmark's Digital Height Model (DHM/Terræn) data
2. Get road network data from OpenStreetMap for Denmark
3. Place these files in a `data` directory:
   - DTM_*.tif files for elevation data
   - denmark_roads.geojson for road network

## Processing Data

Run the data processing script to prepare the data:
```bash
python seed_db.py --all --data-dir=data --roads-file=data/denmark_roads.geojson
```

## Running the Application

Start the Flask development server:
```bash
python app.py
```

Access the application at http://localhost:5000

## Project Structure

- `app.py`: Main Flask application
- `config.py`: Configuration settings
- `seed_db.py`: Data processing script
- `backend/`: Backend modules
  - `services/`: Core services for processing data
  - `routes/`: API routes
  - `utils/`: Utility functions
- `templates/`: HTML templates
- `static/`: Static assets (CSS, JS, images)
- `data/`: Data directory (not included in repository)

## License

MIT

## Acknowledgments

- OpenStreetMap for road data
- Danish Agency for Data Supply and Infrastructure for elevation data