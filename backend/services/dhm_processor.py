# backend/services/dhm_processor.py
import os
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
from shapely.geometry import Point, LineString
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DHMProcessor:
    """Processes Denmark's Digital Height Model (DHM) data."""
    
    def __init__(self, dhm_directory='data'):
        """Initialize with directory containing DHM files."""
        self.dhm_directory = dhm_directory
        self.merged_dhm_path = os.path.join(dhm_directory, 'merged_dhm.tif')
        self.dhm_dataset = None
    
    def list_dhm_files(self):
        """List all DTM TIF files in the data directory."""
        return [os.path.join(self.dhm_directory, f) for f in os.listdir(self.dhm_directory) 
                if f.startswith('DTM') and f.endswith('.tif')]
    
    def merge_dhm_files(self, output_path=None):
        """Merge multiple DHM files into a single raster."""
        if output_path:
            self.merged_dhm_path = output_path
            
        # Check if merged file already exists
        if os.path.exists(self.merged_dhm_path):
            logger.info(f"Using existing merged DHM file: {self.merged_dhm_path}")
            return self.merged_dhm_path
            
        dhm_files = self.list_dhm_files()
        
        if not dhm_files:
            raise FileNotFoundError("No DHM files found in the specified directory")
            
        logger.info(f"Merging {len(dhm_files)} DHM files...")
        
        # Open each dataset
        src_files_to_mosaic = [rasterio.open(fp) for fp in dhm_files]
        
        # Merge datasets
        mosaic, out_trans = merge(src_files_to_mosaic)
        
        # Copy the metadata from the first file
        out_meta = src_files_to_mosaic[0].meta.copy()
        
        # Update the metadata
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans,
            "crs": src_files_to_mosaic[0].crs
        })
        
        # Write the mosaic to disk
        with rasterio.open(self.merged_dhm_path, "w", **out_meta) as dest:
            dest.write(mosaic)
            
        # Close all source files
        for src in src_files_to_mosaic:
            src.close()
            
        logger.info(f"Merged DHM saved to: {self.merged_dhm_path}")
        return self.merged_dhm_path
    
    def load_merged_dhm(self):
        """Load the merged DHM file."""
        if not os.path.exists(self.merged_dhm_path):
            self.merge_dhm_files()
            
        self.dhm_dataset = rasterio.open(self.merged_dhm_path)
        return self.dhm_dataset
    
    def get_elevation(self, lon, lat):
        """Get elevation for a specific coordinate."""
        if self.dhm_dataset is None:
            self.load_merged_dhm()
            
        # Get pixel coordinates from map coordinates
        py, px = self.dhm_dataset.index(lon, lat)
        
        # Read the elevation value
        window = ((py, py+1), (px, px+1))
        try:
            elevation_value = self.dhm_dataset.read(1, window=window)[0, 0]
            return float(elevation_value)
        except Exception as e:
            logger.error(f"Error reading elevation at ({lon}, {lat}): {e}")
            return None
    
    def sample_elevations_along_line(self, line_geometry, sample_distance=10):
        """
        Sample elevations along a LineString at regular intervals.
        
        Args:
            line_geometry: Shapely LineString in the same CRS as the DHM
            sample_distance: Distance between samples in meters
            
        Returns:
            List of (distance, elevation) tuples
        """
        if self.dhm_dataset is None:
            self.load_merged_dhm()
            
        # Get the total length of the line
        total_length = line_geometry.length
        
        # Generate points at regular intervals
        elevations = []
        current_distance = 0
        
        while current_distance <= total_length:
            # Get point at current distance
            point = line_geometry.interpolate(current_distance)
            
            # Get elevation
            elev = self.get_elevation(point.x, point.y)
            
            # Store distance (in meters) and elevation
            elevations.append((current_distance, elev))
            
            # Move to next point
            current_distance += sample_distance
            
        return elevations
    
    def close(self):
        """Close the DHM dataset."""
        if self.dhm_dataset is not None:
            self.dhm_dataset.close()
            self.dhm_dataset = None