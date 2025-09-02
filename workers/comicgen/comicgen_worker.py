from ComicGenFlow import ComicGenFlow

def preprocess_task(workload_id, input_text):
  print(f"[Comicgen Worker] Starting ComicGenFlow for workload- {workload_id}")

  # try:
  #   pre_process_flow = ComicGenFlow(task_input=input_text,workload_id=workload_id)
  #   pre_process_flow.kickoff()

  # except Exception as e:
  #   raise Exception(f"\n[Preprocess Worker] An error occurred while running PreProcessingFlow: {e}")

  print(f"[Comicgen Worker] Finished ComicGenFlow for- {workload_id}")