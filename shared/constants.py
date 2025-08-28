'''This file contains global constants that are required by any service in the system'''

# 1] for flask orchestrator
WORKLOAD_STATUSES = {
  "starting_workload" : "STARTING_WORKLOAD",
  'validating_recipe' : "VALIDATING_RECIPE",
  "extracting_recipe" : "EXTRACTING_RECIPE",
  "searching_comics" : "SEARCHING_EXISTING_COMICS",
  "awaiting_user_choice": "AWAITING_USER_CHOICE",
  "generating_prompts" : "GENERATING_PROMPTS",
  "generating images" : "GENERATING_IMAGES",
  "styling_images" : "STYLING_IMAGES",
  "merging_comic_pages" : "MERGING_COMIC_PAGES",
  "completed_w_existing" :"COMPLETED_W_EXISTING",
  "completed_w_new" : "COMPLETED_W_NEW",
  "failed_not_recipe" : "FAILED_NOT_RECIPE",
  "failed_overlimit" : "FAILED_OVERLIMIT",
}

# 2] For workers- Image generation constants
IMG_GEN_LIMIT = 20
