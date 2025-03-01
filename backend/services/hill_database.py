# backend/services/hill_database.py
import os
import json
import sqlite3
import numpy as np
import geopandas as gpd
import pandas as pd
import logging
from shapely.geometry import shape, LineString, Point
from shapely import wkt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HillDatabase:
    """Database manager for hill gradient data."""
    
    def __init__(self, db_path='hills.db'):
        """Initialize with database path."""
        self.db_path = db_path
        
    def init_db(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create hills table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            road_id TEXT,
            category TEXT,
            length_m REAL,
            avg_gradient REAL,
            max_gradient REAL,
            elevation_gain REAL,
            start_elevation REAL,
            end_elevation REAL,
            geometry TEXT,
            source TEXT,
            bbox TEXT,
            region TEXT
        )
        ''')
        
        # Create elevation_profiles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS elevation_profiles (
            hill_id INTEGER,
            distance REAL,
            elevation REAL,
            FOREIGN KEY (hill_id) REFERENCES hills(id)
        )
        ''')
        
        # Create spatial index for faster geographic queries
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='idx_hills_bbox'")
        if not cursor.fetchone():
            try:
                cursor.execute("CREATE VIRTUAL TABLE idx_hills_bbox USING rtree(id, min_x, max_x, min_y, max_y)")
            except Exception as e:
                logger.warning(f"Could not create spatial index: {e}")
                
        conn.commit()
        conn.close()
        logger.info("Database initialized")
        
    def import_hills_from_geojson(self, geojson_path):
        """Import hill data from a GeoJSON file."""
        if not os.path.exists(geojson_path):
            logger.error(f"GeoJSON file not found: {geojson_path}")
            return False
            
        # Read GeoJSON
        logger.info(f"Importing hills from {geojson_path}")
        hills_gdf = gpd.read_file(geojson_path)
        
        # Initialize database
        self.init_db()
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing data if needed
        cursor.execute("DELETE FROM hills")
        cursor.execute("DELETE FROM elevation_profiles")
        if cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='idx_hills_bbox'").fetchone():
            cursor.execute("DELETE FROM idx_hills_bbox")
        
        # Process each hill
        for idx, row in hills_gdf.iterrows():
            geom_wkt = row.geometry.wkt
            
            # Extract bounding box for spatial indexing
            minx, miny, maxx, maxy = row.geometry.bounds
            bbox = json.dumps([minx, miny, maxx, maxy])
            
            # Extract name or generate a default
            name = row.get('name', f"Hill {idx+1}")
            
            # Extract or calculate other attributes
            road_id = row.get('road_id', str(idx))
            category = row.get('category', 'Unknown')
            length_m = row.get('length_m', 0.0)
            avg_gradient = row.get('avg_gradient', 0.0)
            max_gradient = row.get('max_gradient', 0.0)
            elevation_gain = row.get('elevation_gain', 0.0)
            
            # Extract start and end elevations from profile if available
            start_elev = end_elev = None
            if 'elevation_profile' in row and row.elevation_profile:
                # Handle string representation of elevation profile
                if isinstance(row.elevation_profile, str):
                    try:
                        # Try to convert string representation to actual data
                        profile_data = eval(row.elevation_profile)
                        if profile_data and isinstance(profile_data, list) and len(profile_data) > 0:
                            start_elev = profile_data[0][1]
                            end_elev = profile_data[-1][1]
                    except:
                        pass
                elif isinstance(row.elevation_profile, list) and len(row.elevation_profile) > 0:
                    start_elev = row.elevation_profile[0][1]
                    end_elev = row.elevation_profile[-1][1]
            
            # Default values if we couldn't extract
            start_elev = start_elev if start_elev is not None else 0.0
            end_elev = end_elev if end_elev is not None else 0.0
            
            # Determine region from coordinates
            # (You might want to use a more sophisticated method based on Danish regions)
            region = "Unknown"
            
            # Insert main hill data
            cursor.execute('''
            INSERT INTO hills (
                name, road_id, category, length_m, avg_gradient, max_gradient,
                elevation_gain, start_elevation, end_elevation, geometry,
                source, bbox, region
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name, road_id, category, length_m, avg_gradient, max_gradient,
                elevation_gain, start_elev, end_elev, geom_wkt,
                geojson_path, bbox, region
            ))
            
            # Get the hill ID for elevation profile data
            hill_id = cursor.lastrowid
            
            # Insert into spatial index
            cursor.execute('''
            INSERT INTO idx_hills_bbox (id, min_x, max_x, min_y, max_y)
            VALUES (?, ?, ?, ?, ?)
            ''', (hill_id, minx, maxx, miny, maxy))
            
            # Insert elevation profile if available
            if 'elevation_profile' in row and row.elevation_profile:
                try:
                    profile_data = row.elevation_profile
                    if isinstance(profile_data, str):
                        profile_data = eval(profile_data)
                        
                    if profile_data and isinstance(profile_data, list):
                        for distance, elevation in profile_data:
                            cursor.execute('''
                            INSERT INTO elevation_profiles (hill_id, distance, elevation)
                            VALUES (?, ?, ?)
                            ''', (hill_id, distance, elevation))
                except Exception as e:
                    logger.warning(f"Could not process elevation profile for hill {hill_id}: {e}")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        logger.info(f"Imported {len(hills_gdf)} hills into database")
        return True
    
    def get_all_hills(self):
        """Get all hills from the database."""
        conn = sqlite3.connect(self.db_path)
        
        # Convert database rows to DataFrame
        hills_df = pd.read_sql_query("SELECT * FROM hills", conn)
        
        # Create a GeoDataFrame with WKT geometries
        if not hills_df.empty:
            hills_df['geometry'] = hills_df['geometry'].apply(wkt.loads)
            hills_gdf = gpd.GeoDataFrame(hills_df, geometry='geometry')
        else:
            hills_gdf = gpd.GeoDataFrame()
            
        conn.close()
        return hills_gdf
    
    def search_hills(self, 
                     min_gradient=None, 
                     max_gradient=None,
                     min_length=None, 
                     max_length=None,
                     category=None,
                     region=None,
                     bbox=None):
        """
        Search for hills based on criteria.
        
        Args:
            min_gradient: Minimum average gradient (%)
            max_gradient: Maximum average gradient (%)
            min_length: Minimum length (m)
            max_length: Maximum length (m)
            category: Hill category
            region: Region name
            bbox: Bounding box [minx, miny, maxx, maxy]
            
        Returns:
            GeoDataFrame with matching hills
        """
        conn = sqlite3.connect(self.db_path)
        
        # Build query
        query = "SELECT * FROM hills WHERE 1=1"
        params = []
        
        if min_gradient is not None:
            query += " AND avg_gradient >= ?"
            params.append(min_gradient)
            
        if max_gradient is not None:
            query += " AND avg_gradient <= ?"
            params.append(max_gradient)
            
        if min_length is not None:
            query += " AND length_m >= ?"
            params.append(min_length)
            
        if max_length is not None:
            query += " AND length_m <= ?"
            params.append(max_length)
            
        if category is not None:
            query += " AND category = ?"
            params.append(category)
            
        if region is not None:
            query += " AND region = ?"
            params.append(region)
            
        # Use spatial index if bbox is provided
        if bbox is not None:
            minx, miny, maxx, maxy = bbox
            
            # Use the spatial index for initial filtering
            spatial_query = """
            SELECT h.* FROM hills h
            JOIN idx_hills_bbox i ON h.id = i.id
            WHERE i.min_x <= ? AND i.max_x >= ?
            AND i.min_y <= ? AND i.max_y >= ?
            """
            
            if params:
                # Combine with other filters
                query = spatial_query + " AND " + query.split("WHERE 1=1 AND ")[1]
                params = [maxx, minx, maxy, miny] + params
            else:
                query = spatial_query
                params = [maxx, minx, maxy, miny]
        
        # Get results
        hills_df = pd.read_sql_query(query, conn, params=params)
        
        # Create a GeoDataFrame with WKT geometries
        if not hills_df.empty:
            hills_df['geometry'] = hills_df['geometry'].apply(wkt.loads)
            hills_gdf = gpd.GeoDataFrame(hills_df, geometry='geometry')
        else:
            hills_gdf = gpd.GeoDataFrame()
            
        conn.close()
        return hills_gdf
    
    def get_hill_elevation_profile(self, hill_id):
        """Get the elevation profile for a specific hill."""
        conn = sqlite3.connect(self.db_path)
        
        # Query elevation profile
        query = """
        SELECT distance, elevation 
        FROM elevation_profiles 
        WHERE hill_id = ? 
        ORDER BY distance
        """
        
        profile_df = pd.read_sql_query(query, conn, params=[hill_id])
        conn.close()
        
        if profile_df.empty:
            return None
            
        # Convert to list of tuples [(distance, elevation), ...]
        profile = list(zip(profile_df['distance'], profile_df['elevation']))
        return profile
    
    def get_hill_details(self, hill_id):
        """Get detailed information about a specific hill."""
        conn = sqlite3.connect(self.db_path)
        
        # Query hill details
        query = "SELECT * FROM hills WHERE id = ?"
        hill_df = pd.read_sql_query(query, conn, params=[hill_id])
        
        if hill_df.empty:
            conn.close()
            return None
            
        # Get elevation profile
        profile = self.get_hill_elevation_profile(hill_id)
        
        # Create hill details dictionary
        hill_row = hill_df.iloc[0]
        
        # Convert WKT geometry to Shapely object
        geometry = wkt.loads(hill_row['geometry'])
        
        hill_details = {
            'id': int(hill_row['id']),
            'name': hill_row['name'],
            'category': hill_row['category'],
            'length_m': float(hill_row['length_m']),
            'avg_gradient': float(hill_row['avg_gradient']),
            'max_gradient': float(hill_row['max_gradient']),
            'elevation_gain': float(hill_row['elevation_gain']),
            'start_elevation': float(hill_row['start_elevation']),
            'end_elevation': float(hill_row['end_elevation']),
            'region': hill_row['region'],
            'geometry': geometry,
            'elevation_profile': profile
        }
        
        conn.close()
        return hill_details
    
    def get_statistics(self):
        """Get statistical information about the hills in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Count total hills
        cursor.execute("SELECT COUNT(*) FROM hills")
        stats['total_hills'] = cursor.fetchone()[0]
        
        # Get category distribution
        cursor.execute("SELECT category, COUNT(*) FROM hills GROUP BY category")
        stats['categories'] = {category: count for category, count in cursor.fetchall()}
        
        # Get gradient statistics
        cursor.execute("SELECT AVG(avg_gradient), MAX(avg_gradient), MIN(avg_gradient) FROM hills")
        avg, max_grad, min_grad = cursor.fetchone()
        stats['gradient'] = {
            'average': avg,
            'max': max_grad,
            'min': min_grad
        }
        
        # Get length statistics
        cursor.execute("SELECT AVG(length_m), MAX(length_m), MIN(length_m) FROM hills")
        avg, max_len, min_len = cursor.fetchone()
        stats['length'] = {
            'average': avg,
            'max': max_len,
            'min': min_len
        }
        
        # Get region distribution
        cursor.execute("SELECT region, COUNT(*) FROM hills GROUP BY region")
        stats['regions'] = {region: count for region, count in cursor.fetchall()}
        
        conn.close()
        return stats