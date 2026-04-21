from flask import Flask, jsonify
import sys

# Test if psycopg2 can actually be imported on this Vercel instance
try:
    import psycopg2
    import psycopg2.extras
    psycopg_status = "Successfully Imported"
except Exception as e:
    psycopg_status = f"FAILED: {str(e)}"

app = Flask(__name__)

@app.route('/')
@app.route('/api/status')
def test():
    return jsonify({
        "status": "Diagnostic Active",
        "psycopg2": psycopg_status,
        "python": sys.version
    })

if __name__ == "__main__":
    app.run()
