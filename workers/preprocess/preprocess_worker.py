import PreProcessingFlow

def preprocess_task(workload_id, input_text):
  print(f"[Preprocess Worker] Starting PreprocessingFlow for workload- {workload_id}")

  try:
    pre_process_flow = PreProcessingFlow(task_input=input_text,workload_id=workload_id)
    pre_process_flow.kickoff()

  except Exception as e:
    raise Exception(f"\n[Preprocess Worker] An error occurred while running PreProcessingFlow: {e}")

  print(f"[Preprocess Worker] Finished PreprocessingFlow for- {workload_id}")