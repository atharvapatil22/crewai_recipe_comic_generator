from crewai.flow.flow import Flow, listen, start
from pydantic import ValidationError
from crewai import Crew,Task,Agent,Process
import json
from openai import OpenAI
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image,ImageDraw,ImageFont
from pathlib import Path

from .constants import RL_DALLEE_BATCH_SIZE,RL_DALEE_WAIT_TIME,FINAL_PAGE_HEIGHT,FINAL_PAGE_WIDTH,IMG_GEN_LIMIT
from .comic_gen_models import RecipeData,ImagesData,ImageObject,ImagePrompt
from .helpers import print_state,dalle_api_call,add_image_styling,draw_header

class PreProcessingFlow(Flow):
	def __init__(self, flow_input):
		super().__init__()
		# Save raw input to state
		self.state['input_text'] = flow_input

		print("PreProcessingFlow constructor sucess ✅")
		print_state(self.state)

	# (1) Check if the input resembles a recipe
	@start()
	def validate_recipe(self):
		validator_agent = Agent(
			role="Recipe Validator",
			goal="Decide if the given input text is a valid recipe",
			backstory="You're a culinary AI with expertise in identifying recipes from natural language text.",
			verbose=True
		)

		validation_task = Task(
			description=f"""
			You are given the following user input:
			{self.state['input_text']}

			Determine if it resembles a cooking recipe or not. For it to be a valid recipe it must have mentions of ingredient names and their quantities. And it must gave a series of steps or instrucitons to make the recipe.
			If the input is a valid recipe, respond with 'VALID'.
			If the input is not a recipe or lacks come components, respond with a short reason starting with 'ERROR:'.
			""",
			agent=validator_agent,
			expected_output="Either 'VALID' or 'ERROR: ...'",
		)

		crew = Crew(agents=[validator_agent], tasks=[validation_task], process=Process.sequential)
		result = crew.kickoff()

		if result.raw.startswith("ERROR"):
			print(result)
			raise Exception(f"[Application Exception] The input text does not resemble a recipe")
		
	# (2) Extract recipe data 
	@listen(validate_recipe)
	def extract_full_recipe(self):
		input_text = self.state['input_text']

		# Agent Definition
		recipe_extraction_agent = Agent(
			role="Recipe Extraction Specialist",
			goal="Extract complete structured recipe data from natural language input.",
			backstory="""
					You are a culinary AI assistant trained to understand free-form text that contains recipes.
					You specialize in converting messy or informal recipe text into a clean JSON structure.
					If the recipe name is not clearly mentioned, infer a short descriptive title from the ingredients and instructions.
			""",
			verbose=True
		)

		# Task Description
		recipe_extraction_task = Task(
			description=f"""
			Your job is to extract structured recipe data from the following text:

			{input_text}

			Output a python dictionary with the following keys:
			"name": a sting with title for the recipe,
			"ingredients": a list of dictionaries with each dict containing "name" and "quantity" keys
			"instructions": a list of strings which are the steps of the recipe
			
			Notes:
			- If a title is not explicitly given, infer a name (e.g., "Lemon Water", "Cucumber Mix").
			- Each ingredient must include both name and quantity.
			- for each ingredient its quantity must only contain quantity related data. For example "3 cloves (minced)" should become "3 cloves"
			- if any ingredient is mentioned as optional then remove it completely and also remove the corresponding step or instruction
			- Each instruction step must be a concise, clear sentence.
			""",
			agent=recipe_extraction_agent,
			expected_output="A recipe data object with all the recipe information",
			output_pydantic=RecipeData
		)

		# Run the task via Crew
		crew = Crew(agents=[recipe_extraction_agent], tasks=[recipe_extraction_task], process=Process.sequential)
		result = crew.kickoff()
		parsed_result = json.loads(result.raw)

		# validation image gen limit
		if (len(parsed_result["ingredients"]) + len(parsed_result["instructions"]) + 1) > IMG_GEN_LIMIT:
			raise Exception(f"[Application Exception] Recipe is too large. Current app limit is set for {IMG_GEN_LIMIT} images!")
		
		return parsed_result

class ComicGenFlow(Flow):
	def __init__(self, flow_input):
		super().__init__()

    # Save recipe_data in state variable after validaton
		try:
			self.state['recipe_data'] = RecipeData(**flow_input)
		except ValidationError as e:
			raise ValueError(f"[Application Exception] Invalid input recieved by ComicGenFlow. Invalid recipe_data: {e}")

    # Create empty images_data state variable
		self.state['images_data'] = ImagesData(
      cover_page=ImageObject(type="POSTER",prompt="", url="", styled_image=""),
      ingredient_images=[],
      instruction_images=[]
    )

		print("ComicGenFlow constructor sucess ✅")
		print_state(self.state)

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
			Generate a prompt which can be used by a text to image model to generate an image for the ingredient in comic art style. The prompt should be in less than 50 words. 
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
			Generate a prompt which can be used by a text to image model to generate a comic style image for this particular step. The prompt should be in less than 50 words. It should be focused on the action performed in the step. Background should be simple ''',
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
		images_data = self.state['images_data']
		pages = []
		HEADER_MARGIN = 20
		header_height = 120 + HEADER_MARGIN

		### First page: Poster image with its header
		poster_img_obj = images_data.cover_page.styled_image

		# Create a copy to draw on
		poster_with_overlay = poster_img_obj.copy()
		draw = ImageDraw.Draw(poster_with_overlay)

		# Overlay rectangle settings
		OVERLAY_WIDTH = int(FINAL_PAGE_WIDTH * 0.7)
		OVERLAY_HEIGHT = 240
		OVERLAY_MARGIN_BOTTOM = 300
		OVERLAY_COLOR = (135, 206, 250)
		OVERLAY_TEXT = self.state['recipe_data'].name
		BORDER_THICKNESS = 4
		BORDER_COLOR = (0, 0, 0)

		# Calculate position
		rect_x0 = (FINAL_PAGE_WIDTH - OVERLAY_WIDTH) // 2
		rect_y1 = FINAL_PAGE_HEIGHT - OVERLAY_MARGIN_BOTTOM
		rect_y0 = rect_y1 - OVERLAY_HEIGHT
		rect_x1 = rect_x0 + OVERLAY_WIDTH

		# Draw overlay background
		draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=OVERLAY_COLOR)

		# Draw solid black border (4 sides manually to match "solid border")
		for i in range(BORDER_THICKNESS):
			draw.rectangle(
				[rect_x0 - i, rect_y0 - i, rect_x1 + i, rect_y1 + i],
				outline=BORDER_COLOR
			)

		# Load and draw text
		pattaya_font = Path(__file__).resolve().parent / "assets" / "Pattaya.ttf"
		try:
			font = ImageFont.truetype(str(pattaya_font), 68)
		except:
			font = ImageFont.load_default()

		# First line: main title
		bbox1 = font.getbbox(OVERLAY_TEXT)
		text1_w, text1_h = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
		text1_x = rect_x0 + (OVERLAY_WIDTH - text1_w) // 2
		text1_y = rect_y0 + 20  # Top margin from inside the rectangle

		draw.text((text1_x, text1_y), OVERLAY_TEXT, fill=(0, 0, 0), font=font)

		subtitle_font = ImageFont.truetype(str(pattaya_font), 48)
		bbox2 = subtitle_font.getbbox("(Recipe Book)")
		text2_w, text2_h = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
		text2_x = rect_x0 + (OVERLAY_WIDTH - text2_w) // 2
		text2_y = text1_y + text1_h + 10

		draw.text((text2_x, text2_y), "(Recipe Book)", fill=(0, 0, 0), font=subtitle_font)

		# Add final image to pages
		pages.append(poster_with_overlay)

		### Pages for ING images (3x4 grid = 12 per page)
		ING_ROWS = 4
		ING_COLS = 3
		ING_PER_PAGE = ING_ROWS * ING_COLS

		ing_chunks = [images_data.ingredient_images[i:i+ING_PER_PAGE] for i in range(0, len(images_data.ingredient_images), ING_PER_PAGE)]

		for chunk in ing_chunks:
			page = Image.new("RGB", (FINAL_PAGE_WIDTH, FINAL_PAGE_HEIGHT), color=(255, 255, 255))
			draw = ImageDraw.Draw(page)
			draw_header(draw, "Ingredients")

			sample_img = chunk[0].styled_image
			img_w, img_h = sample_img.size

			total_imgs_w = ING_COLS * img_w
			total_imgs_h = ING_ROWS * img_h

			padding_x = (FINAL_PAGE_WIDTH - total_imgs_w) // 2
			padding_y = ((FINAL_PAGE_HEIGHT - total_imgs_h) // 2) + header_height // 2  # shift down

			for idx, img_obj in enumerate(chunk):
				row = idx // ING_COLS
				col = idx % ING_COLS

				x0 = padding_x + col * img_w
				y0 = padding_y + row * img_h

				page.paste(img_obj.styled_image, (x0, y0))

			pages.append(page)

		### Pages for INS images (3 per page, stacked vertically)
		INS_PER_PAGE = 3

		ins_chunks = [images_data.instruction_images[i:i+INS_PER_PAGE] for i in range(0, len(images_data.instruction_images), INS_PER_PAGE)]

		for chunk in ins_chunks:
			page = Image.new("RGB", (FINAL_PAGE_WIDTH, FINAL_PAGE_HEIGHT), color=(255, 255, 255))
			draw = ImageDraw.Draw(page)
			draw_header(draw, "Instructions")

			# These are fixed expected dimensions
			expected_h = FINAL_PAGE_WIDTH // 2   # because width:height is 4:7 → image height is half of page width
			expected_w = FINAL_PAGE_HEIGHT // 2  # image width is half of page height

			current_y = header_height  # start below the header

			for img_obj in chunk:
				img = img_obj.styled_image
				img_w, img_h = img.size

				# Verify aspect ratio is approximately 7:4
				assert abs((img_w / img_h) - (7/4)) < 0.05, f"INS image has wrong aspect ratio: {img_w}:{img_h}"

				# Verify size
				assert abs(img_w - expected_w) <= 5 and abs(img_h - expected_h) <= 5, f"INS image has wrong size: {img_w}x{img_h}"

				# Center horizontally
				x0 = (FINAL_PAGE_WIDTH - img_w) // 2
				y0 = current_y

				page.paste(img, (x0, y0))

				current_y += img_h  # stack next image below

			pages.append(page)

		for page in pages:
			page.show()
		
		return pages
		
