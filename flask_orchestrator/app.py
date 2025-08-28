
from dotenv import load_dotenv
import os
# Explicitly load .env from repo root
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path)
from flask import Flask
from routes import routes

app = Flask(__name__)
app.register_blueprint(routes)

if __name__ == "__main__":
  port = int(os.environ.get("FLASK_PORT", 5000)) 

  # LOCAL:
  # app.run(debug=True)

  # PRODUCTION: 
  app.run(host="0.0.0.0", port=port)