from flask import Blueprint, request, jsonify
import sys
import os
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
    workflow_internal_id = db_response.data[0]["id"]
    workflow_public_id = db_response.data[0]["public_id"]

    # Enqueue preprocess task
    preprocess_queue.enqueue(
      "preprocess_worker.preprocess_task", 
      workflow_internal_id,
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
    "workload_id": workflow_public_id,
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

@routes.route("/workflows/<workflow_id>/user-decision", methods=["PUT"])
def user_decision(workflow_id):
  try:
    data = request.json
    choice = data.get("choice")
    selected_comic_id = data.get("selected_comic_id") 

    print("REACHED",choice,selected_comic_id) 

  except Exception as e:
    return {"message": "Failed to handle user decision", "error": str(e)}, 500

  return {"message": f"User decision handled successfully"}, 200