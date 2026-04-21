from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/test_native')
def test():
    return jsonify({"status": "Native Vercel API Active"})

if __name__ == "__main__":
    app.run()
