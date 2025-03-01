from flask import Blueprint, render_template
from ..config import Config

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Initialize empty stats - they will be loaded via HTMX
    initial_stats = {
        'total_roads': 0,
        'total_length_km': 0,
        'highway_types': {},
        'gradient_stats': {
            'mean': 0,
            'max': 0,
            'min': 0
        }
    }
    return render_template('index.html', stats=initial_stats)

@main_bp.route('/map')
def map_view():
    return render_template('map.html', 
                         center_lat=Config.DEFAULT_LAT,
                         center_lon=Config.DEFAULT_LON,
                         zoom=Config.DEFAULT_ZOOM)

@main_bp.route('/statistics')
def statistics():
    return render_template('statistics.html')