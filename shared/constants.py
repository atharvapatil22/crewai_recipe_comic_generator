'''This file contains global constants that are required by any service in the system'''

# 1] for flask orchestrator
WORKLOAD_STATUSES = {
  "starting_workload" : "Starting workload",
  'validating_recipe' : "Validating recipe",
  "extracting_recipe" : "Extracting recipe",
  "awaiting_user_choice": "Awaiting user choice",
  "generating_prompts" : "Generating prompts",
  "generating images" : "Generating images",
  "styling_images" : "Styling images",
  "merging_comic_pages" : "Merging comic pages",
  "completed_w_existing" :"Completed with existing",
  "completed_w_new" : "Completed with new",
}
