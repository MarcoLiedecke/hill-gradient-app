from flask import Flask, request, jsonify
from typing import Dict, List, Optional
from dataclasses import dataclass
import rasterio
from rasterio.merge import merge
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
import glob
import os
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Data models
@dataclass
class RoadMetadata:
    id: int
    name: Optional[str]
    highway: str
    maxspeed: Optional[str]
    surface: Optional[str]
    length_meters: float
    gradient: float
    min_elevation: float
    max_elevation: float

# Configuration
CONFIG = {
    'DHM_FOLDERS': [
        'T:/hill_hunt/hill_gradient_app/data/DTM_616_53_TIF_UTM32-ETRS89',
        'T:/hill_hunt/hill_gradient_app/data/DTM_617_52_TIF_UTM32-ETRS89',
        'T:/hill_hunt/hill_gradient_app/data/DTM_617_53_TIF_UTM32-ETRS89',
        'T:/hill_hunt/hill_gradient_app/data/DTM_616_52_TIF_UTM32-ETRS89',
        'T:/hill_hunt/hill_gradient_app/data/DTM_617_54_TIF_UTM32-ETRS89',
    ],
    'ROADS_FILE': 'T:/hill_hunt/hill_gradient_app/data/denmark_roads.geojson',
    'OUTPUT_FILE': 'T:/hill_hunt/hill_gradient_app/data/vejle_roads_elevation.geojson',
    'MERGED_DHM': 'merged_dhm.tif'
}

def get_elevation(dem, x, y):
    """Get elevation for a point, handling no-data values"""
    try:
        val = next(dem.sample([(x, y)]))[0]
        if val == -9999.0:
            return None
        return val
    except:
        return None

def create_gradient_profile(geometry, dem, sample_distance=50):
    """Create gradient profile data for visualization"""
    profile_data = []
    cumulative_distance = 0
    
    if geometry.geom_type == 'MultiLineString':
        segments = list(geometry.geoms)
    else:
        segments = [geometry]
        
    for segment in segments:
        length = segment.length
        num_points = int(length / sample_distance) + 1
        distances = np.linspace(0, 1, num=num_points)
        
        for i in range(len(distances)-1):
            point1 = segment.interpolate(distances[i])
            point2 = segment.interpolate(distances[i+1])
            
            elev1 = get_elevation(dem, point1.x, point1.y)
            elev2 = get_elevation(dem, point2.x, point2.y)
            
            if elev1 is not None and elev2 is not None:
                dist = point1.distance(point2)
                gradient = abs(elev2 - elev1) / dist * 100
                
                profile_data.append({
                    'distance': round(cumulative_distance),
                    'elevation': round(elev1, 1),
                    'gradient': round(gradient, 1)
                })
                cumulative_distance += dist
    
    return profile_data

def calculate_road_gradients(roads_file, dem_file):
    """Calculate gradients for all roads"""
    roads = gpd.read_file(roads_file)
    if roads.crs != 'EPSG:25832':
        roads = roads.to_crs('EPSG:25832')
        
    dem = rasterio.open(dem_file)
    if dem.crs != roads.crs:
        raise ValueError(f"CRS mismatch: DEM is {dem.crs}, roads are {roads.crs}")
        
    def process_single_line(line):
        length = line.length
        num_points = max(int(length), 2)
        distances = np.linspace(0, 1, num=num_points)
        points = [line.interpolate(d) for d in distances]
        
        # Get valid elevations
        elevations = []
        valid_points = []
        for i, p in enumerate(points):
            elev = get_elevation(dem, p.x, p.y)
            if elev is not None:
                elevations.append(elev)
                valid_points.append(points[i])
        
        if len(elevations) < 2:
            return 0, 0, 0
        
        # Debug information
        print(f"Line length: {length:.1f}m")
        print(f"Number of sampled points: {num_points}")
        print(f"Valid elevations found: {len(elevations)}")
        print(f"Elevation range: {min(elevations):.1f}m - {max(elevations):.1f}m")
                
        # Calculate distances between valid points
        point_distances = [valid_points[i+1].distance(valid_points[i])
                          for i in range(len(valid_points)-1)]
        elevation_changes = [abs(elevations[i+1] - elevations[i]) 
                            for i in range(len(elevations)-1)]
        
        gradients = [(change/dist)*100 for change, dist in zip(elevation_changes, point_distances)]
        avg_gradient = np.mean(gradients) if gradients else 0
        
        # Debug gradient information
        print(f"Average gradient: {avg_gradient:.1f}%")
        print("---")
        
        return avg_gradient, min(elevations), max(elevations)
        pass
    
    def get_segment_gradient(geometry):
        if geometry.geom_type == 'MultiLineString':
            gradients = []
            min_elevs = []
            max_elevs = []
            
            for line in geometry.geoms:
                grad, min_elev, max_elev = process_single_line(line)
                gradients.append(grad)
                min_elevs.append(min_elev)
                max_elevs.append(max_elev)
                
            return np.mean(gradients), min(min_elevs), max(max_elevs)
        else:
            return process_single_line(geometry)
        pass
    
    roads['gradient'] = roads['geometry'].apply(lambda x: get_segment_gradient(x)[0])
    roads['min_elevation'] = roads['geometry'].apply(lambda x: get_segment_gradient(x)[1])
    roads['max_elevation'] = roads['geometry'].apply(lambda x: get_segment_gradient(x)[2])
    
    return roads

@app.route('/api/process-roads', methods=['POST'])
def process_roads():
    try:
        # Process DHM data and calculate gradients
        tif_files = []
        for folder in CONFIG['DHM_FOLDERS']:
            tif_files.extend(glob.glob(os.path.join(folder, '*.tif')))
        
        src_files = [rasterio.open(f) for f in tif_files]
        try:
            mosaic, out_trans = merge(src_files)
        finally:
            for src in src_files:
                src.close()
        
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans
        })
        
        # Save merged DEM
        with rasterio.open(CONFIG['MERGED_DHM'], "w", **out_meta) as dest:
            dest.write(mosaic)
        
        # Calculate gradients
        roads_with_gradients = calculate_road_gradients(
            CONFIG['ROADS_FILE'], 
            CONFIG['MERGED_DHM']
        )
        
        # Save results
        roads_with_gradients.to_file(CONFIG['OUTPUT_FILE'])
        
        return jsonify({
            'status': 'success',
            'message': 'Road gradients processed successfully'
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/gradient-profile/<road_id>', methods=['GET'])
def get_gradient_profile(road_id):
    try:
        # Read the roads data
        roads = gpd.read_file(CONFIG['OUTPUT_FILE'])
        road = roads.iloc[int(road_id)]
        
        # Create profile
        with rasterio.open(CONFIG['MERGED_DHM']) as dem:
            profile_data = create_gradient_profile(road.geometry, dem)
        
        return jsonify({
            'status': 'success',
            'data': {
                'name': road['name'] if 'name' in road else f'Road {road_id}',
                'length': float(road['length']) if 'length' in road else 0,
                'averageGradient': float(road['gradient']),
                'profile': profile_data
            }
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/roads', methods=['GET'])
def get_roads():
    try:
        # Query parameters
        highway_type = request.args.get('highway_type')
        min_gradient = float(request.args.get('min_gradient', 0))
        max_gradient = float(request.args.get('max_gradient', 100))
        
        # Read processed roads
        roads = gpd.read_file(CONFIG['OUTPUT_FILE'])
        
        # Filter by criteria
        if highway_type:
            roads = roads[roads['highway'] == highway_type]
        
        roads = roads[
            (roads['gradient'] >= min_gradient) & 
            (roads['gradient'] <= max_gradient)
        ]
        
        # Convert to list of road metadata
        roads_list = []
        for _, road in roads.iterrows():
            roads_list.append({
                'id': int(road.get('id', 0)),
                'name': road.get('name'),
                'highway': road.get('highway'),
                'maxspeed': road.get('maxspeed'),
                'surface': road.get('surface'),
                'length_meters': float(road.get('length_meters', 0)),
                'gradient': float(road['gradient']),
                'min_elevation': float(road['min_elevation']),
                'max_elevation': float(road['max_elevation'])
            })
        
        return jsonify({
            'status': 'success',
            'data': roads_list
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/roads/stats', methods=['GET'])
def get_road_stats():
    try:
        roads = gpd.read_file(CONFIG['OUTPUT_FILE'])
        
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

@app.route('/api/roads/<int:road_id>', methods=['GET'])
def get_road_details(road_id):
    try:
        roads = gpd.read_file(CONFIG['OUTPUT_FILE'])
        road = roads[roads['id'] == road_id].iloc[0]
        
        details = {
            'id': int(road.get('id', 0)),
            'name': road.get('name'),
            'highway': road.get('highway'),
            'maxspeed': road.get('maxspeed'),
            'surface': road.get('surface'),
            'length_meters': float(road.get('length_meters', 0)),
            'gradient': float(road['gradient']),
            'min_elevation': float(road['min_elevation']),
            'max_elevation': float(road['max_elevation']),
            'additional_properties': {
                'lanes': road.get('lanes'),
                'lit': road.get('lit'),
                'junction': road.get('junction'),
                'cycleway': road.get('cycleway'),
                'sidewalk': road.get('sidewalk')
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': details
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)