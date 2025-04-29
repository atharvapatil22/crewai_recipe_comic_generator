from flask import Flask, request, jsonify
from flask_cors import CORS
from src.crewai_recipe_comic_generator.main import run
from src.crewai_recipe_comic_generator.helpers import image_to_base64
import PIL
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# API Route for testing connection
@app.route('/test-connection', methods=['GET'])
def test_connection():
  return jsonify({"message": "Server is up and running!"}), 200

# API Route to trigger CrewAI
@app.route('/run-crew', methods=['POST'])
def run_crew():

  print("[FLASK] hit run-crew route 🚀☑️")
  try:
    data = request.json
    input_text = data.get("input_text", "")

    if not input_text:
      return jsonify({"message": "Missing input_text param"}), 400
    
    crewai_output = run(input_text=input_text)
    print("[FLASK] got crewai output 🚀☑️")
    
    # if crewai_response == "LIMIT_EXCEEDED":
    #   return jsonify({"message": "Ingredient Limit exceeded"}), 400
    if isinstance(crewai_output, list) and all(isinstance(item, PIL.Image.Image) for item in crewai_output):
      poster = [image_to_base64(page) for page in crewai_output]
      print("[FLASK] ready to send response 🚀☑️")
      return jsonify({"message": "API SUCCESS","res":poster}), 200
      
  except Exception as e:
      return jsonify({"message":"[Application Exception] Some internal error occured!","error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # 5000 as fallback for local dev

    # LOCAL:
    app.run(debug=True)

    # PRODUCTION: 
    # app.run(host="0.0.0.0", port=port)