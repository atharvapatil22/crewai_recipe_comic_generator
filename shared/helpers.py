from pydantic import BaseModel
import json
from .supabase_client import supabase

# Function will print Flow state in prettified format
def print_state(state):
  state_dict = {
      k: v.dict() if isinstance(v, BaseModel) else v
      for k, v in state.items()
  }
  print("\n\nState Updated -")
  print(json.dumps(state_dict, indent=2))

# Workload status update
def workload_status_update(workload_id,new_status):
  try:
    supabase.table("workloads").update({"status": new_status}).eq("id", workload_id).execute()
  except Exception as e:
    raise Exception(f"\n[Preprocess Worker] Failed to update status on DB: {e}")