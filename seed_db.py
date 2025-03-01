# seed_db.py
import os
import argparse
import logging
from backend.services.dhm_processor import DHMProcessor
from backend.services.road_processor import RoadProcessor
from backend.services.hill_database import HillDatabase

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_data(args):
    """Process data and populate the database."""
    logger.info("Starting data processing...")
    
    # Initialize processors
    dhm_processor = DHMProcessor(args.data_dir)
    road_processor = RoadProcessor(args.roads_file, dhm_processor)
    hill_db = HillDatabase(args.db_path)
    
    # Process DHM data if requested
    if args.process_dhm:
        logger.info("Processing DHM data...")
        try:
            merged_path = dhm_processor.merge_dhm_files()
            logger.info(f"DHM data processed and saved to {merged_path}")
        except Exception as e:
            logger.error(f"Error processing DHM data: {e}")
            if not args.continue_on_error:
                return False
    
    # Process road data if requested
    if args.process_roads:
        logger.info("Processing road data...")
        try:
            # Load roads
            roads_gdf = road_processor.load_roads()
            logger.info(f"Loaded {len(roads_gdf)} road segments")
            
            # Calculate gradients
            road_processor.calculate_road_gradients(
                sample_distance=args.sample_distance,
                smoothing=not args.no_smoothing
            )
            
            # Save processed roads
            output_path = os.path.join(args.data_dir, 'processed_roads.geojson')
            saved = road_processor.save_processed_roads(output_path)
            if saved:
                logger.info(f"Processed road data saved to {output_path}")
            else:
                logger.error("Failed to save processed road data")
                if not args.continue_on_error:
                    return False
        except Exception as e:
            logger.error(f"Error processing road data: {e}")
            if not args.continue_on_error:
                return False
    
    # Identify hills if requested
    if args.identify_hills:
        logger.info("Identifying hills...")
        try:
            # Set hill identification parameters
            # These should be set before calling identify_hills()
            road_processor.HILL_MIN_LENGTH = args.min_length
            road_processor.HILL_MIN_GRADIENT = args.min_gradient
            road_processor.HILL_MIN_ELEVATION_GAIN = args.min_elevation_gain
            
            # Identify and save hills
            hills_path = os.path.join(args.data_dir, 'denmark_hills.geojson')
            saved = road_processor.save_hills(hills_path)
            
            if saved:
                logger.info(f"Identified hills saved to {hills_path}")
            else:
                logger.error("Failed to save identified hills")
                if not args.continue_on_error:
                    return False
        except Exception as e:
            logger.error(f"Error identifying hills: {e}")
            if not args.continue_on_error:
                return False
    
    # Import hills to database if requested
    if args.import_database:
        logger.info("Importing hills to database...")
        try:
            # Initialize database
            hill_db.init_db()
            
            # Import hills
            hills_path = os.path.join(args.data_dir, 'denmark_hills.geojson')
            if not os.path.exists(hills_path):
                logger.error(f"Hills file not found: {hills_path}")
                if not args.continue_on_error:
                    return False
            else:
                imported = hill_db.import_hills_from_geojson(hills_path)
                if imported:
                    logger.info(f"Hills imported to database: {args.db_path}")
                else:
                    logger.error("Failed to import hills to database")
                    if not args.continue_on_error:
                        return False
        except Exception as e:
            logger.error(f"Error importing hills to database: {e}")
            if not args.continue_on_error:
                return False
    
    logger.info("Data processing complete!")
    return True

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Process and import hill data.')
    
    # Data directories
    parser.add_argument('--data-dir', default='data', help='Directory containing data files')
    parser.add_argument('--roads-file', default='data/denmark_roads.geojson', help='Path to roads GeoJSON file')
    parser.add_argument('--db-path', default='hills.db', help='Path to SQLite database')
    
    # Processing flags
    parser.add_argument('--process-dhm', action='store_true', help='Process DHM data')
    parser.add_argument('--process-roads', action='store_true', help='Process road data')
    parser.add_argument('--identify-hills', action='store_true', help='Identify hills')
    parser.add_argument('--import-database', action='store_true', help='Import hills to database')
    parser.add_argument('--all', action='store_true', help='Perform all processing steps')
    
    # Processing parameters
    parser.add_argument('--sample-distance', type=float, default=10.0, help='Distance between elevation samples in meters')
    parser.add_argument('--no-smoothing', action='store_true', help='Disable elevation profile smoothing')
    parser.add_argument('--min-length', type=float, default=100.0, help='Minimum hill length in meters')
    parser.add_argument('--min-gradient', type=float, default=3.0, help='Minimum average gradient percentage')
    parser.add_argument('--min-elevation-gain', type=float, default=10.0, help='Minimum elevation gain in meters')
    
    # Error handling
    parser.add_argument('--continue-on-error', action='store_true', help='Continue processing if an error occurs')
    
    args = parser.parse_args()
    
    # If --all is specified, enable all processing steps
    if args.all:
        args.process_dhm = True
        args.process_roads = True
        args.identify_hills = True
        args.import_database = True
    
    # Check if at least one processing step is enabled
    if not (args.process_dhm or args.process_roads or args.identify_hills or args.import_database):
        logger.error("No processing steps specified. Use --help for usage information.")
        return 1
    
    # Process data
    success = process_data(args)
    
    return 0 if success else 1

if __name__ == '__main__':
    exit(main())