from flask import Blueprint, jsonify, request, current_app
import os
import json
import geopandas as gpd
from shapely.geometry import shape, box
import logging

# Import our services
from backend.services.hill_database import HillDatabase
from backend.services.dhm_processor import DHMProcessor
from backend.services.road_processor import RoadProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
hill_routes = Blueprint('hill_routes', __name__)

# Initialize the database
hill_db = HillDatabase('hills.db')

@hill_routes.route('/api/hills', methods=['GET'])
def get_hills():
    """Get hills based on filter criteria."""
    # Parse filter parameters
    try:
        min_gradient = request.args.get('min_gradient', type=float)
        max_gradient = request.args.get('max_gradient', type=float)
        min_length = request.args.get('min_length', type=float)
        max_length = request.args.get('max_length', type=float)
        category = request.args.get('category')
        region = request.args.get('region')
        
        # Parse bounding box if provided
        bbox_str = request.args.get('bbox')
        bbox = None
        if bbox_str:
            try:
                bbox = [float(x) for x in bbox_str.split(',')]
                if len(bbox) != 4:
                    bbox = None
            except:
                pass
        
        # Search hills with filters
        hills_gdf = hill_db.search_hills(
            min_gradient=min_gradient,
            max_gradient=max_gradient,
            min_length=min_length,
            max_length=max_length,
            category=category,
            region=region,
            bbox=bbox
        )
        
        # Convert to GeoJSON
        if not hills_gdf.empty:
            # Keep only essential properties for the list view
            properties_to_keep = [
                'id', 'name', 'category', 'length_m', 
                'avg_gradient', 'max_gradient', 'elevation_gain'
            ]
            
            if len(hills_gdf.columns) > len(properties_to_keep) + 1:  # +1 for geometry
                hills_gdf = hills_gdf[properties_to_keep + ['geometry']]
            
            # Convert to GeoJSON
            geo_json = json.loads(hills_gdf.to_json())
            
            # Return formatted GeoJSON
            return jsonify(geo_json)
        else:
            return jsonify({
                "type": "FeatureCollection",
                "features": []
            })
            
    except Exception as e:
        logger.error(f"Error getting hills: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@hill_routes.route('/api/hills/<int:hill_id>', methods=['GET'])
def get_hill_details(hill_id):
    """Get detailed information about a specific hill."""
    try:
        # Get hill details
        hill_details = hill_db.get_hill_details(hill_id)
        
        if hill_details:
            # Convert geometry to GeoJSON
            geom_json = json.loads(gpd.GeoSeries([hill_details['geometry']]).to_json())
            geometry = geom_json['features'][0]['geometry']
            
            # Create response
            response = {
                "id": hill_details['id'],
                "name": hill_details['name'],
                "category": hill_details['category'],
                "length_m": hill_details['length_m'],
                "avg_gradient": hill_details['avg_gradient'],
                "max_gradient": hill_details['max_gradient'],
                "elevation_gain": hill_details['elevation_gain'],
                "start_elevation": hill_details['start_elevation'],
                "end_elevation": hill_details['end_elevation'],
                "region": hill_details['region'],
                "geometry": geometry,
                "elevation_profile": hill_details['elevation_profile'],
                "status": "success"
            }
            
            return jsonify(response)
        else:
            return jsonify({"error": "Hill not found", "status": "error"}), 404
            
    except Exception as e:
        logger.error(f"Error getting hill details: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@hill_routes.route('/api/hills/stats', methods=['GET'])
def get_hill_statistics():
    """Get statistics about the hills in the database."""
    try:
        stats = hill_db.get_statistics()
        return jsonify({"data": stats, "status": "success"})
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@hill_routes.route('/api/process', methods=['POST'])
def process_data():
    """Admin endpoint to process data and refresh the database."""
    try:
        # Check for authorization (you might want to add authentication)
        if current_app.config.get('ENV') == 'production':
            api_key = request.headers.get('X-API-Key')
            if not api_key or api_key != current_app.config.get('ADMIN_API_KEY'):
                return jsonify({"error": "Unauthorized", "status": "error"}), 401
        
        # Initialize processors
        data_dir = current_app.config.get('DATA_DIR', 'data')
        roads_file = current_app.config.get('ROADS_FILE', os.path.join(data_dir, 'denmark_roads.geojson'))
        
        dhm_processor = DHMProcessor(data_dir)
        road_processor = RoadProcessor(roads_file, dhm_processor)
        
        # Process steps
        steps = request.json.get('steps', ['all'])
        
        results = {}
        
        # Process DHM data
        if 'dhm' in steps or 'all' in steps:
            try:
                merged_path = dhm_processor.merge_dhm_files()
                results['dhm_processing'] = "Success" if os.path.exists(merged_path) else "Failed"
            except Exception as e:
                results['dhm_processing'] = f"Error: {str(e)}"
        
        # Process road data
        if 'roads' in steps or 'all' in steps:
            try:
                # Load roads
                roads_gdf = road_processor.load_roads()
                
                # Calculate gradients
                road_processor.calculate_road_gradients(
                    sample_distance=current_app.config.get('SAMPLE_DISTANCE', 10)
                )
                
                # Save processed roads
                processed_path = os.path.join(data_dir, 'processed_roads.geojson')
                saved = road_processor.save_processed_roads(processed_path)
                results['road_processing'] = "Success" if saved else "Failed"
            except Exception as e:
                results['road_processing'] = f"Error: {str(e)}"
        
        # Identify hills
        if 'hills' in steps or 'all' in steps:
            try:
                # Identify hills
                hills_path = os.path.join(data_dir, 'denmark_hills.geojson')
                hills_saved = road_processor.save_hills(hills_path)
                results['hill_identification'] = "Success" if hills_saved else "Failed"
            except Exception as e:
                results['hill_identification'] = f"Error: {str(e)}"
        
        # Import hills to database
        if 'database' in steps or 'all' in steps:
            try:
                # Import hills to database
                hills_path = os.path.join(data_dir, 'denmark_hills.geojson')
                if os.path.exists(hills_path):
                    imported = hill_db.import_hills_from_geojson(hills_path)
                    results['database_import'] = "Success" if imported else "Failed"
                else:
                    results['database_import'] = "Failed: Hills file not found"
            except Exception as e:
                results['database_import'] = f"Error: {str(e)}"
        
        return jsonify({"status": "success", "results": results})
    
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@hill_routes.route('/api/elevation', methods=['GET'])
def get_elevation():
    """Get elevation for a specific coordinate."""
    try:
        # Parse coordinates
        lon = request.args.get('lon', type=float)
        lat = request.args.get('lat', type=float)
        
        if lon is None or lat is None:
            return jsonify({"error": "Missing coordinates", "status": "error"}), 400
            
        # Initialize DHM processor
        data_dir = current_app.config.get('DATA_DIR', 'data')
        dhm_processor = DHMProcessor(data_dir)
        
        # Get elevation
        elevation = dhm_processor.get_elevation(lon, lat)
        
        # Close dataset
        dhm_processor.close()
        
        if elevation is not None:
            return jsonify({"elevation": float(elevation), "status": "success"})
        else:
            return jsonify({"error": "Could not determine elevation", "status": "error"}), 404
            
    except Exception as e:
        logger.error(f"Error getting elevation: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500