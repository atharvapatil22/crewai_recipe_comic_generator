from openai import RateLimitError, APIError
from .constants import ING_IMAGE_SIZE,INS_IMAGE_SIZE,POSTER_IMAGE_SIZE,FINAL_PAGE_HEIGHT,FINAL_PAGE_WIDTH,PS_TITLE_HEIGHT
from pydantic import BaseModel
import json
from PIL import Image,ImageFont,ImageDraw
import requests
from io import BytesIO
import base64
from pathlib import Path

# Function will print Flow state in prettified format
def print_state(state):
  state_dict = {
      k: v.dict() if isinstance(v, BaseModel) else v
      for k, v in state.items()
  }
  print("\n\nState Updated -")
  print(json.dumps(state_dict, indent=2))


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
  
# This function will resize images and add text to them
def add_image_styling(img_obj):
  response = requests.get(img_obj.url, stream=True)
  raw_img = Image.open(BytesIO(response.content))
  # print(f"Image Type: {img_obj.type}, Resolution: {img.width}x{img.height}")
      
  if img_obj.type == "ING":
    LABEL_HEIGHT = 60
    LABEL_COLOR = (135, 206, 250)  # Sky blue

    # Scale down image
    new_width = (FINAL_PAGE_WIDTH * 22) // 80
    resized_img = raw_img.resize((new_width, new_width))

    # Add label text
    labled_img = Image.new("RGB", (new_width, new_width + LABEL_HEIGHT), color=(255, 255, 255))
    
    draw = ImageDraw.Draw(labled_img)
    draw.rectangle([0, 0, new_width, LABEL_HEIGHT], fill=LABEL_COLOR)
    pattaya_font = Path(__file__).resolve().parent / "assets" / "Pattaya.ttf"
    try:
      font = ImageFont.truetype(str(pattaya_font), 20)
    except:
      font = ImageFont.load_default()
    text = "placeholder"
    bbox = font.getbbox(text)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x = (new_width - text_w) // 2
    text_y = (LABEL_HEIGHT - text_h) // 2
    draw.text((text_x, text_y), text, fill=(0, 0, 0), font=font)

    labled_img.paste(resized_img, (0, LABEL_HEIGHT))

    img_obj.styled_image = labled_img

  elif img_obj.type == "INS":
    raw_img = raw_img.resize((FINAL_PAGE_HEIGHT // 2, FINAL_PAGE_WIDTH // 2))
    img_obj.styled_image = raw_img

  else:
    img_obj.styled_image = raw_img

  

def image_to_base64(image):
  """Converts a PIL Image to a base64 string."""
  buffered = BytesIO()
  image.save(buffered, format="PNG")  
  img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
  return img_str

def draw_page_title(draw, title):
  TITLE_HEIGHT = PS_TITLE_HEIGHT
  TITLE_BG_COLOR = (135, 206, 250)  # sky blue
  TITLE_TEXT_COLOR = (0, 0, 0)
  TITLE_BORDER_COLOR = (0, 0, 0)     # Black
  TITLE_BORDER_THICKNESS = 4
  pattaya_font = Path(__file__).resolve().parent / "assets" / "Pattaya.ttf"

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