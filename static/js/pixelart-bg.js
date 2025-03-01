// pixelart-bg.js - Animated pixel art background

// Canvas setup
let pixelCanvas, pixelCtx;
let canvasWidth, canvasHeight;
let pixelSize = 8;  // Size of each "pixel" (actually small blocks)
let isDarkMode = false;

// Mountain parameters
let mountainLayers = [];
let clouds = [];
let stars = [];
let lastFrameTime = 0;
const FPS = 24;
const frameTime = 1000 / FPS;

// Colors
const lightColors = {
    sky: '#3498db',
    mountains: ['#2ecc71', '#27ae60', '#1e8449', '#196f3d'],
    clouds: '#ecf0f1',
    cloudShadow: '#bdc3c7'
};

const darkColors = {
    sky: '#1a2639',
    mountains: ['#34495e', '#2c3e50', '#212f3d', '#17202a'],
    clouds: '#34495e',
    cloudShadow: '#2c3e50',
    stars: '#ecf0f1'
};

// Initialize the background
function initPixelBackground() {
    pixelCanvas = document.getElementById('pixel-canvas');
    if (!pixelCanvas) return;
    
    pixelCtx = pixelCanvas.getContext('2d');
    
    // Resize canvas to fill window
    resizeCanvas();
    
    // Check current theme
    isDarkMode = document.documentElement.classList.contains('dark');
    
    // Initialize mountains
    initMountains();
    
    // Initialize clouds
    initClouds();
    
    // Initialize stars (for dark mode)
    initStars();
    
    // Start animation loop
    requestAnimationFrame(animateBackground);
    
    // Listen for theme changes
    document.getElementById('theme-toggle')?.addEventListener('click', function() {
        isDarkMode = document.documentElement.classList.contains('dark');
    });
    
    // Listen for window resize
    window.addEventListener('resize', resizeCanvas);
}

// Resize canvas
function resizeCanvas() {
    canvasWidth = window.innerWidth;
    canvasHeight = window.innerHeight;
    
    pixelCanvas.width = canvasWidth;
    pixelCanvas.height = canvasHeight;
    
    // Reinitialize elements for new size
    if (mountainLayers.length > 0) {
        initMountains();
        initClouds();
        initStars();
    }
}

// Initialize mountain layers
function initMountains() {
    mountainLayers = [];
    
    // Create 4 layers of mountains with different heights and speeds
    for (let i = 0; i < 4; i++) {
        const segmentCount = Math.floor(canvasWidth / (pixelSize * 4)) + 1;
        let points = [];
        
        // Starting height is higher for background mountains
        const startHeight = canvasHeight - (canvasHeight * 0.15) - (i * canvasHeight * 0.07);
        
        // Generate mountain points
        for (let j = 0; j < segmentCount; j++) {
            // First and last points are at base height
            if (j === 0 || j === segmentCount - 1) {
                points.push(startHeight);
            } else {
                // Random height with constraints to create mountain shape
                const randomHeight = startHeight - Math.random() * (canvasHeight * 0.15) * (1 - i * 0.2);
                points.push(randomHeight);
            }
        }
        
        // Smooth the mountain profile
        points = smoothArray(points, 3);
        
        mountainLayers.push({
            points: points,
            speed: 0.1 * (4 - i), // Background mountains move slower
            position: 0,
            color: i
        });
    }
}

// Initialize clouds
function initClouds() {
    clouds = [];
    const cloudCount = Math.floor(canvasWidth / 400) + 2;
    
    for (let i = 0; i < cloudCount; i++) {
        clouds.push({
            x: Math.random() * canvasWidth,
            y: Math.random() * (canvasHeight * 0.4),
            width: 100 + Math.random() * 150,
            height: 30 + Math.random() * 30,
            speed: 0.2 + Math.random() * 0.3
        });
    }
}

// Initialize stars (visible in dark mode)
function initStars() {
    stars = [];
    const starCount = Math.floor((canvasWidth * canvasHeight) / 10000);
    
    for (let i = 0; i < starCount; i++) {
        stars.push({
            x: Math.random() * canvasWidth,
            y: Math.random() * (canvasHeight * 0.6),
            size: 1 + Math.floor(Math.random() * 2),
            twinkle: Math.random() * 2 * Math.PI
        });
    }
}

// Animation loop
function animateBackground(timestamp) {
    // Limit frame rate
    if (timestamp - lastFrameTime < frameTime) {
        requestAnimationFrame(animateBackground);
        return;
    }
    lastFrameTime = timestamp;
    
    // Clear canvas
    pixelCtx.clearRect(0, 0, canvasWidth, canvasHeight);
    
    // Choose color palette based on theme
    const colors = isDarkMode ? darkColors : lightColors;
    
    // Draw sky background (handled by CSS)
    
    // Draw stars in dark mode
    if (isDarkMode) {
        drawStars(colors);
    }
    
    // Draw clouds
    drawClouds(colors);
    
    // Draw mountain layers
    drawMountains(colors);
    
    // Update positions
    updatePositions();
    
    // Continue animation loop
    requestAnimationFrame(animateBackground);
}

// Draw mountains
function drawMountains(colors) {
    mountainLayers.forEach((layer, index) => {
        pixelCtx.fillStyle = colors.mountains[layer.color];
        
        // Draw mountain shape
        pixelCtx.beginPath();
        pixelCtx.moveTo(0, canvasHeight);
        
        const segmentWidth = pixelSize * 4;
        const points = layer.points;
        
        for (let i = 0; i < points.length; i++) {
            const x = (i * segmentWidth + layer.position) % (canvasWidth + segmentWidth) - segmentWidth;
            
            // Draw in "pixels"
            const pixelX = Math.floor(x / pixelSize) * pixelSize;
            const pixelY = Math.floor(points[i] / pixelSize) * pixelSize;
            
            pixelCtx.lineTo(pixelX, pixelY);
        }
        
        // Complete mountain shape
        pixelCtx.lineTo(canvasWidth, canvasHeight);
        pixelCtx.closePath();
        pixelCtx.fill();
    });
}

// Draw clouds
function drawClouds(colors) {
    clouds.forEach(cloud => {
        // Draw cloud shadow
        pixelCtx.fillStyle = colors.cloudShadow;
        drawPixelatedEllipse(cloud.x + 5, cloud.y + 5, cloud.width, cloud.height);
        
        // Draw cloud
        pixelCtx.fillStyle = colors.clouds;
        drawPixelatedEllipse(cloud.x, cloud.y, cloud.width, cloud.height);
    });
}

// Draw stars
function drawStars(colors) {
    pixelCtx.fillStyle = colors.stars;
    
    stars.forEach(star => {
        // Apply twinkle effect
        const opacity = (Math.sin(star.twinkle + lastFrameTime * 0.001) + 1) / 2 * 0.5 + 0.5;
        pixelCtx.globalAlpha = opacity;
        
        const pixelX = Math.floor(star.x / pixelSize) * pixelSize;
        const pixelY = Math.floor(star.y / pixelSize) * pixelSize;
        
        pixelCtx.fillRect(pixelX, pixelY, star.size, star.size);
    });
    
    pixelCtx.globalAlpha = 1.0;
}

// Draw pixelated ellipse
function drawPixelatedEllipse(x, y, width, height) {
    for (let py = y - height; py < y + height; py += pixelSize) {
        for (let px = x - width; px < x + width; px += pixelSize) {
            // Test if point is inside ellipse
            const dx = (px - x) / width;
            const dy = (py - y) / height;
            const dist = dx * dx + dy * dy;
            
            if (dist <= 1.0) {
                pixelCtx.fillRect(px, py, pixelSize, pixelSize);
            }
        }
    }
}

// Update positions of animated elements
function updatePositions() {
    // Move mountains
    mountainLayers.forEach(layer => {
        layer.position -= layer.speed;
        
        // Reset position for seamless scrolling
        if (layer.position <= -pixelSize * 4) {
            layer.position = 0;
        }
    });
    
    // Move clouds
    clouds.forEach(cloud => {
        cloud.x -= cloud.speed;
        
        // Reset cloud position when it moves off-screen
        if (cloud.x + cloud.width < -100) {
            cloud.x = canvasWidth + 100;
            cloud.y = Math.random() * (canvasHeight * 0.4);
        }
    });
    
    // Update star twinkle
    stars.forEach(star => {
        star.twinkle += 0.03;
    });
}

// Helper: Smooth an array of values
function smoothArray(arr, passes = 1) {
    let result = [...arr];
    
    for (let p = 0; p < passes; p++) {
        let smoothed = [...result];
        
        for (let i = 1; i < arr.length - 1; i++) {
            smoothed[i] = (result[i-1] + result[i] + result[i+1]) / 3;
        }
        
        result = smoothed;
    }
    
    return result;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initPixelBackground);