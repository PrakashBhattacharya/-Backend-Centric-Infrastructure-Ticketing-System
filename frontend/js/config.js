// Centralized Configuration for the InfraTick Frontend
const CONFIG = {
    // If the frontend is served by the Flask app, we can use a relative path.
    // Otherwise, specify the full URL here.
    API_BASE: window.location.origin.includes('127.0.0.1:5500') || window.location.origin.includes('localhost:3000')
        ? 'http://127.0.0.1:5000' 
        : window.location.origin
};

// Make it available globally
window.API_BASE = CONFIG.API_BASE;
console.log("[Config] API Base set to:", window.API_BASE);
