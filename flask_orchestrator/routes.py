from flask import Blueprint, request, jsonify
from shared.constants import WORKLOAD_STATUSES
from shared.supabase_client import supabase
from shared.redis import preprocess_queue

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
      "workers.preprocess_worker.preprocess_task",
      workflow_internal_id,
      input_text,
      result_ttl=3600
    )
    print("[FLASK] Inserted new task into preprocess queue ✅")

  except Exception as e:
    return jsonify({
      "message": "Failed to create new workload",
      "error": str(e),
    }), 500

  return jsonify({
    "workload_id": workflow_public_id,
    "message": "Created new workload successfully"
  }), 201