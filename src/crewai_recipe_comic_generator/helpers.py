from openai import RateLimitError, APIError
from .constants import ING_IMAGE_SIZE,INS_IMAGE_SIZE,POSTER_IMAGE_SIZE,FINAL_PAGE_HEIGHT,FINAL_PAGE_WIDTH
from pydantic import BaseModel
import json
from PIL import Image,ImageFont
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
  img = Image.open(BytesIO(response.content))
  # print(f"Image Type: {img_obj.type}, Resolution: {img.width}x{img.height}")
      
  if img_obj.type == "ING":
    x = (FINAL_PAGE_WIDTH * 25) // 80
    x = int(x)  # Make sure it's an integer
    img = img.resize((x, x))
  elif img_obj.type == "INS":
    img = img.resize((FINAL_PAGE_HEIGHT // 2, FINAL_PAGE_WIDTH // 2))

  # print(f"-resized: {img_obj.type}, Resolution: {img.width}x{img.height}")

  
  # LOGIC TO ADD TEXT ON IMAGES

  img_obj.styled_image = img

def image_to_base64(image):
  """Converts a PIL Image to a base64 string."""
  buffered = BytesIO()
  image.save(buffered, format="PNG")  
  img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
  return img_str

def draw_header(draw, title):
  HEADER_HEIGHT = 120
  HEADER_COLOR = (135, 206, 250)  # sky blue
  HEADER_TEXT_COLOR = (0, 0, 0)
  HEADER_BORDER_COLOR = (0, 0, 0)     # Black
  HEADER_BORDER_THICKNESS = 4
  pattaya_font = Path(__file__).resolve().parent / "assets" / "Pattaya.ttf"

  # Full-width rectangle (header background)
  rect_x0 = 0
  rect_y0 = 0
  rect_x1 = FINAL_PAGE_WIDTH
  rect_y1 = HEADER_HEIGHT
  draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=HEADER_COLOR)

  # Bottom border line (4px black)
  border_y0 = HEADER_HEIGHT - HEADER_BORDER_THICKNESS
  border_y1 = HEADER_HEIGHT
  draw.rectangle([rect_x0, border_y0, rect_x1, border_y1], fill=HEADER_BORDER_COLOR)

  # Load custom font
  try:
    font = ImageFont.truetype(str(pattaya_font), 46)
  except:
    font = ImageFont.load_default()

  # Center the title
  bbox = font.getbbox(title)
  text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
  text_x = (FINAL_PAGE_WIDTH - text_w) // 2
  text_y = (HEADER_HEIGHT - text_h) // 2

  draw.text((text_x, text_y), title, fill=HEADER_TEXT_COLOR, font=font)