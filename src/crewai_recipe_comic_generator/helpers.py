from openai import RateLimitError, APIError
from .constants import ING_IMAGE_SIZE,INS_IMAGE_SIZE,POSTER_IMAGE_SIZE
from pydantic import BaseModel
import json

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