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

def load_hills_from_db(db_path='hills.db'):
    """Load hills data from the database into a GeoDataFrame."""
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return None
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    
    try:
        # Load data into a pandas DataFrame
        df = pd.read_sql_query("SELECT * FROM hills", conn)
        
        # Check if we have data
        if df.empty:
            print("No hills found in the database.")
            conn.close()
            return None
        
        # Convert WKT geometry to shapely objects
        df['geometry'] = df['geometry'].apply(wkt.loads)
        
        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        
        # Set a coordinate reference system (CRS) - WGS84 is standard for web maps
        gdf.crs = "EPSG:4326"
        
        print(f"Loaded {len(gdf)} hills from database.")
        conn.close()
        return gdf
    
    except Exception as e:
        print(f"Error loading hills data: {e}")
        conn.close()
        return None

def create_hills_map(hills_gdf):
    """Create an interactive map with hills from the GeoDataFrame."""
    # Calculate center point for the map (average of all geometries)
    center_lat = hills_gdf.geometry.centroid.y.mean()
    center_lon = hills_gdf.geometry.centroid.x.mean()
    
    # Create a folium map centered on Denmark
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=9,
        tiles='OpenStreetMap'
    )
    
    # Add Satellite view as an option
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite'
    ).add_to(m)
    
    # Create a color map for hill gradients
    color_map = cm.LinearColormap(
        ['green', 'yellow', 'orange', 'red'],
        vmin=hills_gdf['avg_gradient'].min(),
        vmax=hills_gdf['avg_gradient'].max()
    )
    
    # Create feature groups for different hill categories
    categories = {}
    if 'category' in hills_gdf.columns:
        for cat in hills_gdf['category'].unique():
            if cat and not pd.isna(cat):
                categories[cat] = folium.FeatureGroup(name=f"Category {cat}")
                m.add_child(categories[cat])
    
    # Default group for hills without category
    default_group = folium.FeatureGroup(name="All Hills")
    m.add_child(default_group)
    
    # Define popup and tooltip
    popup = GeoJsonPopup(
        fields=['name', 'category', 'length_m', 'avg_gradient', 'max_gradient', 'elevation_gain'],
        aliases=['Name', 'Category', 'Length (m)', 'Avg Gradient (%)', 'Max Gradient (%)', 'Elevation Gain (m)'],
        localize=True,
        labels=True,
        style="background-color: white;"
    )
    
    tooltip = GeoJsonTooltip(
        fields=['name', 'avg_gradient'],
        aliases=['Name', 'Gradient (%)'],
        localize=True,
        sticky=False,
        labels=True
    )
    
    # Add each hill to the map
    for idx, row in hills_gdf.iterrows():
        # Determine color based on gradient
        color = color_map(row['avg_gradient'])
        
        # Create GeoJSON for this hill
        feature = {
            'type': 'Feature',
            'geometry': row['geometry'].__geo_interface__,
            'properties': {
                'name': row.get('name', f'Hill {row["id"]}'),
                'category': row.get('category', 'Unknown'),
                'length_m': round(row.get('length_m', 0), 1),
                'avg_gradient': round(row.get('avg_gradient', 0), 1),
                'max_gradient': round(row.get('max_gradient', 0), 1),
                'elevation_gain': round(row.get('elevation_gain', 0), 1)
            }
        }
        
        # Add to appropriate group
        if 'category' in row and row['category'] in categories:
            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'color': color,
                    'weight': 4,
                    'opacity': 0.8
                },
                popup=popup,
                tooltip=tooltip
            ).add_to(categories[row['category']])
        else:
            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'color': color,
                    'weight': 4,
                    'opacity': 0.8
                },
                popup=popup,
                tooltip=tooltip
            ).add_to(default_group)
    
    # Add color legend
    color_map.caption = 'Hill Gradient (%)'
    m.add_child(color_map)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m

def main():
    """Main function to create and save the map."""
    # Get database path from command line or use default
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'hills.db'
    
    # Load hills data
    hills_gdf = load_hills_from_db(db_path)
    
    if hills_gdf is not None:
        # Create map
        m = create_hills_map(hills_gdf)
        
        # Save map to HTML file
        output_file = 'hills_map.html'
        m.save(output_file)
        
        print(f"Map saved to {output_file}")
        
        # Open map in web browser
        webbrowser.open('file://' + os.path.realpath(output_file))
        
        return hills_gdf
    
    return None

if __name__ == "__main__":
    hills_gdf = main()
    
    # Keep the DataFrame available for further analysis
    print("\nThe hills data is now available in the 'hills_gdf' variable for further analysis.")
    print("You can run this script in interactive mode to explore the data:")
    print("python -i visualize_hills_map.py")