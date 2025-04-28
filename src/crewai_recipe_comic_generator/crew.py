from crewai.flow.flow import Flow, listen, start
from .comic_gen_models import RecipeData,ImagesData,ImageObject
from pydantic import ValidationError

class ComicGenFlow(Flow):
	def __init__(self, flow_input):
		super().__init__()

    # Save recipe_data in state variable after validaton
		try:
			self.state['recipe_data'] = RecipeData(**flow_input['cleaned_recipe_data'])
		except ValidationError as e:
			raise ValueError(f"Invalid input recieved by ComicGenFlow. Invalid recipe_data: {e}")

    # Create empty images_data state variable
		self.state['images_data'] = ImagesData(
      cover_page=ImageObject(prompt="", url="", styled_image=""),
      ingredient_images=[],
      instruction_images=[]
    )

	@start()
	def fun1(self):
		print("inside fun1")

		return "fun1_output"

	@listen(fun1)
	def fun2(self):
		print("inside fun2")

		return "fun2_output"