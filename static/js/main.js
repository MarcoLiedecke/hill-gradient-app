// main.js - Integrated with Mapbox

// Handle road stats loading (preserve existing htmx functionality)
document.addEventListener('htmx:afterRequest', function(evt) {
    if (evt.detail.target.id === 'road-stats' && evt.detail.successful) {
        const data = JSON.parse(evt.detail.response);
        if (data.status === 'success') {
            // Update stats
            document.getElementById('total-roads').textContent = data.data.total_roads;
            document.getElementById('total-length').textContent = data.data.total_length_km.toFixed(1) + ' km';
            document.getElementById('avg-gradient').textContent = data.data.gradient_stats.mean.toFixed(1) + '%';
            document.getElementById('max-gradient').textContent = data.data.gradient_stats.max.toFixed(1) + '%';
            
            // Update road types
            const roadTypesContainer = document.getElementById('road-types');
            if (roadTypesContainer) {
                roadTypesContainer.innerHTML = '';
                Object.entries(data.data.highway_types).forEach(([type, count]) => {
                    roadTypesContainer.innerHTML += `
                        <div class="flex justify-between items-center">
                            <span class="text-gray-700 capitalize">${type}</span>
                            <span class="text-blue-600 font-medium">${count}</span>
                        </div>
                    `;
                });
            }
            
            // Hide loading, show content
            document.getElementById('stats-loading')?.classList.add('hidden');
            document.getElementById('stats-content')?.classList.remove('hidden');
        }
    }
});

// Global variables
let map = null;
let roadLayers = {};

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const menuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (menuButton && mobileMenu) {
        menuButton.addEventListener('click', function() {
            const expanded = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', !expanded);
            mobileMenu.classList.toggle('hidden');
        });
    }
    
    // Handle climb length slider on home page
    const lengthSlider = document.querySelector('input[name="length"]');
    const lengthValue = lengthSlider?.nextElementSibling;
    
    if (lengthSlider && lengthValue) {
        lengthSlider.addEventListener('input', function() {
            lengthValue.textContent = this.value + ' km';
        });
    }
    
    // Initialize hero map on home page
    const heroMapElement = document.getElementById('hero-map');
    if (heroMapElement) {
        initializeHeroMap();
    }
    
    // Initialize main map if we're on the map page
    const mapElement = document.getElementById('map');
    if (mapElement) {
        // Check if we should use Mapbox or fallback to Leaflet
        if (typeof mapboxgl !== 'undefined') {
            initializeMapbox();
        } else {
            initializeLeaflet();
        }
    }
    
    // Handle top hills filtering
    setupHillsFiltering();
});

// Function to initialize small preview map on home page
function initializeHeroMap() {
    // Skip if mapboxgl is not available
    if (typeof mapboxgl === 'undefined') return;
    
    // Get token from meta tag or use default
    const mapboxToken = document.querySelector('meta[name="mapbox-token"]')?.getAttribute('content') || 
                         'pk.eyJ1IjoibGllZGVja2U5NSIsImEiOiJjbGNxZ3E1YnEwNXV3M3BsaHdqaG0yOG5vIn0.nphFmNshYXzqJDdb_SoGnw';
    
    mapboxgl.accessToken = mapboxToken;
    
    // Check theme
    const isDark = document.documentElement.classList.contains('dark');
    const mapStyle = isDark ? 'mapbox://styles/mapbox/dark-v10' : 'mapbox://styles/mapbox/outdoors-v12';
    
    const heroMap = new mapboxgl.Map({
        container: 'hero-map',
        style: mapStyle,
        center: [10.4513, 55.7132], // Center on Denmark
        zoom: 7,
        interactive: false // Disable interactions for the hero map
    });
}

// Function to initialize Mapbox map
function initializeMapbox() {
    // Get token from meta tag or use default
    const mapboxToken = document.querySelector('meta[name="mapbox-token"]')?.getAttribute('content') || 
                         'pk.eyJ1IjoibGllZGVja2U5NSIsImEiOiJjbGNxZ3E1YnEwNXV3M3BsaHdqaG0yOG5vIn0.nphFmNshYXzqJDdb_SoGnw';
    
    mapboxgl.accessToken = mapboxToken;
    
    // Check theme
    const isDark = document.documentElement.classList.contains('dark');
    const mapStyle = isDark ? 'mapbox://styles/mapbox/dark-v10' : 'mapbox://styles/mapbox/outdoors-v12';
    
    map = new mapboxgl.Map({
        container: 'map',
        style: mapStyle,
        center: [10.4513, 55.7132], // Denmark coordinates
        zoom: 7,
        pitch: 30, // Default 3D perspective
    });
    
    // Store map globally for external functions like showOnMap
    window.mapboxMap = map;
    
    // Add navigation controls with custom styling
    const nav = new mapboxgl.NavigationControl({
        showCompass: true,
        visualizePitch: true
    });
    map.addControl(nav, 'bottom-right');
    
    // Setup custom controls
    setupCustomControls();
    
    // Add terrain and sky layer when map loads
    map.on('load', function() {
        // Add 3D terrain
        map.addSource('mapbox-dem', {
            'type': 'raster-dem',
            'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
            'tileSize': 512,
            'maxzoom': 14
        });
        
        map.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 1.5 });
        
        // Add sky layer
        map.addLayer({
            'id': 'sky',
            'type': 'sky',
            'paint': {
                'sky-type': 'atmosphere',
                'sky-atmosphere-sun': [0.0, 0.0],
                'sky-atmosphere-sun-intensity': 15
            }
        });
        
        // Fetch roads data from API
        fetchRoadsMapbox();
        
        // Check URL for highlighted road
        const urlParams = new URLSearchParams(window.location.search);
        const highlightId = urlParams.get('highlight');
        if (highlightId) {
            // Slight delay to ensure data is loaded
            setTimeout(() => {
                showOnMap(highlightId);
            }, 1000);
        }
    });
    
    // Setup filter form
    setupFilters();
}

// Function to setup custom map controls for Mapbox
function setupCustomControls() {
    // Zoom controls
    document.getElementById('zoom-in')?.addEventListener('click', function() {
        map.zoomIn();
    });
    
    document.getElementById('zoom-out')?.addEventListener('click', function() {
        map.zoomOut();
    });
    
    // Location control
    document.getElementById('locate-me')?.addEventListener('click', function() {
        // Get user location and center map
        navigator.geolocation.getCurrentPosition(function(position) {
            map.flyTo({
                center: [position.coords.longitude, position.coords.latitude],
                zoom: 14,
                essential: true
            });
            
            // Add marker at user location
            new mapboxgl.Marker({ color: '#3b82f6' })
                .setLngLat([position.coords.longitude, position.coords.latitude])
                .addTo(map);
        }, function(error) {
            console.error('Error getting location:', error);
            alert('Unable to get your location. Please check your location permissions.');
        });
    });
    
    // 3D terrain toggle
    const terrainToggle = document.getElementById('toggle-3d');
    if (terrainToggle) {
        terrainToggle.addEventListener('click', function() {
            const isEnabled = terrainToggle.classList.contains('bg-blue-100');
            
            if (isEnabled) {
                map.setTerrain(null);
                terrainToggle.classList.replace('bg-blue-100', 'bg-gray-100');
                terrainToggle.classList.replace('text-blue-700', 'text-gray-700');
            } else {
                map.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 1.5 });
                terrainToggle.classList.replace('bg-gray-100', 'bg-blue-100');
                terrainToggle.classList.replace('text-gray-700', 'text-blue-700');
            }
        });
    }
    
    // Heatmap toggle
    const heatmapToggle = document.getElementById('toggle-heatmap');
    if (heatmapToggle) {
        heatmapToggle.addEventListener('click', function() {
            if (!map.getLayer('gradient-heatmap')) return;
            
            const isEnabled = heatmapToggle.classList.contains('bg-blue-100');
            
            if (isEnabled) {
                map.setLayoutProperty('gradient-heatmap', 'visibility', 'none');
                heatmapToggle.classList.replace('bg-blue-100', 'bg-gray-100');
                heatmapToggle.classList.replace('text-blue-700', 'text-gray-700');
            } else {
                map.setLayoutProperty('gradient-heatmap', 'visibility', 'visible');
                heatmapToggle.classList.replace('bg-gray-100', 'bg-blue-100');
                heatmapToggle.classList.replace('text-gray-700', 'text-blue-700');
            }
        });
    }
}

// Function to setup filters for Mapbox
function setupFilters() {
    const filterForm = document.getElementById('filter-form');
    if (!filterForm) return;
    
    filterForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        
        // Get filter values
        const filters = {
            min_gradient: formData.get('min_gradient'),
            max_gradient: formData.get('max_gradient'),
            min_length: formData.get('min_length'),
            max_length: formData.get('max_length'),
            road_type: formData.get('road_type')
        };
        
        // Apply filters to map
        applyFilters(filters);
    });
    
    // Handle road details close button
    const closeDetailsBtn = document.getElementById('close-details');
    if (closeDetailsBtn) {
        closeDetailsBtn.addEventListener('click', function() {
            document.getElementById('selected-road-info').classList.add('hidden');
        });
    }
}

// Function to fetch roads data for Mapbox
function fetchRoadsMapbox() {
    fetch('/api/roads')
        .then(response => response.json())
        .then(data => {
            // Handle both API response formats (supports both old and new API structure)
            const roads = data.roads || (data.status === 'success' ? data.data : []);
            addRoadsToMapbox(roads);
        })
        .catch(error => {
            console.error('Error fetching roads:', error);
        });
}

// Function to add roads data to Mapbox
function addRoadsToMapbox(roads) {
    // Create a GeoJSON source for roads
    const geojsonData = {
        type: 'FeatureCollection',
        features: roads.map(road => {
            // Support both coordinate formats
            let coordinates = road.coordinates;
            if (!coordinates && road.geometry) {
                coordinates = road.geometry.coordinates || road.geometry;
            }
            
            return {
                type: 'Feature',
                properties: {
                    id: road.id,
                    name: road.name || 'Unnamed Road',
                    gradient: road.gradient,
                    length: road.length_meters / 1000,
                    min_elevation: road.min_elevation,
                    max_elevation: road.max_elevation,
                    highway: road.highway,
                    maxspeed: road.maxspeed
                },
                geometry: {
                    type: 'LineString',
                    coordinates: coordinates
                }
            };
        })
    };
    
    // Add source to map
    map.addSource('roads', {
        type: 'geojson',
        data: geojsonData
    });
    
    // Add road lines layer
    map.addLayer({
        id: 'road-lines',
        type: 'line',
        source: 'roads',
        layout: {
            'line-join': 'round',
            'line-cap': 'round'
        },
        paint: {
            'line-width': [
                'interpolate', ['linear'], ['zoom'],
                8, 1,
                12, 3,
                16, 5
            ],
            'line-color': [
                'interpolate', ['linear'], ['get', 'gradient'],
                0, '#3b82f6', // Blue for flat
                5, '#fbbf24', // Yellow for medium gradient
                10, '#ef4444'  // Red for steep gradient
            ],
            'line-opacity': 0.8
        }
    });
    
    // Add gradient heatmap layer
    map.addLayer({
        id: 'gradient-heatmap',
        type: 'heatmap',
        source: 'roads',
        maxzoom: 15,
        paint: {
            'heatmap-weight': [
                'interpolate', ['linear'], ['get', 'gradient'],
                0, 0,
                5, 0.5,
                10, 1
            ],
            'heatmap-intensity': [
                'interpolate', ['linear'], ['zoom'],
                8, 0.5,
                12, 1
            ],
            'heatmap-color': [
                'interpolate', ['linear'], ['heatmap-density'],
                0, 'rgba(0, 0, 255, 0)',
                0.2, 'rgb(0, 255, 255)',
                0.4, 'rgb(0, 255, 0)',
                0.6, 'rgb(255, 255, 0)',
                0.8, 'rgb(255, 0, 0)'
            ],
            'heatmap-radius': [
                'interpolate', ['linear'], ['zoom'],
                8, 8,
                12, 15
            ],
            'heatmap-opacity': 0.6
        }
    });
    
    // Add click event to show road details
    map.on('click', 'road-lines', function(e) {
        if (e.features.length > 0) {
            const feature = e.features[0];
            const properties = feature.properties;
            
            // Get road details and center map on road
            showRoadDetailsMapbox(properties.id);
            
            // Fly to road location
            const coordinates = feature.geometry.coordinates;
            const bounds = coordinates.reduce(function(bounds, coord) {
                return bounds.extend(coord);
            }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));
            
            map.fitBounds(bounds, {
                padding: { top: 50, bottom: 50, left: 300, right: 50 },
                duration: 1000
            });
        }
    });
    
    // Change cursor on hover
    map.on('mouseenter', 'road-lines', function() {
        map.getCanvas().style.cursor = 'pointer';
    });
    
    map.on('mouseleave', 'road-lines', function() {
        map.getCanvas().style.cursor = '';
    });
}

// Function to apply filters to Mapbox
function applyFilters(filters) {
    // Create filter expressions for Mapbox
    let filterExpressions = ['all'];
    
    // Gradient filters
    if (filters.min_gradient) {
        filterExpressions.push(['>=', ['get', 'gradient'], parseFloat(filters.min_gradient)]);
    }
    
    if (filters.max_gradient) {
        filterExpressions.push(['<=', ['get', 'gradient'], parseFloat(filters.max_gradient)]);
    }
    
    // Length filters
    if (filters.min_length) {
        filterExpressions.push(['>=', ['get', 'length'], parseFloat(filters.min_length)]);
    }
    
    if (filters.max_length) {
        filterExpressions.push(['<=', ['get', 'length'], parseFloat(filters.max_length)]);
    }
    
    // Road type filter
    if (filters.road_type) {
        filterExpressions.push(['==', ['get', 'highway'], filters.road_type]);
    }
    
    // Apply filters to map layers
    map.setFilter('road-lines', filterExpressions);
    map.setFilter('gradient-heatmap', filterExpressions);
}

// Function to show road details for Mapbox
function showRoadDetailsMapbox(roadId) {
    fetch(`/api/roads/${roadId}`)
        .then(response => response.json())
        .then(data => {
            // Handle both API formats
            const road = data.status === 'success' ? data.data : data;
            
            // Update road details panel
            const roadDetailsEl = document.getElementById('road-details');
            if (!roadDetailsEl) return;
            
            roadDetailsEl.innerHTML = `
                <div class="space-y-3">
                    <h3 class="text-xl font-bold text-theme-primary">${road.name || 'Unnamed Road'}</h3>
                    <div class="flex items-center">
                        <span class="text-sm py-1 px-2 rounded-full ${road.gradient > 8 ? 'bg-red-100 text-red-800' : road.gradient > 5 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}">
                            ${road.gradient.toFixed(1)}% Gradient
                        </span>
                    </div>
                    <div class="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <p class="text-theme-secondary">Length</p>
                            <p class="font-medium text-theme-primary">${(road.length_meters/1000).toFixed(2)} km</p>
                        </div>
                        <div>
                            <p class="text-theme-secondary">Elevation Gain</p>
                            <p class="font-medium text-theme-primary">${(road.max_elevation - road.min_elevation).toFixed(1)} m</p>
                        </div>
                        <div>
                            <p class="text-theme-secondary">Min Elevation</p>
                            <p class="font-medium text-theme-primary">${road.min_elevation.toFixed(1)} m</p>
                        </div>
                        <div>
                            <p class="text-theme-secondary">Max Elevation</p>
                            <p class="font-medium text-theme-primary">${road.max_elevation.toFixed(1)} m</p>
                        </div>
                    </div>
                </div>
            `;
            
            // Create elevation profile chart if data is available
            if (road.elevation_profile) {
                createElevationChart(road.elevation_profile);
            }
            
            // Show road details panel
            document.getElementById('selected-road-info').classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error fetching road details:', error);
        });
}

// Function to create elevation chart with Chart.js
function createElevationChart(elevationData) {
    const elevationEl = document.getElementById('elevation-profile');
    if (!elevationEl) return;
    
    const ctx = elevationEl.getContext('2d');
    if (!ctx) return;
    
    // Convert data for chart
    const labels = elevationData.map((_, index) => index);
    const data = elevationData.map(point => point.elevation);
    
    // Create gradient for chart
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.8)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.1)');
    
    // Check if chart already exists
    if (window.elevationChart) {
        window.elevationChart.destroy();
    }
    
    // Create chart
    window.elevationChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Elevation (m)',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: gradient,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    display: false,
                    grid: {
                        color: document.documentElement.classList.contains('dark') ? 
                               'rgba(100, 116, 139, 0.2)' : 'rgba(200, 200, 200, 0.2)'
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: document.documentElement.classList.contains('dark') ? 
                               'rgba(100, 116, 139, 0.2)' : 'rgba(200, 200, 200, 0.2)'
                    },
                    ticks: {
                        color: document.documentElement.classList.contains('dark') ? 
                              '#94a3b8' : '#64748b'
                    }
                }
            }
        }
    });
}

// Function to initialize Leaflet map (fallback)
function initializeLeaflet() {
    console.log('Using Leaflet fallback for mapping');
    
    // Initialize the map
    map = L.map('map', {
        zoomControl: false,  // Disable default zoom controls
        dragging: true,
        scrollWheelZoom: true
    });
    
    // Set view to Denmark center
    map.setView([56.2639, 9.5018], 7);
    
    // Add a base map
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Load roads
    fetch('/api/roads')
        .then(response => response.json())
        .then(data => {
            // Handle both API formats
            const roads = data.roads || (data.status === 'success' ? data.data : []);
            
            // Add roads to map
            roads.forEach(road => {
                const color = getGradientColor(road.gradient);
                
                // Handle different geometry formats
                let geometry = road.geometry;
                if (!geometry && road.coordinates) {
                    geometry = {
                        type: 'LineString',
                        coordinates: road.coordinates
                    };
                }
                
                const roadLayer = L.geoJSON(geometry, {
                    style: {
                        color: color,
                        weight: 3,
                        opacity: 0.7
                    }
                }).addTo(map);

                roadLayer.on('click', () => showRoadDetails(road));
                roadLayers[road.id] = roadLayer;
            });
        })
        .catch(error => {
            console.error('Error fetching roads:', error);
        });
    
    // Handle filter form submission
    document.getElementById('filter-form')?.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const params = new URLSearchParams(formData);
        
        fetch(`/api/roads?${params}`)
            .then(response => response.json())
            .then(data => {
                // Handle both API formats
                const roads = data.roads || (data.status === 'success' ? data.data : []);
                updateLeafletMap(roads);
            })
            .catch(error => {
                console.error('Error applying filters:', error);
            });
    });
}

// Function to update Leaflet map (used after filtering)
function updateLeafletMap(roads) {
    // Clear existing layers
    Object.values(roadLayers).forEach(layer => map.removeLayer(layer));
    roadLayers = {};
    
    // Add filtered roads
    roads.forEach(road => {
        const color = getGradientColor(road.gradient);
        const roadLayer = L.geoJSON(road.geometry, {
            style: {
                color: color,
                weight: 3,
                opacity: 0.7
            }
        }).addTo(map);

        roadLayer.on('click', () => showRoadDetails(road));
        roadLayers[road.id] = roadLayer;
    });
}

// Function to calculate gradient color (used by both map implementations)
function getGradientColor(gradient) {
    if (gradient > 8) return '#ef4444';  // Red for steep gradients
    if (gradient > 5) return '#f59e0b';  // Orange for medium gradients
    return '#22c55e';  // Green for gentle gradients
}

// Function to show road details in sidebar (used by Leaflet)
function showRoadDetails(road) {
    const detailsDiv = document.getElementById('selected-road-info');
    const detailsContent = document.getElementById('road-details');
    
    if (!detailsDiv || !detailsContent) return;
    
    detailsDiv.classList.remove('hidden');
    detailsContent.innerHTML = `
        <div class="space-y-3">
            <h3 class="text-xl font-bold text-theme-primary">${road.name || 'Unnamed Road'}</h3>
            <div class="flex items-center">
                <span class="text-sm py-1 px-2 rounded-full ${road.gradient > 8 ? 'bg-red-100 text-red-800' : road.gradient > 5 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}">
                    ${road.gradient.toFixed(1)}% Gradient
                </span>
            </div>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <p class="text-theme-secondary">Length</p>
                    <p class="font-medium text-theme-primary">${(road.length_meters/1000).toFixed(2)} km</p>
                </div>
                <div>
                    <p class="text-theme-secondary">Elevation Gain</p>
                    <p class="font-medium text-theme-primary">${(road.max_elevation - road.min_elevation).toFixed(1)} m</p>
                </div>
                <div>
                    <p class="text-theme-secondary">Min Elevation</p>
                    <p class="font-medium text-theme-primary">${road.min_elevation.toFixed(1)} m</p>
                </div>
                <div>
                    <p class="text-theme-secondary">Max Elevation</p>
                    <p class="font-medium text-theme-primary">${road.max_elevation.toFixed(1)} m</p>
                </div>
            </div>
        </div>
    `;
    
    // Add elevation profile button if showProfile function exists
    if (typeof showProfile === 'function') {
        detailsContent.innerHTML += `
            <button 
                onclick="showProfile(${road.id})"
                class="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                View Elevation Profile
            </button>
        `;
    }
}

// Function to show elevation profile (compatible with old code)
function showProfile(roadId) {
    fetch(`/api/roads/${roadId}/profile`)
        .then(response => response.json())
        .then(data => {
            // Handle both API formats
            const profile = data.status === 'success' ? data.data : data;
            
            // Implementation for showing profile chart
            console.log('Show profile chart', profile);
            
            // If we have the new elevation-profile element, use Chart.js
            const elevationEl = document.getElementById('elevation-profile');
            if (elevationEl && profile.elevation_profile) {
                createElevationChart(profile.elevation_profile);
            }
        })
        .catch(error => {
            console.error('Error fetching elevation profile:', error);
        });
}

// Global function to show a road on the map (works with both Mapbox and Leaflet)
window.showOnMap = function(roadId) {
    // Redirect to map page if not already there
    if (!document.getElementById('map')) {
        window.location.href = `/map?highlight=${roadId}`;
        return;
    }
    
    // For Mapbox
    if (typeof mapboxgl !== 'undefined' && window.mapboxMap) {
        // Fetch road data
        fetch(`/api/roads/${roadId}`)
            .then(response => response.json())
            .then(data => {
                // Handle both API formats
                const road = data.status === 'success' ? data.data : data;
                
                // Show road details
                showRoadDetailsMapbox(roadId);
                
                // Get coordinates
                let coordinates = road.coordinates;
                if (!coordinates && road.geometry) {
                    coordinates = road.geometry.coordinates || road.geometry;
                }
                
                // Fly to road location
                const bounds = coordinates.reduce(function(bounds, coord) {
                    return bounds.extend(coord);
                }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));
                
                window.mapboxMap.fitBounds(bounds, {
                    padding: { top: 50, bottom: 50, left: 300, right: 50 },
                    duration: 1000
                });
                
                // Add a highlight to the road
                window.mapboxMap.setPaintProperty('road-lines', 'line-width', [
                    'match',
                    ['get', 'id'],
                    roadId,
                    6, // Highlighted width
                    ['interpolate', ['linear'], ['zoom'],
                        8, 1,
                        12, 3,
                        16, 5
                    ] // Default width
                ]);
            })
            .catch(error => {
                console.error('Error fetching road details:', error);
            });
    }
    // For Leaflet
    else if (roadLayers[roadId]) {
        map.fitBounds(roadLayers[roadId].getBounds());
        
        // Highlight the road
        roadLayers[roadId].setStyle({
            weight: 5,
            opacity: 1
        });
        
        // Reset after a delay
        setTimeout(() => {
            roadLayers[roadId].setStyle({
                weight: 3,
                opacity: 0.7
            });
        }, 2000);
        
        // Show road details
        fetch(`/api/roads/${roadId}`)
            .then(response => response.json())
            .then(data => {
                // Handle both API formats
                const road = data.status === 'success' ? data.data : data;
                showRoadDetails(road);
            })
            .catch(error => {
                console.error('Error fetching road details:', error);
            });
    }
};

// Setup hills filtering functionality
function setupHillsFiltering() {
    const filterButtons = document.querySelectorAll('[data-filter]');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active state from all buttons
            filterButtons.forEach(btn => {
                btn.classList.remove('bg-blue-500', 'text-white');
                btn.classList.add('bg-gray-200', 'text-gray-700');
            });
            
            // Add active state to clicked button
            this.classList.remove('bg-gray-200', 'text-gray-700');
            this.classList.add('bg-blue-500', 'text-white');
            
            // Get filter type and fetch data
            const filterType = this.dataset.filter;
            fetchTopHills(filterType);
        });
    });
}

// Function to fetch top hills data
function fetchTopHills(filterType) {
    fetch(`/api/top-hills?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            // Handle both API formats
            const hills = data.hills || (data.status === 'success' ? data.data : []);
            updateTopHillsTable(hills);
        })
        .catch(error => {
            console.error('Error fetching top hills:', error);
        });
}

// Function to update top hills table
function updateTopHillsTable(hills) {
    const tbody = document.querySelector('table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    hills.forEach((hill, index) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50 transition-colors';
        
        tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-theme-primary">${index + 1}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-theme-primary">${hill.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-theme-primary text-right">${hill.length} km</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-theme-primary text-right">${hill.height} m</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-theme-primary text-right">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${hill.gradient > 8 ? 'bg-red-100 text-red-800' : hill.gradient > 5 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}">
                    ${hill.gradient}%
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-center">
                <button 
                    onclick="showOnMap(${hill.id})" 
                    class="text-blue-600 hover:text-blue-900 font-medium"
                >
                    Show on Map
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}