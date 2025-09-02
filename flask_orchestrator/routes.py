from flask import Blueprint, request, jsonify
import sys
import os
from openai import OpenAI
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import WORKLOAD_STATUSES
from shared.supabase_client import supabase
from shared.redis_client import preprocess_queue,comicgen_queue


routes = Blueprint("routes", __name__)

@routes.route('/test-connection', methods=['GET'])
def test_connection():
  return jsonify({"message": "Server is up and running!"}), 200

@routes.route("/workloads", methods=["POST"])
def create_workload():
  data = request.json
  input_text = data.get("input_text")
  if not input_text:
    return jsonify({"message": "Missing input_text param"}), 400

  try:
    # Insert into workloads table
    db_response = (
      supabase.table("workloads")
      .insert({
        "prompt": input_text,
        "status": WORKLOAD_STATUSES['starting_workload']
      })
      .execute()
    )
    print("[FLASK] Inserted new workload into DB ✅")
    workload_internal_id = db_response.data[0]["id"]
    workload_public_id = db_response.data[0]["public_id"]

    # Enqueue preprocess task
    preprocess_queue.enqueue(
      "preprocess_worker.preprocess_task", 
      workload_internal_id,
      input_text,
      result_ttl=86400 #24hrs
    )
    print("[FLASK] Added new task into preprocess queue ✅")

  except Exception as e:
    return jsonify({
      "message": "Failed to create new workload",
      "error": str(e),
    }), 500

  return jsonify({
    "workload_id": workload_public_id,
    "message": "Created new workload successfully"
  }), 201

@routes.route("/workloads/<workload_id>/continue-flow", methods=["PUT"])
def continue_flow(workload_id):
  try:
    data = request.json 
    recipe_data = data.get("recipe_data")

    # Enqueue comicgen task
    comicgen_queue.enqueue(
      "comicgen_worker.comicgen_task",
      workload_id,
      recipe_data,
      result_ttl=86400 #24hrs
    )
    print("[FLASK] Added new task into comicgen queue ✅")

  except Exception as e:
    return jsonify({
      "message": "Failed to continue flow",
      "error": str(e),
    }), 500

  return jsonify({
    "message": "Continued flow successfully"
  }), 200

@routes.route("/workloads/<workload_public_id>/user-decision", methods=["PUT"])
def user_decision(workload_public_id):
  try:
    if not request.is_json:
      return {"message": "Request body must be JSON"}, 400

    data = request.json
    choice = data.get("choice")
    selected_comic_id = data.get("selected_comic_id") 

    if choice not in ["NEW", "EXISTING"]:
      return {"message": "Invalid choice value"}, 400

    print(f"REACHED: workload_public_id={workload_public_id}, choice={choice}, selected_comic_id={selected_comic_id}")

    # TODO: Save decision in DB or perform necessary action

  except Exception as e:
    return {"message": "Failed to handle user decision", "error": str(e)}, 500

  return {"message": "User decision handled successfully"}, 200

@routes.route('/generate-recipe', methods=['POST'])
def generate_recipe():
  try:
    if not request.is_json:
      return {"message": "Request body must be JSON"}, 400

    data = request.json
    dish_name = data.get("dish_name", "") 

    if not dish_name:
      return jsonify({"message": "Missing dish_name param"}), 400

    client = OpenAI()
    prompt = f"""
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

    print("[FLASK] Generated new recipe ✅")

    return jsonify({"recipe": recipe_text, "message": "Generated recipe successfully"}), 200


  except Exception as e:
    return {"message": "Failed to generate recipe", "error": str(e)}, 500
