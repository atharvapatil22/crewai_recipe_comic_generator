from ComicGenFlow import ComicGenFlow

def comicgen_task(workload_id, recipe_name,ingredients,instructions):
  print(f"[Comicgen Worker] Starting ComicGenFlow for workload- {workload_id}")

  try:
    comic_gen_flow = ComicGenFlow(recipe_data={'name':recipe_name,'ingredients':ingredients,'instructions':instructions})
    comic_gen_flow.kickoff()

  except Exception as e:
    raise Exception(f"\n[Comicgen Worker] An error occurred while running ComicGenFlow: {e}")

  print(f"[Comicgen Worker] Finished ComicGenFlow for- {workload_id}")