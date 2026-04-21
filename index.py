from flask import Flask, jsonify
import os
import sys

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def debug(path):
    # List all files and directories in the current working directory
    files_info = {}
    for root, dirs, files in os.walk('.'):
        # Limit depth to 2 to avoid too much text
        depth = root.count(os.sep)
        if depth <= 2:
            files_info[root] = {"dirs": dirs, "files": files}
    
    return jsonify({
        "status": "Diagnostic File Check",
        "cwd": os.getcwd(),
        "python_path": sys.path,
        "structure": files_info,
        "env": {k: v for k, v in os.environ.items() if "URL" not in k and "PASS" not in k} # Safe env check
    })

if __name__ == "__main__":
    app.run()
