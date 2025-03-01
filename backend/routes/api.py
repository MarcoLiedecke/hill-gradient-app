from flask import Blueprint, jsonify, request
import geopandas as gpd
import rasterio
from ..utils.geo_utils import get_elevation, calculate_segment_gradient
from ..config import Config

api_bp = Blueprint('api', __name__)

@api_bp.route('/roads', methods=['GET'])
def get_roads():
    try:
        # Get filter parameters
        highway_type = request.args.get('highway_type')
        min_gradient = float(request.args.get('min_gradient', 0))
        max_gradient = float(request.args.get('max_gradient', 100))
        
        # Read roads data
        roads = gpd.read_file(Config.OUTPUT_FILE)
        
        # Apply filters
        if highway_type:
            roads = roads[roads['highway'] == highway_type]
        
        roads = roads[
            (roads['gradient'] >= min_gradient) & 
            (roads['gradient'] <= max_gradient)
        ]
        
        # Convert to GeoJSON format
        roads_data = []
        for _, road in roads.iterrows():
            roads_data.append({
                'id': int(road.get('id', 0)),
                'name': road.get('name'),
                'highway': road.get('highway'),
                'maxspeed': road.get('maxspeed'),
                'surface': road.get('surface'),
                'length_meters': float(road.get('length_meters', 0)),
                'gradient': float(road['gradient']),
                'min_elevation': float(road['min_elevation']),
                'max_elevation': float(road['max_elevation']),
                'geometry': road['geometry'].__geo_interface__
            })
        
        return jsonify({
            'status': 'success',
            'data': roads_data
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/roads/<int:road_id>/profile', methods=['GET'])
def get_road_profile(road_id):
    try:
        # Read road data
        roads = gpd.read_file(Config.OUTPUT_FILE)
        road = roads[roads['id'] == road_id].iloc[0]
        
        # Open DEM for elevation data
        with rasterio.open(Config.MERGED_DHM) as dem:
            # Calculate elevation profile
            profile_data = []
            geometry = road['geometry']
            length = geometry.length
            num_points = int(length / Config.SAMPLE_DISTANCE) + 1
            
            for i in range(num_points):
                distance = (i * Config.SAMPLE_DISTANCE)
                point = geometry.interpolate(distance)
                elevation = get_elevation(dem, point.x, point.y)
                
                if elevation is not None:
                    profile_data.append({
                        'distance': round(distance),
                        'elevation': round(elevation, 1)
                    })
        
        return jsonify({
            'status': 'success',
            'data': {
                'name': road.get('name', f'Road {road_id}'),
                'length': float(road['length_meters']),
                'average_gradient': float(road['gradient']),
                'profile': profile_data
            }
        })
    
    except IndexError:
        return jsonify({
            'status': 'error',
            'message': f'Road with id {road_id} not found'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/roads/stats', methods=['GET'])
def get_road_stats():
    try:
        roads = gpd.read_file(Config.OUTPUT_FILE)
        
        stats = {
            'total_roads': len(roads),
            'highway_types': roads['highway'].value_counts().to_dict(),
            'total_length_km': round(roads['length_meters'].sum() / 1000, 2),
            'gradient_stats': {
                'mean': float(roads['gradient'].mean()),
                'max': float(roads['gradient'].max()),
                'min': float(roads['gradient'].min())
            },
            'elevation_range': {
                'min': float(roads['min_elevation'].min()),
                'max': float(roads['max_elevation'].max())
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': stats
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500