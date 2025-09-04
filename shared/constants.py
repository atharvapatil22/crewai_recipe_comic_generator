'''This file contains global constants that are required by any service in the system'''

# 1] for flask orchestrator
WORKLOAD_STATUSES = {
  "starting_workload" : "STARTING_WORKLOAD",
  'validating_recipe' : "VALIDATING_RECIPE",
  "extracting_recipe" : "EXTRACTING_RECIPE",
  "searching_comics" : "SEARCHING_EXISTING_COMICS",
  "awaiting_user_choice": "AWAITING_USER_CHOICE",
  "generating_prompts" : "GENERATING_PROMPTS",
  "generating_images" : "GENERATING_IMAGES",
  "styling_images" : "STYLING_IMAGES",
  "merging_comic_pages" : "MERGING_COMIC_PAGES",
  "completed_w_existing" :"COMPLETED_W_EXISTING",
  "completed_w_new" : "COMPLETED_W_NEW",
  "failed_not_recipe" : "FAILED_NOT_RECIPE",
  "failed_overlimit" : "FAILED_OVERLIMIT",
}

# 2] For workers

# Image generation constants
IMG_GEN_LIMIT = 20
ING_IMAGE_SIZE = "1024x1024"
INS_IMAGE_SIZE = "1792x1024"
POSTER_IMAGE_SIZE = "1024x1792"

# Rate Limit constants (RL)
RL_DALLEE_BATCH_SIZE = 5 #How many parallel calls(batch size) to the Image generation api
RL_DALEE_WAIT_TIME = 60 #How many seconds to wait, before next batch of calls to Image generation api

# Page Styling constants (PS)
FINAL_PAGE_HEIGHT = 1792
FINAL_PAGE_WIDTH = 1024

PS_TITLE_HEIGHT = 140
