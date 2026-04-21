from flask import Flask, jsonify
import sys
import os

app = Flask(__name__)

@app.route('/api/test')
def test():
    return jsonify({
        "status": "Diagnostic Backend Active",
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "files": os.listdir('.')
    })

if __name__ == "__main__":
    app.run()
