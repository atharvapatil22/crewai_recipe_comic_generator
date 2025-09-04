from pydantic import BaseModel
import json
from openai import RateLimitError, APIError
from PIL import Image,ImageFont,ImageDraw,ImageOps
import requests
from io import BytesIO
from pathlib import Path
import textwrap
import praw
import tempfile
import os
import html
from .supabase_client import supabase
from .constants import ING_IMAGE_SIZE,INS_IMAGE_SIZE,POSTER_IMAGE_SIZE,FINAL_PAGE_WIDTH,PS_TITLE_HEIGHT


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
    raise Exception(f"\n[System Error] Failed to update status on DB: {e}")
  
# Function will recieve an image object with a prompt and a type. It will dynamically call dalle api and add the generated url to the input image object
def dalle_api_call(imageObj,client):

  if imageObj.type == "ING":
    size = ING_IMAGE_SIZE
  elif imageObj.type == "INS":
    size = INS_IMAGE_SIZE
  elif imageObj.type == "POSTER":
    size = POSTER_IMAGE_SIZE
  
  try:
    response = client.images.generate(model="dall-e-3",
      prompt=imageObj.prompt,
      n=1,
      size=size)
    
    if not response.data:
      raise ValueError(f"[Application Exception] No data in dalle API response: ",response)

    # Assign the generated url to its respective image object
    imageObj.url = response.data[0].url 

    return response.data[0].url 
  except (RateLimitError,APIError) as e:
    raise Exception(f"[Application Exception] msg {e}")
  

# This function will download the generated ING images and save them as PIL. And resize + add labels to them
def style_ing_image(img_obj,ing_obj):
  response = requests.get(img_obj.url, stream=True)
  raw_img = Image.open(BytesIO(response.content))
  LABEL_HEIGHT = 80
  LABEL_COLOR = (135, 206, 250)  # Sky blue
  BORDER_SIZE = 2

  # Scale down image
  new_width = (FINAL_PAGE_WIDTH * 22) // 80
  resized_img = raw_img.resize((new_width, new_width))

  # Add label text
  labled_img = Image.new("RGB", (new_width, new_width + LABEL_HEIGHT), color=(255, 255, 255))
  
  draw = ImageDraw.Draw(labled_img)
  draw.rectangle([0, 0, new_width, LABEL_HEIGHT], fill=LABEL_COLOR)
  draw.rectangle([0, LABEL_HEIGHT - BORDER_SIZE, new_width, LABEL_HEIGHT],fill="black")

  patrick_font_path = "/app/fonts/PatrickHand.ttf"
  if not os.path.exists(patrick_font_path):
    raise FileNotFoundError(f"Font file not found at {patrick_font_path}.")
  patrick_font = Path(patrick_font_path)
  try:
    font = ImageFont.truetype(str(patrick_font), 25)
  except:
    font = ImageFont.load_default()
  # Split text into two lines
  name_text = f'{ing_obj.name}'
  quantity_text = f'({ing_obj.quantity})'

  # Measure each line
  name_bbox = font.getbbox(name_text)
  name_w, name_h = name_bbox[2] - name_bbox[0], name_bbox[3] - name_bbox[1]

  qty_bbox = font.getbbox(quantity_text)
  qty_w, qty_h = qty_bbox[2] - qty_bbox[0], qty_bbox[3] - qty_bbox[1]

  # Compute vertical placement for two lines
  total_text_height = name_h + qty_h + 8  # 4px spacing between lines
  start_y = (LABEL_HEIGHT - total_text_height) // 2

  # Draw both lines centered
  draw.text(((new_width - name_w) // 2, start_y), name_text, fill=(0, 0, 0), font=font)
  draw.text(((new_width - qty_w) // 2, start_y + name_h + 4), quantity_text, fill=(0, 0, 0), font=font)

  # Paste the image below the label
  labled_img.paste(resized_img, (0, LABEL_HEIGHT))

  bordered_image = ImageOps.expand(labled_img, border=BORDER_SIZE, fill="black")

  img_obj.styled_image = bordered_image  

# This function will download the generated INS images and save them as PIL. And resize + add text to them
def style_ins_image(img_obj,ins_text,step_num):
  response = requests.get(img_obj.url, stream=True)
  raw_img = Image.open(BytesIO(response.content))

  BASE_LABEL_HEIGHT = 50
  LABEL_COLOR = (135, 206, 250)  # Sky blue
  BORDER_SIZE = 2
  SCALE_DOWN_FACTOR = 0.45
  MAX_LABEL_HEIGHT = 80
  LINE_SPACING = 6
  TEXT_PADDING_X = 10

  # Scale down image
  new_width = int(raw_img.width * SCALE_DOWN_FACTOR)
  new_height = int(raw_img.height * SCALE_DOWN_FACTOR)
  resized_img = raw_img.resize((new_width, new_height))

  # Load font
  patrick_font = Path(__file__).resolve().parent / "assets" / "PatrickHand.ttf"
  try:
    font = ImageFont.truetype(str(patrick_font), 25)
  except:
    font = ImageFont.load_default()

  full_text = f"Step {step_num}: {ins_text}"

  # Check if text fits in one line
  text_width = font.getbbox(full_text)[2] - font.getbbox(full_text)[0]
  available_width = new_width - 2 * TEXT_PADDING_X

  if text_width <= available_width:
    label_height = BASE_LABEL_HEIGHT
    labled_img = Image.new("RGB", (new_width, new_height + label_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(labled_img)

    # Draw background and border
    draw.rectangle([0, new_height, new_width, new_height + label_height], fill=LABEL_COLOR)
    draw.rectangle([0, new_height, new_width, new_height + BORDER_SIZE], fill="black")

    # Vertically center
    text_h = font.getbbox(full_text)[3] - font.getbbox(full_text)[1]
    text_y = new_height + (label_height - text_h) // 2
    draw.text((TEXT_PADDING_X, text_y), full_text, fill=(0, 0, 0), font=font)
  else:
    # Split into 2 lines
    label_height = MAX_LABEL_HEIGHT
    labled_img = Image.new("RGB", (new_width, new_height + label_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(labled_img)

    draw.rectangle([0, new_height, new_width, new_height + label_height], fill=LABEL_COLOR)
    draw.rectangle([0, new_height, new_width, new_height + BORDER_SIZE], fill="black")

    # Wrap text into max 2 lines
    wrapper = textwrap.TextWrapper(width=100)
    wrapped_lines = []
    temp_line = ""
    for word in full_text.split():
      trial_line = temp_line + (" " if temp_line else "") + word
      if font.getbbox(trial_line)[2] - font.getbbox(trial_line)[0] <= available_width:
        temp_line = trial_line
      else:
        wrapped_lines.append(temp_line)
        temp_line = word
      if len(wrapped_lines) == 2:
        break
    if temp_line and len(wrapped_lines) < 2:
      wrapped_lines.append(temp_line)

    # Vertical centering
    total_text_height = sum(font.getbbox(line)[3] - font.getbbox(line)[1] for line in wrapped_lines)
    total_text_height += (len(wrapped_lines) - 1) * LINE_SPACING
    start_y = new_height + (label_height - total_text_height) // 2

    for i, line in enumerate(wrapped_lines):
      line_h = font.getbbox(line)[3] - font.getbbox(line)[1]
      draw.text((TEXT_PADDING_X, start_y), line, fill=(0, 0, 0), font=font)
      start_y += line_h + LINE_SPACING

  # Paste the image above the label
  labled_img.paste(resized_img, (0, 0))
  bordered_image = ImageOps.expand(labled_img, border=BORDER_SIZE, fill="black")

  img_obj.styled_image = bordered_image

def draw_page_title(draw, title):
  TITLE_HEIGHT = PS_TITLE_HEIGHT
  TITLE_BG_COLOR = (135, 206, 250)  # sky blue
  TITLE_TEXT_COLOR = (0, 0, 0)
  TITLE_BORDER_COLOR = (0, 0, 0)     # Black
  TITLE_BORDER_THICKNESS = 4

  pattaya_font_path = "/app/fonts/Pattaya.ttf"
  if not os.path.exists(pattaya_font_path):
    raise FileNotFoundError(f"Font file not found at {pattaya_font_path}.")
  pattaya_font = Path(pattaya_font_path)

  # Full-width rectangle (title background)
  rect_x0 = 0
  rect_y0 = 0
  rect_x1 = FINAL_PAGE_WIDTH
  rect_y1 = TITLE_HEIGHT
  draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=TITLE_BG_COLOR)

  # Bottom border line (4px black)
  border_y0 = TITLE_HEIGHT - TITLE_BORDER_THICKNESS
  border_y1 = TITLE_HEIGHT
  draw.rectangle([rect_x0, border_y0, rect_x1, border_y1], fill=TITLE_BORDER_COLOR)

  # Load custom font
  try:
    font = ImageFont.truetype(str(pattaya_font), 46)
  except:
    font = ImageFont.load_default()

  # Center the title
  bbox = font.getbbox(title)
  text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
  text_x = (FINAL_PAGE_WIDTH - text_w) // 2
  text_y = (TITLE_HEIGHT - text_h) // 2

  draw.text((text_x, text_y), title, fill=TITLE_TEXT_COLOR, font=font)

def upload_comic_to_reddit(pil_images,recipe_name):

  reddit = praw.Reddit(
    client_id=os.environ.get("REDDIT_CLIENT_ID"),             
    client_secret=os.environ.get("REDDIT_SECRET"),     
    username="No-Advisor9169",              
    password=os.environ.get("REDDIT_ACCOUNT_PASSWORD"),        
    user_agent="RecipeComicGenGallery/0.1 by u/No-Advisor9169"
  )

  # Subreddit to post to
  subreddit = reddit.subreddit("RecipeComicGenGallery")

  # Save PIL images to temporary files
  temp_files = []
  for idx, img in enumerate(pil_images):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    img.save(temp_file, format="JPEG")
    temp_file.close()  
    temp_files.append({"image_path": temp_file.name, "caption": f"Page {idx + 1}"})

  post_title = recipe_name + " - Recipe book"
  # Submit gallery post 
  submission = subreddit.submit_gallery(
    title=post_title,
    images=temp_files,
    nsfw=False,       # Optional: mark NSFW
    spoiler=False,    # Optional: mark Spoiler
    flair_id=None,    # Optional: add a flair ID
    flair_text=None   # Optional: set flair text
  )

  print("Comic uploaded to reddit ✅")

  # Clean up temp files 
  for img in temp_files:
    os.remove(img["image_path"])

  return submission.url

def get_reddit_preview_image(submission_id: str) -> str | None:
  reddit = praw.Reddit(
    client_id=os.environ.get("REDDIT_CLIENT_ID"),             
    client_secret=os.environ.get("REDDIT_SECRET"),     
    username="No-Advisor9169",              
    password=os.environ.get("REDDIT_ACCOUNT_PASSWORD"),        
    user_agent="RecipeComicGenGallery/0.1 by u/No-Advisor9169"
  )

  try:
    submission = reddit.submission(id=submission_id)
    if hasattr(submission, "media_metadata"):
      media = submission.media_metadata
      first_media_id = list(submission.gallery_data['items'])[0]['media_id']
      url = media[first_media_id]['s']['u']
      return html.unescape(url)
    else:
      print("[Warning] No media metadata available.")
      return None
  except Exception as e:
    print(f"[Error] Reddit API fetch failed: {e}")
    return None

  except Exception as e:
    print(f"[Error] Failed to fetch or parse Reddit post JSON: {e}")
    return None