import rasterio
import numpy as np
from shapely.geometry import Point, LineString

def get_elevation(dem, x, y):
    """Get elevation for a point, handling no-data values"""
    try:
        val = next(dem.sample([(x, y)]))[0]
        if val == -9999.0:
            return None
        return val
    except:
        return None

def calculate_segment_gradient(line_geometry, dem):
    """Calculate gradient for a line segment"""
    length = line_geometry.length
    num_points = max(int(length / 10), 2)  # Sample every 10 meters or at least 2 points
    
    points = [line_geometry.interpolate(i/num_points, normalized=True) 
             for i in range(num_points + 1)]
    
    elevations = []
    valid_points = []