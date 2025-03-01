# backend/services/road_processor.py
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
import logging
from scipy.signal import savgol_filter

from .dhm_processor import DHMProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RoadProcessor:
    """Processes road data and calculates gradients using elevation data."""
    
    def __init__(self, roads_file='data/denmark_roads.geojson', dhm_processor=None):
        """Initialize with the road network file and DHM processor."""
        self.roads_file = roads_file
        self.dhm_processor = dhm_processor if dhm_processor else DHMProcessor()
        self.roads_gdf = None
        
    def load_roads(self):
        """Load road network data."""
        logger.info(f"Loading road data from {self.roads_file}")
        
        # Check if file exists
        if not os.path.exists(self.roads_file):
            raise FileNotFoundError(f"Road file not found: {self.roads_file}")
            
        # Load roads as GeoDataFrame
        self.roads_gdf = gpd.read_file(self.roads_file)
        
        # Ensure roads are in the same CRS as the DHM
        if self.dhm_processor.dhm_dataset is None:
            self.dhm_processor.load_merged_dhm()
        
        dhm_crs = self.dhm_processor.dhm_dataset.crs
        if self.roads_gdf.crs != dhm_crs:
            logger.info(f"Reprojecting roads from {self.roads_gdf.crs} to {dhm_crs}")
            self.roads_gdf = self.roads_gdf.to_crs(dhm_crs)
            
        logger.info(f"Loaded {len(self.roads_gdf)} road segments")
        return self.roads_gdf
        
    def calculate_road_gradients(self, sample_distance=10, smoothing=True):
        """
        Calculate gradients for all road segments.
        
        Args:
            sample_distance: Distance between elevation samples in meters
            smoothing: Whether to apply smoothing to elevation profiles
        
        Returns:
            GeoDataFrame with road segments and gradient information
        """
        if self.roads_gdf is None:
            self.load_roads()
            
        logger.info("Calculating road gradients...")
        
        # Create columns for gradient data
        self.roads_gdf['elevation_profile'] = None
        self.roads_gdf['avg_gradient'] = None
        self.roads_gdf['max_gradient'] = None
        self.roads_gdf['length_m'] = None
        self.roads_gdf['elevation_gain'] = None
        
        # Process each road segment
        for idx, row in self.roads_gdf.iterrows():
            if idx % 100 == 0:
                logger.info(f"Processing road segment {idx}/{len(self.roads_gdf)}")
                
            # Get the geometry
            line = row.geometry
            
            # Calculate length in meters
            length = line.length
            self.roads_gdf.at[idx, 'length_m'] = length
            
            # Skip very short segments
            if length < sample_distance * 2:
                continue
                
            # Sample elevations along the line
            elevations = self.dhm_processor.sample_elevations_along_line(line, sample_distance)
            
            # Skip if we couldn't get valid elevation data
            if not elevations or any(e is None for _, e in elevations):
                continue
                
            # Extract distances and elevation values
            distances = [d for d, _ in elevations]
            elev_values = [e for _, e in elevations]
            
            # Apply smoothing if requested
            if smoothing and len(elev_values) > 5:
                try:
                    # Use Savitzky-Golay filter for smoothing
                    window_length = min(5, len(elev_values) - 2)
                    if window_length % 2 == 0:  # Must be odd
                        window_length += 1
                    poly_order = min(2, window_length - 1)
                    elev_values = savgol_filter(elev_values, window_length, poly_order)
                except Exception as e:
                    logger.warning(f"Smoothing failed for segment {idx}: {e}")
            
            # Calculate gradients between consecutive points
            gradients = []
            for i in range(1, len(distances)):
                dist_diff = distances[i] - distances[i-1]
                elev_diff = elev_values[i] - elev_values[i-1]
                
                if dist_diff > 0:
                    gradient = (elev_diff / dist_diff) * 100  # Convert to percentage
                    gradients.append(gradient)
            
            # Store elevation profile and gradient statistics
            if gradients:
                self.roads_gdf.at[idx, 'elevation_profile'] = list(zip(distances, elev_values))
                self.roads_gdf.at[idx, 'avg_gradient'] = float(np.mean(np.abs(gradients)))
                self.roads_gdf.at[idx, 'max_gradient'] = float(np.max(np.abs(gradients)))
                
                # Calculate total elevation gain (sum of all positive elevation changes)
                elev_gain = sum(max(0, elev_values[i] - elev_values[i-1]) for i in range(1, len(elev_values)))
                self.roads_gdf.at[idx, 'elevation_gain'] = float(elev_gain)
        
        logger.info("Gradient calculation complete")
        return self.roads_gdf
    
    def identify_hills(self, min_length=100, min_gradient=3.0, min_elevation_gain=10):
        """
        Identify hill segments based on criteria.
        
        Args:
            min_length: Minimum length in meters
            min_gradient: Minimum average gradient percentage
            min_elevation_gain: Minimum elevation gain in meters
            
        Returns:
            GeoDataFrame containing only hill segments
        """
        if self.roads_gdf is None or 'avg_gradient' not in self.roads_gdf.columns:
            logger.warning("Road gradients have not been calculated yet")
            self.calculate_road_gradients()
            
        logger.info(f"Identifying hills with min_length={min_length}m, min_gradient={min_gradient}%, min_gain={min_elevation_gain}m")
        
        # Filter for hill segments
        hills_gdf = self.roads_gdf[
            (self.roads_gdf['length_m'] >= min_length) & 
            (self.roads_gdf['avg_gradient'] >= min_gradient) &
            (self.roads_gdf['elevation_gain'] >= min_elevation_gain)
        ].copy()
        
        # Categorize hills by difficulty (example categories)
        def categorize_hill(row):
            avg_grad = row['avg_gradient']
            length = row['length_m']
            
            if avg_grad >= 10:
                return "HC"  # Hors Categorie (very steep)
            elif avg_grad >= 7:
                return "1"   # Category 1
            elif avg_grad >= 5:
                return "2"   # Category 2
            elif avg_grad >= 3:
                return "3"   # Category 3
            else:
                return "4"   # Category 4
                
        hills_gdf['category'] = hills_gdf.apply(categorize_hill, axis=1)
        
        logger.info(f"Identified {len(hills_gdf)} hill segments")
        return hills_gdf
    
    def save_processed_roads(self, output_file='data/processed_roads.geojson'):
        """Save the processed road data to a file."""
        if self.roads_gdf is None:
            logger.warning("No processed road data available to save")
            return False
            
        # Convert elevation_profile from lists to strings for GeoJSON compatibility
        roads_to_save = self.roads_gdf.copy()
        
        # Convert complex data to strings for storage
        if 'elevation_profile' in roads_to_save.columns:
            roads_to_save['elevation_profile'] = roads_to_save['elevation_profile'].apply(
                lambda x: str(x) if x is not None else None
            )
            
        # Save to file
        logger.info(f"Saving processed road data to {output_file}")
        roads_to_save.to_file(output_file, driver='GeoJSON')
        
        return True
    
    def save_hills(self, output_file='data/denmark_hills.geojson'):
        """Save identified hills to a file."""
        hills_gdf = self.identify_hills()
        
        if hills_gdf.empty:
            logger.warning("No hills identified to save")
            return False
            
        # Convert complex data to strings for storage
        hills_to_save = hills_gdf.copy()
        if 'elevation_profile' in hills_to_save.columns:
            hills_to_save['elevation_profile'] = hills_to_save['elevation_profile'].apply(
                lambda x: str(x) if x is not None else None
            )
            
        # Save to file
        logger.info(f"Saving identified hills to {output_file}")
        hills_to_save.to_file(output_file, driver='GeoJSON')
        
        return True