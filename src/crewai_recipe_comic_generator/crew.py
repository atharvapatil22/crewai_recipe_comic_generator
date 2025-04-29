from crewai.flow.flow import Flow, listen, start
from pydantic import ValidationError
from crewai import Crew,Task,Agent,Process
import json
from openai import OpenAI
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .constants import RL_DALLEE_BATCH_SIZE,RL_DALEE_WAIT_TIME
from .comic_gen_models import RecipeData,ImagesData,ImageObject,ImagePrompt
from .helpers import print_state,dalle_api_call,add_image_styling

class ComicGenFlow(Flow):
	def __init__(self, flow_input):
		super().__init__()

    # Save recipe_data in state variable after validaton
		try:
			self.state['recipe_data'] = RecipeData(**flow_input['cleaned_recipe_data'])
		except ValidationError as e:
			raise ValueError(f"[Application Exception] Invalid input recieved by ComicGenFlow. Invalid recipe_data: {e}")

    # Create empty images_data state variable
		self.state['images_data'] = ImagesData(
      cover_page=ImageObject(type="POSTER",prompt="", url="", styled_image=""),
      ingredient_images=[],
      instruction_images=[]
    )

		# print_state(self.state)

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
			raise AssertionError(f"[Application Exception] Length of Ingredients from recipe_data and prompt results is not the same")
		if not len(ins_results) == len(recipe_data.instructions):
			raise AssertionError(f"[Application Exception] Length of Instructions from recipe_data and prompt results is not the same")

		# Parsing the output & updating state
		ingredient_images = []
		for m in range(len(ing_results)):
			ingredient_images.append(
				ImageObject(
				type = "ING",
				prompt = json.loads(ing_results[m].raw)['prompt'],
				url = "",
				styled_image = "")
			)
		instruction_images = []
		for n in range(len(ins_results)):
			instruction_images.append(
				ImageObject(
				type = "INS",
				prompt = json.loads(ins_results[n].raw)['prompt'],
				url = "",
				styled_image = "")
			)

		self.state['images_data'].ingredient_images = ingredient_images
		self.state['images_data'].instruction_images = instruction_images
		self.state['images_data'].cover_page.prompt = json.loads(poster_prompt.raw)['prompt']

		# print_state(self.state)

	# (2) Generate DallE images using prompts
	@listen(generate_prompts)
	def generate_images(self):
		client = OpenAI()

		# A list of all image objects including ingredients,instructions & poster. For each object dall api will be called
		image_objects_list = self.state['images_data'].ingredient_images + self.state['images_data'].instruction_images + [self.state['images_data'].cover_page]

		# This loop will make parallel calls using the dalle_api_call function and other constant parameters
		for i in range(0,len(image_objects_list),RL_DALLEE_BATCH_SIZE):
			
			# Create a batch of image objects
			batch = image_objects_list[i:i+RL_DALLEE_BATCH_SIZE]

			print(f"Processing batch {i//RL_DALLEE_BATCH_SIZE + 1}")
			start_time = time.time()

			with ThreadPoolExecutor(max_workers=RL_DALLEE_BATCH_SIZE) as executor:
				future_to_prompt = {executor.submit(dalle_api_call, imageObj, client): imageObj for imageObj in batch}
				for future in as_completed(future_to_prompt):
					future.result()

			# if more image objects are left then this block will handle sleep to avoid hitting the RL_DALEE_WAIT_TIME limit
			if i + RL_DALLEE_BATCH_SIZE < len(image_objects_list):
				elapsed = time.time() - start_time
				sleep_time = max(0, RL_DALEE_WAIT_TIME - elapsed)
				print(f"Waiting for {sleep_time:.2f} seconds before next batch...")
				time.sleep(sleep_time)
				
		# print_state(self.state)

	# (3) Style the generated images with cropping and adding text
	@listen(generate_images)
	def style_images(self):
		image_objects_list = self.state['images_data'].ingredient_images + self.state['images_data'].instruction_images + [self.state['images_data'].cover_page]

		for imgObj in image_objects_list:
			add_image_styling(imgObj)

		print('\n\nState updated- ',self.state['images_data'])

	# (4) Merge the styled images and generate book pages.
	@listen(style_images)
	def merge_images(self):
		""
