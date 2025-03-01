import os

# Flask settings
DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'
SECRET_KEY = os.environ.get('SECRET_KEY', 'denmark-hill-analyzer-dev-key')
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///hills.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Environment settings
ENV = os.environ.get('FLASK_ENV', 'development')

# API settings
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'development-admin-key')

# Mapbox settings
MAPBOX_TOKEN = os.environ.get('pk.eyJ1IjoibGllZGVja2U5NSIsImEiOiJjbGNxZ3E1YnEwNXV3M3BsaHdqaG0yOG5vIn0.nphFmNshYXzqJDdb_SoGnw', '')

# Database settings
DB_PATH = os.environ.get('DB_PATH', 'hills.db')

# Data directories
DATA_DIR = os.environ.get('DATA_DIR', 'data')
DHM_DIR = os.path.join(DATA_DIR, 'dhm')
ROADS_FILE = os.path.join(DATA_DIR, 'denmark_roads.geojson')
HILLS_FILE = os.path.join(DATA_DIR, 'denmark_hills.geojson')
MERGED_DHM = os.path.join(DATA_DIR, 'merged_dhm.tif')
OUTPUT_FILE = os.path.join(DATA_DIR, 'processed_roads.geojson')

# Processing settings
SAMPLE_DISTANCE = 10  # meters between elevation samples
HILL_MIN_LENGTH = 100  # minimum hill length in meters
HILL_MIN_GRADIENT = 3.0  # minimum average gradient percentage
HILL_MIN_ELEVATION_GAIN = 10  # minimum elevation gain in meters