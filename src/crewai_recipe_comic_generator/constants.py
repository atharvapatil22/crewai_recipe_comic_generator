'''This file contains global constants that are required anywhere in the app'''

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


