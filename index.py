from flask import Flask, jsonify
import sys

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return jsonify({
        "status": "Pure Root Backend Active",
        "python": sys.version,
        "path_accessed": path
    })

if __name__ == "__main__":
    app.run()
