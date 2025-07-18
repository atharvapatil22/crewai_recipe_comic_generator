from flask import Flask, request, jsonify
from flask_cors import CORS
import PIL
import os
from openai import OpenAI

from src.crewai_recipe_comic_generator.main import run
from src.crewai_recipe_comic_generator.helpers import image_to_base64

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

  data = request.json
  input_text = data.get("input_text", "")

  if not input_text:
    return jsonify({"message": "Missing input_text param"}), 400

  try:    
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
  
@app.route('/generate-recipe', methods=['POST'])
def generate_recipe():
  print("[FLASK] hit generate-recipe route 🚀☑️")

  data = request.json
  dish_name = data.get("dish_name", "")

  if not dish_name:
    return jsonify({"message": "Missing dish_name param"}), 400
  
  client = OpenAI()
  prompt = prompt = f"""
  Generate a recipe for {dish_name}

  Your generated text should contain Recipe name,Ingredients,Instructions

  Ingredients should be a list in this format:
  Name – quantity
  Example: Bread – 2 slices, Butter – 1 tbsp

  Then there should be a numbered list of instructions. Each numbered point should be one logical step and must contain only one sentence.

  Notes:
  - An ingredient name should not have options. For example, do not give an ingredient as "Chicken or Beef". In such cases, just make the choice yourself.
  - If an entire ingredient is optional to the dish, skip it altogether. For example, "Cilantro - 2 tbsp (optional)" should be skipped altogether.
  """
  try:
    response = client.chat.completions.create(
      model="gpt-4.1-mini",  
      messages=[
          {"role": "system", "content": "You are a helpful and expert chef."},
          {"role": "user", "content": prompt}
      ],
      max_tokens=800,
      temperature=0.6,
    )

    recipe_text = response.choices[0].message.content

    return jsonify({"recipe": recipe_text})

  except Exception as e:
    return jsonify({"message":"[Application Exception] Failed to generate recipe!","error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # 5000 as fallback for local dev

    # LOCAL:
    # app.run(debug=True)

    # PRODUCTION: 
    app.run(host="0.0.0.0", port=port)