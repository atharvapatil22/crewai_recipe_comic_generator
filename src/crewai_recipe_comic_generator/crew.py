from crewai.flow.flow import Flow, listen, start
from .comic_gen_models import RecipeData,ImagesData,ImageObject,ImagePrompt
from pydantic import ValidationError
from crewai import Crew,Task,Agent,Process
import json

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

		# print("\n\nState Updated -",self.state)

	# (1) Generate image prompts for (i)List of ingredients (ii)List of instructions and (iii)Poster/Cover page,
	@start()
	def generate_prompts(self):
		recipe_data = self.state['recipe_data']

		prompt_generation_agent = Agent(
			role="Image Prompt Creator",
			goal="Create image generation prompts in the with comic art style.",
			backstory='''You are an AI-powered creator with deep knowledge of recipes and ingredients. You are a part of a crew which makes comic style recipe books. 
			You are responsible for creating image generation prompt for the ingredients, instructions and cover page of the recipe book.''',
			verbose=True
    )

		#i)Ingredients
		ingredient_task = Task(
			description=f'''You are given an ingredient name: {{name}}. 
			Generate a prompt which can be used by a text to image model to generate a comic style image for the ingredient. The prompt should be in less than 50 words. 
			You may use any of the following additional information:
			a) You are also given the quantity ({{quantity}}) of the ingredient. If it is feasable, you may incorporate this in the prompt.
			b) The prompt should be about the ingredient with a blank or simple background''',
			agent=prompt_generation_agent,
			expected_output="A prompt for the image generation tool.",
			output_pydantic=ImagePrompt, 
		)
		ingredient_crew = Crew(
			agents=[prompt_generation_agent],
			tasks=[ingredient_task],
			verbose=True,
			process=Process.sequential 
    )
		ingredient_inputs= [
			{"name": ing.name, "quantity": ing.quantity}
			for ing in recipe_data.ingredients
    ]
		ing_results = ingredient_crew.kickoff_for_each(inputs=ingredient_inputs)

		#ii)Instructions
		instruction_task = Task(
			description=f'''You are given a particular step from the recipe instructions: {{step}}. 
			Generate a prompt which can be used by a text to image model to generate a comic style image for this particular step. The prompt should be in less than 50 words. ''',
			agent=prompt_generation_agent,
			expected_output="A prompt for the image generation tool.",
			output_pydantic=ImagePrompt, 
		)
		instruction_crew = Crew(
			agents=[prompt_generation_agent],
			tasks=[instruction_task],
			verbose=True,
			process=Process.sequential
    )
		instuction_inputs = [{"step": step} for step in recipe_data.instructions]
		ins_results = instruction_crew.kickoff_for_each(inputs=instuction_inputs)

		#iii)Poster
		poster_task = Task(
			description=f'''You are given a recipe name: {recipe_data.name}. 
			Generate a prompt for a comic style cover image representing the final dish with a simple background. 
			- Do not add any title, only generate the image''',
			agent=prompt_generation_agent,
			expected_output="A prompt for the image generation tool.",
			output_pydantic=ImagePrompt, 
    )
		poster_crew = Crew(
			agents=[prompt_generation_agent],
			tasks=[poster_task],
			verbose=True
    )
		poster_prompt = poster_crew.kickoff()

		# Check assertion
		if not len(ing_results) == len(recipe_data.ingredients):
			raise AssertionError(f"Length of Ingredients from recipe_data and prompt results is not the same")
		if not len(ins_results) == len(recipe_data.instructions):
			raise AssertionError(f"Length of Instructions from recipe_data and prompt results is not the same")

		# Parsing the output & updating state
		ingredient_images = []
		for m in range(len(ing_results)):
			ingredient_images.append(
				ImageObject(
				prompt = json.loads(ing_results[m].raw)['prompt'],
				url = "",
				styled_image = "")
			)
		instruction_images = []
		for n in range(len(ins_results)):
			instruction_images.append(
				ImageObject(
				prompt = json.loads(ins_results[n].raw)['prompt'],
				url = "",
				styled_image = "")
			)

		self.state['images_data'].ingredient_images = ingredient_images
		self.state['images_data'].instruction_images = instruction_images
		self.state['images_data'].cover_page.prompt = json.loads(poster_prompt.raw)['prompt']

		# print("\n\nState Updated -",self.state)

	@listen(generate_prompts)
	def fun2(self):
		print("inside fun2")

		return "fun2_output"