from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import json
import os
import logging
from datetime import datetime
from flask import send_from_directory, abort
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
db = SQLAlchemy()

# Define models
class Road(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    highway = db.Column(db.String(50), nullable=False)
    surface = db.Column(db.String(50), nullable=True)
    length_meters = db.Column(db.Float, nullable=False)
    min_elevation = db.Column(db.Float, nullable=False)
    max_elevation = db.Column(db.Float, nullable=False)
    gradient = db.Column(db.Float, nullable=False)
    maxspeed = db.Column(db.Integer, nullable=True)
    coordinates_json = db.Column(db.Text, nullable=False)  # Stored as GeoJSON or JSON array
    elevation_profile_json = db.Column(db.Text, nullable=True)  # Stored as JSON array
    featured = db.Column(db.Boolean, default=False)
    favorite = db.Column(db.Boolean, default=False)
    difficulty = db.Column(db.String(20), nullable=True)
    
    def get_coordinates(self):
        """Return the road's coordinates as a Python list"""
        if self.coordinates_json:
            return json.loads(self.coordinates_json)
        return []
    
    def get_elevation_profile(self):
        """Return the road's elevation profile as a Python list"""
        if self.elevation_profile_json:
            return json.loads(self.elevation_profile_json)
        
        # If no stored profile, generate a simple one based on min/max elevation
        profile_length = int(self.length_meters / 50)  # Sample every 50 meters
        if profile_length < 2:
            profile_length = 2
            
        elevation_diff = self.max_elevation - self.min_elevation
        
        # Create a simple profile with a linear increase and some small variations
        profile = []
        for i in range(profile_length):
            # Calculate distance along the road
            distance = (i / (profile_length - 1)) * self.length_meters
            
            # Calculate elevation with a simple curve
            # This is just an example - real elevation profiles would be more complex
            elevation = self.min_elevation + (elevation_diff * (i / (profile_length - 1)))
            
            profile.append({
                'distance': distance,
                'elevation': elevation
            })
            
        return profile

    def to_dict(self):
        """Convert road object to dictionary for API response"""
        return {
            'id': self.id,
            'name': self.name,
            'highway': self.highway,
            'surface': self.surface if hasattr(self, 'surface') else None,
            'length_meters': self.length_meters,
            'min_elevation': self.min_elevation,
            'max_elevation': self.max_elevation,
            'gradient': self.gradient,
            'maxspeed': self.maxspeed,
            'coordinates': self.get_coordinates(),
            'favorite': self.favorite if hasattr(self, 'favorite') else False,
            'difficulty': self.difficulty if hasattr(self, 'difficulty') else None
        }

class Hill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=True)
    length = db.Column(db.Float, nullable=False)  # in km
    height = db.Column(db.Float, nullable=False)  # in meters
    gradient = db.Column(db.Float, nullable=False)  # in percentage
    rating = db.Column(db.Integer, nullable=True)  # 1-5 star rating
    road_id = db.Column(db.Integer, db.ForeignKey('road.id'), nullable=True)
    image = db.Column(db.String(255), nullable=True)  # Path to hill image
    
    # Relationship to road
    road = db.relationship('Road', backref=db.backref('hills', lazy=True))
    
    def to_dict(self):
        """Convert hill object to dictionary for API response"""
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'length': self.length,
            'height': self.height,
            'gradient': self.gradient,
            'rating': self.rating,
            'road_id': self.road_id,
            'image': self.image
        }

# Helper function for consistent API responses
def api_response(data=None, status="success", message=None):
    response = {
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    if message:
        response["message"] = message
    
    return jsonify(response)

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    import os
    app.config.from_pyfile(os.path.join(os.path.dirname(__file__), 'config.py'))
    
    # Initialize extensions
    db.init_app(app)
    
    # Import blueprints
    from backend.routes.hill_routes import hill_routes
    
    # Register blueprints
    app.register_blueprint(hill_routes)
    
    # Ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Routes from existing app.py
    @app.route('/')
    def index():
        # Get featured roads for the homepage
        featured_roads = Road.query.filter_by(featured=True).limit(4).all()
        
        # If no featured roads, get some with highest gradient
        if len(featured_roads) < 4:
            additional_roads = Road.query.order_by(Road.gradient.desc()).limit(4 - len(featured_roads)).all()
            featured_roads.extend(additional_roads)
        
        # Get top hills for the table
        top_hills = Hill.query.order_by(Hill.length.desc()).limit(10).all()
        
        # Get road statistics for the homepage
        total_roads = Road.query.count()
        total_length = db.session.query(db.func.sum(Road.length_meters)/1000).scalar() or 0
        max_gradient = db.session.query(db.func.max(Road.gradient)).scalar() or 0
        avg_gradient = db.session.query(db.func.avg(Road.gradient)).scalar() or 0
        
        return render_template('index.html', 
                            featured_roads=featured_roads,
                            top_hills=top_hills,
                            total_roads=total_roads,
                            total_length=total_length,
                            max_gradient=max_gradient,
                            avg_gradient=avg_gradient)

    @app.route('/map')
    def map_view():
        # Pass Mapbox token to template
        mapbox_token = app.config.get('MAPBOX_TOKEN', '')
        return render_template('map.html', mapbox_token=mapbox_token)
    
    @app.route('/hill/<int:hill_id>')
    def hill_detail(hill_id):
        # Pass Mapbox token to template
        mapbox_token = app.config.get('MAPBOX_TOKEN', '')
        return render_template('hill_detail.html', hill_id=hill_id, mapbox_token=mapbox_token)

    @app.route('/statistics')
    def statistics():
        # Get statistics for the page
        total_roads = Road.query.count()
        total_length = db.session.query(db.func.sum(Road.length_meters)/1000).scalar() or 0
        max_gradient = db.session.query(db.func.max(Road.gradient)).scalar() or 0
        avg_gradient = db.session.query(db.func.avg(Road.gradient)).scalar() or 0
        
        # Get hills for different categories
        longest_hills = Hill.query.order_by(Hill.length.desc()).limit(5).all()
        steepest_hills = Hill.query.order_by(Hill.gradient.desc()).limit(5).all()
        highest_hills = Hill.query.order_by(Hill.height.desc()).limit(5).all()
        
        return render_template('statistics.html',
                            total_roads=total_roads,
                            total_length=total_length,
                            max_gradient=max_gradient,
                            avg_gradient=avg_gradient,
                            longest_hills=longest_hills,
                            steepest_hills=steepest_hills,
                            highest_hills=highest_hills)

    @app.route('/about')
    def about():
        return render_template('about.html')

    @app.route('/contribute')
    def contribute():
        return render_template('contribute.html')

    # API routes
    @app.route('/api/roads')
    def api_roads():
        # Get query parameters for filtering
        min_gradient = request.args.get('min_gradient', type=float)
        max_gradient = request.args.get('max_gradient', type=float)
        min_length = request.args.get('min_length', type=float)
        max_length = request.args.get('max_length', type=float)
        road_type = request.args.get('road_type')
        
        # Base query
        query = Road.query
        
        # Apply filters if provided
        if min_gradient is not None:
            query = query.filter(Road.gradient >= min_gradient)
        if max_gradient is not None:
            query = query.filter(Road.gradient <= max_gradient)
        if min_length is not None:
            query = query.filter(Road.length_meters/1000 >= min_length)
        if max_length is not None:
            query = query.filter(Road.length_meters/1000 <= max_length)
        if road_type:
            query = query.filter(Road.highway == road_type)
        
        # Get roads
        roads = query.all()
        
        # Convert to dictionary format with coordinates
        roads_data = [road.to_dict() for road in roads]
        
        # Support both new and old API formats
        # The new API has direct attribute access, while the old one uses .data
        return jsonify({'roads': roads_data, 'status': 'success'})

    @app.route('/api/roads/<int:road_id>')
    def api_road_detail(road_id):
        road = Road.query.get_or_404(road_id)
        
        # Get elevation profile
        elevation_profile = road.get_elevation_profile()
        
        # Create full road data
        road_data = road.to_dict()
        road_data['elevation_profile'] = elevation_profile
        
        # Return in the same format as the roads list endpoint
        return jsonify(road_data)

    @app.route('/api/roads/<int:road_id>/profile')
    def api_road_profile(road_id):
        road = Road.query.get_or_404(road_id)
        
        # Get elevation profile
        elevation_profile = road.get_elevation_profile()
        
        # Check if this is an HTMX request
        if request.headers.get('HX-Request') == 'true':
            # Return HTML partial for the profile
            return render_template('components/elevation_profile.html', 
                                road=road, 
                                elevation_profile=elevation_profile)
        else:
            # Return JSON data
            return jsonify({
                'status': 'success',
                'data': {
                    'road_id': road.id,
                    'road_name': road.name,
                    'elevation_profile': elevation_profile
                }
            })

    @app.route('/api/top-hills')
    def api_top_hills():
        # Get filter type
        filter_type = request.args.get('filter', 'longest')
        
        # Get hills based on filter
        if filter_type == 'longest':
            hills = Hill.query.order_by(Hill.length.desc()).limit(10).all()
        elif filter_type == 'steepest':
            hills = Hill.query.order_by(Hill.gradient.desc()).limit(10).all()
        elif filter_type == 'highest':
            hills = Hill.query.order_by(Hill.height.desc()).limit(10).all()
        else:
            hills = Hill.query.order_by(Hill.length.desc()).limit(10).all()
        
        # Convert to dictionary format
        hills_data = [hill.to_dict() for hill in hills]
        
        # Support both API formats
        return jsonify({'hills': hills_data, 'status': 'success'})

    @app.route('/api/stats')
    def api_stats():
        # Get road statistics
        total_roads = Road.query.count()
        total_length = db.session.query(db.func.sum(Road.length_meters)/1000).scalar() or 0
        
        # Get gradient statistics
        gradient_stats = {
            'min': db.session.query(db.func.min(Road.gradient)).scalar() or 0,
            'max': db.session.query(db.func.max(Road.gradient)).scalar() or 0,
            'mean': db.session.query(db.func.avg(Road.gradient)).scalar() or 0
        }
        
        # Get highway types
        highway_types = {}
        roads_by_type = db.session.query(Road.highway, db.func.count(Road.id)).group_by(Road.highway).all()
        for highway_type, count in roads_by_type:
            highway_types[highway_type] = count
        
        # Return stats in a structured format
        return api_response({
            'total_roads': total_roads,
            'total_length_km': total_length,
            'gradient_stats': gradient_stats,
            'highway_types': highway_types
        })
    
        
    @app.route('/static/images/<path:filename>')
    def custom_static_images(filename):
        try:
            return send_from_directory(os.path.join(app.root_path, 'static/images'), filename)
        except:
            # Return a default image if the requested one doesn't exist
            if filename == 'default-hill.jpg':
                # You can return a different existing image as a fallback
                # Replace 'contours.png' with an image you know exists
                return send_from_directory(os.path.join(app.root_path, 'static/images'), 'contours.png')
            abort(404)
    
    @app.route('/search')
    def search_hills():
        # Get search parameters
        location = request.args.get('location', '')
        difficulty = request.args.get('difficulty', '')
        length = request.args.get('length', type=float)
        
        # Build query
        query = Hill.query
        
        if location:
            query = query.filter(Hill.location.ilike(f'%{location}%'))
        
        if difficulty:
            if difficulty == 'easy':
                query = query.filter(Hill.gradient < 4)
            elif difficulty == 'moderate':
                query = query.filter(Hill.gradient >= 4, Hill.gradient < 8)
            elif difficulty == 'challenging':
                query = query.filter(Hill.gradient >= 8, Hill.gradient < 12)
            elif difficulty == 'extreme':
                query = query.filter(Hill.gradient >= 12)
        
        if length:
            query = query.filter(Hill.length <= length)
        
        # Get results
        results = query.all()
        
        return render_template('search_results.html', results=results, search_params=request.args)

    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # Create tables on startup
    with app.app_context():
        db.create_all()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))