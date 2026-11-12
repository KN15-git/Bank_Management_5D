"""Entry point for running the Flask Bank REST API server."""
import os
from app import create_app, init_db

app = create_app()

with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Bank API server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
