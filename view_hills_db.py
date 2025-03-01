import sqlite3
import pandas as pd
import sys
import os
from shapely import wkt
import geopandas as gpd

def print_separator():
    """Print a separator line to make output more readable."""
    print("\n" + "="*80 + "\n")

def connect_to_database(db_path='hills.db'):
    """Connect to the SQLite database."""
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        sys.exit(1)
    
    try:
        return sqlite3.connect(db_path)
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def get_tables(conn):
    """Get a list of tables in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]

def view_hills_data(conn):
    """View data from the hills table."""
    print_separator()
    print("HILLS TABLE DATA")
    print_separator()
    
    try:
        # Load data into a pandas DataFrame
        df = pd.read_sql_query("SELECT * FROM hills", conn)
        
        # Convert to GeoDataFrame if possible
        if 'geometry' in df.columns:
            try:
                df['geometry'] = df['geometry'].apply(wkt.loads)
                df = gpd.GeoDataFrame(df, geometry='geometry')
                print("Successfully converted to GeoDataFrame with geometry column.")
            except Exception as e:
                print(f"Note: Could not parse geometry column: {e}")
        
        # Display basic information
        print(f"Number of hills: {len(df)}")
        print("\nColumns:")
        for col in df.columns:
            print(f"  - {col}")
        
        print("\nDataFrame Info:")
        print(df.info())
        
        print("\nStatistical Summary:")
        numeric_cols = df.select_dtypes(include=['number']).columns
        print(df[numeric_cols].describe())
        
        # Display first few rows
        print("\nFirst 5 rows:")
        print(df.head())
        
        return df
    except Exception as e:
        print(f"Error querying hills table: {e}")
        return None

def view_elevation_profiles(conn, hill_id=None):
    """View data from the elevation_profiles table."""
    print_separator()
    print("ELEVATION PROFILES DATA")
    print_separator()
    
    try:
        if hill_id is not None:
            query = f"SELECT * FROM elevation_profiles WHERE hill_id = {hill_id} ORDER BY distance"
            print(f"Showing elevation profile for hill_id = {hill_id}")
        else:
            # Just get a sample to avoid overwhelming output
            query = "SELECT hill_id, COUNT(*) as point_count, MIN(elevation) as min_elev, MAX(elevation) as max_elev FROM elevation_profiles GROUP BY hill_id LIMIT 20"
            print("Showing summary of elevation profiles (first 20 hills)")
        
        df = pd.read_sql_query(query, conn)
        
        print(f"\nNumber of rows: {len(df)}")
        print("\nFirst 10 rows:")
        print(df.head(10))
        
        return df
    except Exception as e:
        print(f"Error querying elevation_profiles table: {e}")
        return None

def explore_database(db_path='hills.db'):
    """Main function to explore the database."""
    conn = connect_to_database(db_path)
    
    print("DENMARK HILL GRADIENT ANALYZER DATABASE")
    print(f"Database file: {db_path}")
    
    # List tables
    tables = get_tables(conn)
    print(f"\nTables in database: {', '.join(tables)}")
    
    # View hills data
    hills_df = view_hills_data(conn)
    
    # Check if elevation_profiles table exists
    if 'elevation_profiles' in tables:
        # View elevation profiles summary
        profiles_summary = view_elevation_profiles(conn)
        
        # If hills data was loaded successfully, view elevation profile for first hill
        if hills_df is not None and not hills_df.empty:
            first_hill_id = hills_df.iloc[0]['id']
            print_separator()
            print(f"DETAILED ELEVATION PROFILE FOR HILL ID {first_hill_id}")
            first_profile = view_elevation_profiles(conn, first_hill_id)
    
    conn.close()
    
    return hills_df

if __name__ == "__main__":
    # Check if database path is provided as an argument
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'hills.db'
    hills_df = explore_database(db_path)
    
    # Keep the DataFrame available for further analysis
    print_separator()
    print("The hills data is now available in the 'hills_df' variable for further analysis.")
    print("You can run this script in interactive mode to explore the data:")
    print("python -i view_hills_db.py")