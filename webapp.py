"""Point d'entrée — lancer avec : python webapp.py"""
import os
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from app import create_app

app = create_app()

if __name__ == "__main__":
    init_db()
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"🚀 Learning Streak Builder Web - http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
