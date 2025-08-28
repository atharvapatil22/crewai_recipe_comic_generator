'''All the pydantic models required by the system are defined here'''
 
from pydantic import BaseModel,Field
from typing import List,Literal

# 1) Suplimentary state models - These are required by the main state models

class IngredientData(BaseModel):
  name: str
  quantity: str

class ImageObject(BaseModel):
  type: Literal["ING","INS","POSTER"]
  prompt: str
  url: str
  styled_image: str

# 2) Main state models - These models will be used by the internal state of the flow

class RecipeData(BaseModel):
  name: str
  ingredients: List[IngredientData]
  instructions: List[str]
  db_id: int

class ImagesData(BaseModel):
  cover_page: ImageObject
  ingredient_images: List[ImageObject]
  instruction_images: List[ImageObject]

# 3) Agent/Tast models - These are required for some agents or tasks in the flow

class ImagePrompt(BaseModel):
  prompt: str = Field(description = "A prompt for text to image models that can be used to generate an image.")
	