import sqlite3
import pandas as pd
import geopandas as gpd
from shapely import wkt
import folium
from folium.features import GeoJsonPopup, GeoJsonTooltip
import branca.colormap as cm
import os
import webbrowser
import sys
import json

def load_hills_from_db(db_path='hills.db'):
    """Load hills data from the database into a GeoDataFrame with debug info."""
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return None
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    
    try:
        # First, let's examine the database structure
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables in the database:", tables)
        
        # Let's check the structure of the hills table
        cursor.execute("PRAGMA table_info(hills);")
        columns = cursor.fetchall()
        print("\nColumns in hills table:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Load data into a pandas DataFrame
        df = pd.read_sql_query("SELECT * FROM hills", conn)
        
        # Check if we have data
        if df.empty:
            print("No hills found in the database.")
            conn.close()
            return None
        
        print(f"\nFound {len(df)} records in the hills table")
        
        # Check if geometry column exists
        if 'geometry' not in df.columns:
            print("Error: No 'geometry' column found in the hills table")
            conn.close()
            return None
        
        # Print a few examples of the geometry strings
        print("\nSample geometry values:")
        for i, geom in enumerate(df['geometry'].head(3)):
            print(f"  {i+1}: {geom[:100]}...")
        
        # Try to convert WKT geometry to shapely objects
        try:
            df['geometry'] = df['geometry'].apply(wkt.loads)
            print("\nSuccessfully converted geometry strings to Shapely objects")
        except Exception as e:
            print(f"\nError converting geometries: {e}")
            # Try handling LINESTRING format issue
            try:
                # Some WKT strings might be improperly formatted
                df['geometry'] = df['geometry'].apply(lambda g: wkt.loads(g.replace('LINESTRING(', 'LINESTRING (').replace(',', ', ')))
                print("Converted geometries after fixing format")
            except Exception as e2:
                print(f"Second attempt failed: {e2}")
                conn.close()
                return None
        
        # Check for valid geometries
        df['is_valid'] = df['geometry'].apply(lambda g: g.is_valid)
        invalid_count = df[~df['is_valid']].shape[0]
        if invalid_count > 0:
            print(f"\nWarning: {invalid_count} invalid geometries found")
        
        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        
        # Set a coordinate reference system (CRS) - WGS84 is standard for web maps
        gdf.crs = "EPSG:4326"
        
        # Show the bounds of the data
        total_bounds = gdf.total_bounds
        print(f"\nData bounds [minx, miny, maxx, maxy]: {total_bounds}")
        
        # Count number of points in each geometry
        gdf['point_count'] = gdf['geometry'].apply(lambda g: len(list(g.coords)))
        print(f"\nAverage points per geometry: {gdf['point_count'].mean():.1f}")
        print(f"Min points: {gdf['point_count'].min()}, Max points: {gdf['point_count'].max()}")
        
        conn.close()
        return gdf
    
    except Exception as e:
        print(f"Error loading hills data: {e}")
        conn.close()
        return None

def create_debug_map(hills_gdf):
    """Create an interactive map with special debug features."""
    # Get the bounds
    bounds = hills_gdf.total_bounds  # [minx, miny, maxx, maxy]
    
    # Calculate center of the data
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Create a map centered on the data
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,  # Start with a closer zoom
        tiles='OpenStreetMap'
    )
    
    # Add Satellite view
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite'
    ).add_to(m)
    
    # Add a special debug layer
    debug_group = folium.FeatureGroup(name="Debug View")
    m.add_child(debug_group)
    
    # Add a regular layer
    regular_group = folium.FeatureGroup(name="Regular View")
    m.add_child(regular_group)
    
    # Add each hill to both layers with different styles for debugging
    for idx, row in hills_gdf.iterrows():
        # Get the coordinates
        if row['geometry'].geom_type == 'LineString':
            coords = list(row['geometry'].coords)
        else:
            print(f"Unsupported geometry type: {row['geometry'].geom_type} for index {idx}")
            continue
        
        # Only process if we have coordinates
        if not coords:
            continue
            
        # For debugging layer: add markers at start and end points
        folium.CircleMarker(
            location=[coords[0][1], coords[0][0]],
            radius=5,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.7,
            popup=f"Start of Hill {row.get('id', idx)}"
        ).add_to(debug_group)
        
        folium.CircleMarker(
            location=[coords[-1][1], coords[-1][0]],
            radius=5,
            color='red',
            fill=True,
            fill_color='red',
            fill_opacity=0.7,
            popup=f"End of Hill {row.get('id', idx)}"
        ).add_to(debug_group)
        
        # Add the road line (using multiple techniques for reliability)
        
        # Method 1: Direct folium.PolyLine
        folium.PolyLine(
            locations=[[coord[1], coord[0]] for coord in coords],  # Convert [lon, lat] to [lat, lon]
            color='red',
            weight=4,
            opacity=0.8,
            popup=f"Hill {row.get('id', idx)} - Method 1"
        ).add_to(debug_group)
        
        # Method 2: Using GeoJson with correct coordinates
        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': coords
            },
            'properties': {
                'id': row.get('id', idx),
                'name': row.get('name', f"Hill {row.get('id', idx)}"),
                'gradient': row.get('avg_gradient', 0)
            }
        }
        
        folium.GeoJson(
            feature,
            style_function=lambda x: {
                'color': 'green',
                'weight': 3,
                'opacity': 0.8
            },
            popup=f"Hill {row.get('id', idx)} - Method 2"
        ).add_to(regular_group)
        
        # Method 3: Alternate PolyLine with different coordinate handling
        points = [[lat, lon] for lon, lat in coords]
        folium.PolyLine(
            points,
            color='blue',
            weight=4,
            opacity=0.8,
            popup=f"Hill {row.get('id', idx)} - Method 3"
        ).add_to(regular_group)
    
    # Add bounds rectangle to show the data extent
    folium.Rectangle(
        bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
        color='black',
        weight=2,
        fill=False,
        popup="Data Bounds"
    ).add_to(debug_group)
    
    # Add a marker for Vejle, Denmark for reference
    folium.Marker(
        location=[55.7061, 9.5357],  # Vejle coordinates
        popup="Vejle, Denmark",
        icon=folium.Icon(color='purple', icon='info-sign')
    ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Make sure to zoom to fit the data
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    return m

def main():
    """Main function to create and save the debug map."""
    # Get database path from command line or use default
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'hills.db'
    
    # Load hills data with debug info
    hills_gdf = load_hills_from_db(db_path)
    
    if hills_gdf is not None:
        # Filter for just valid geometries
        hills_gdf = hills_gdf[hills_gdf['is_valid']]
        
        if len(hills_gdf) == 0:
            print("No valid geometries found after filtering.")
            return None
            
        # Check for roads near Vejle
        vejle_bounds = [9.45, 55.65, 9.60, 55.75]  # Rough bounds for Vejle
        vejle_hills = hills_gdf.cx[vejle_bounds[0]:vejle_bounds[2], vejle_bounds[1]:vejle_bounds[3]]
        print(f"\nFound {len(vejle_hills)} hills in Vejle area")
        
        # Create map
        m = create_debug_map(hills_gdf)
        
        # Save map to HTML file
        output_file = 'debug_hills_map.html'
        m.save(output_file)
        
        print(f"\nDebug map saved to {output_file}")
        
        # Open map in web browser
        webbrowser.open('file://' + os.path.realpath(output_file))
        
        return hills_gdf
    
    return None

if __name__ == "__main__":
    hills_gdf = main()