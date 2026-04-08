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

// Universal date parser — handles both SQLite strings and PostgreSQL ISO strings
window.parseDate = function(dateStr) {
    if (!dateStr) return new Date(NaN);
    // If it already has a 'Z' or timezone offset, parse directly
    if (dateStr.endsWith('Z') || dateStr.match(/[+-]\d{2}:\d{2}$/)) {
        return new Date(dateStr);
    }
    // If it has the ISO 'T' separator, append Z for UTC
    if (dateStr.includes('T')) {
        return new Date(dateStr + 'Z');
    }
    // Old SQLite format: "2024-04-08 12:00:00" — replace space with T and append Z
    return new Date(dateStr.replace(' ', 'T') + 'Z');
};
