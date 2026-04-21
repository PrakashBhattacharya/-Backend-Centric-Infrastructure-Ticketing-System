import sys
import os

# Link to the bundled 'app' package inside the 'api/' directory
# On Vercel, the 'api' folder is part of the sys.path, so 'from app' works.
try:
    from app import create_app
    # We do NOT import init_db at the top level to avoid cold-start timeouts
except ImportError:
    # If standard import fails, try relative fallback
    sys.path.insert(0, os.path.dirname(__file__))
    from app import create_app

# Vercel's required 'app' export
# We create the app instance WITHOUT performing any database operations.
app = create_app()

@app.route('/api/diag')
def diag():
    """Diagnostic route that verifies path resolution."""
    return {
        "status": "Diagnostic Active",
        "cwd": os.getcwd(),
        "files_in_api": os.listdir(os.path.dirname(__file__)),
        "app_folder_exists": os.path.exists(os.path.join(os.path.dirname(__file__), 'app'))
    }

if __name__ == "__main__":
    app.run()
