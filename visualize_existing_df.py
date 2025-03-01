import pandas as pd
import geopandas as gpd
from shapely import wkt
import folium
from folium.features import GeoJsonPopup, GeoJsonTooltip
import branca.colormap as cm
import os
import webbrowser

def convert_to_geodataframe(hills_df):
    """Convert pandas DataFrame to GeoDataFrame if needed."""
    # Check if input is already a GeoDataFrame
    if isinstance(hills_df, gpd.GeoDataFrame) and hills_df.geometry.name == 'geometry':
        return hills_df
    
    # If not, try to convert it
    try:
        # Check if there's a geometry column that needs parsing
        if 'geometry' in hills_df.columns and isinstance(hills_df['geometry'].iloc[0], str):
            hills_df['geometry'] = hills_df['geometry'].apply(wkt.loads)
        
        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame(hills_df, geometry='geometry')
        
        # Set a coordinate reference system (CRS) - WGS84 is standard for web maps
        gdf.crs = "EPSG:4326"
        
        return gdf
    except Exception as e:
        print(f"Error converting to GeoDataFrame: {e}")
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
    if 'avg_gradient' in hills_gdf.columns:
        gradient_col = 'avg_gradient'
    elif 'gradient' in hills_gdf.columns:
        gradient_col = 'gradient'
    else:
        # Default to a constant if no gradient column exists
        hills_gdf['gradient'] = 5
        gradient_col = 'gradient'
    
    color_map = cm.LinearColormap(
        ['green', 'yellow', 'orange', 'red'],
        vmin=hills_gdf[gradient_col].min(),
        vmax=hills_gdf[gradient_col].max()
    )
    
    # Create feature groups for different hill categories
    categories = {}
    category_col = None
    
    # Check which column might contain category information
    if 'category' in hills_gdf.columns:
        category_col = 'category'
    
    if category_col and category_col in hills_gdf.columns:
        for cat in hills_gdf[category_col].unique():
            if cat and not pd.isna(cat):
                categories[cat] = folium.FeatureGroup(name=f"Category {cat}")
                m.add_child(categories[cat])
    
    # Default group for hills without category
    default_group = folium.FeatureGroup(name="All Hills")
    m.add_child(default_group)
    
    # Determine which columns to use in popups
    common_properties = ['id', 'name', category_col, 'length_m', gradient_col, 'max_gradient', 'elevation_gain']
    available_properties = [prop for prop in common_properties if prop and prop in hills_gdf.columns]
    
    # Define popup and tooltip
    popup = GeoJsonPopup(
        fields=available_properties,
        aliases=[prop.replace('_', ' ').title() for prop in available_properties],
        localize=True,
        labels=True,
        style="background-color: white;"
    )
    
    tooltip_fields = ['name', gradient_col] if 'name' in hills_gdf.columns else [gradient_col]
    tooltip_aliases = ['Name', 'Gradient (%)'] if 'name' in hills_gdf.columns else ['Gradient (%)']
    
    tooltip = GeoJsonTooltip(
        fields=tooltip_fields,
        aliases=tooltip_aliases,
        localize=True,
        sticky=False,
        labels=True
    )
    
    # Add each hill to the map
    for idx, row in hills_gdf.iterrows():
        # Determine color based on gradient
        color = color_map(row[gradient_col])
        
        # Create properties dict based on available columns
        properties = {}
        for prop in available_properties:
            if prop in row:
                value = row[prop]
                # Format numbers to 1 decimal place
                if isinstance(value, (int, float)):
                    properties[prop] = round(value, 1)
                else:
                    properties[prop] = value if not pd.isna(value) else "Unknown"
        
        # Create GeoJSON for this hill
        feature = {
            'type': 'Feature',
            'geometry': row['geometry'].__geo_interface__,
            'properties': properties
        }
        
        # Add to appropriate group
        if category_col and category_col in row and row[category_col] in categories:
            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'color': color,
                    'weight': 4,
                    'opacity': 0.8
                },
                popup=popup,
                tooltip=tooltip
            ).add_to(categories[row[category_col]])
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

def visualize_hills_df(hills_df, output_file='hills_map.html', open_browser=True):
    """Visualize hills from a DataFrame on an interactive map."""
    # Convert to GeoDataFrame if needed
    hills_gdf = convert_to_geodataframe(hills_df)
    
    if hills_gdf is None:
        print("Failed to convert input to GeoDataFrame.")
        return None
    
    # Create map
    m = create_hills_map(hills_gdf)
    
    # Save map to HTML file
    m.save(output_file)
    
    print(f"Map saved to {output_file}")
    
    # Open map in web browser if requested
    if open_browser:
        webbrowser.open('file://' + os.path.realpath(output_file))
    
    return m

if __name__ == "__main__":
    # Just a demonstration of how to use the function
    # This will be executed only if the script is run directly, not when imported
    print("This script is designed to be imported and used with an existing DataFrame.")
    print("Example usage:")
    print("from visualize_existing_df import visualize_hills_df")
    print("visualize_hills_df(hills_df)")