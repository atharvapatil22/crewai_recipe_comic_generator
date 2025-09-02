from crewai.flow.flow import Flow, listen, start
from crewai import Crew,Task,Agent,Process
import json
from openai import OpenAI
from PIL import Image,ImageDraw,ImageFont
from io import BytesIO
import requests
import time
from pydantic import ValidationError
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from postgrest import APIError
from shared.helpers import print_state,dalle_api_call,style_ing_image,style_ins_image,draw_page_title,get_reddit_preview_image
from shared.pydantic_models import RecipeData,ImagesData,ImageObject,ImagePrompt
from shared.constants import RL_DALEE_WAIT_TIME,RL_DALLEE_BATCH_SIZE,FINAL_PAGE_WIDTH,FINAL_PAGE_HEIGHT,PS_TITLE_HEIGHT

class ComicGenFlow(Flow):
	def __init__(self, recipe_data):
		super().__init__()

    # Save recipe_data in state variable after validaton
		try:
			self.state['recipe_data'] = RecipeData(**recipe_data)
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
		images_data = self.state['images_data']
		recipe_data = self.state['recipe_data']

		# Check assertion
		if not len(images_data.ingredient_images) == len(recipe_data.ingredients):
			raise AssertionError(f"[Application Exception] Length of Ingredients from image_data and recipe_data is not the same")
		if not len(images_data.instruction_images) == len(recipe_data.instructions):
			raise AssertionError(f"[Application Exception] Length of Instructions from image_data and recipe_data is not the same")
		
		for index in range(0,len(images_data.ingredient_images)):
			style_ing_image(images_data.ingredient_images[index],recipe_data.ingredients[index])
		for index in range(0,len(images_data.instruction_images)):
			style_ins_image(images_data.instruction_images[index],recipe_data.instructions[index],index+1)

		print('\n\nState updated- ',self.state['images_data'])

	# (4) Merge the styled images and generate book pages.
	@listen(style_images)
	def merge_images(self):
		images_data = self.state['images_data']
		pages = []

		# # (4a) First page: Poster image with its header
		# poster_img_obj = images_data.cover_page.styled_image

		response = requests.get(images_data.cover_page.url, stream=True)
		raw_img = Image.open(BytesIO(response.content))

		# Create a copy to draw on
		poster_with_overlay = raw_img.copy()
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

		# (4a) First page completed
		pages.append(poster_with_overlay)

		# (4b) Ingredients pages (3x4 grid = 12 per page)
		ing_image_objects = images_data.ingredient_images
		ING_ROWS = 4
		ING_COLS = 3
		ING_PER_PAGE = ING_ROWS * ING_COLS

		# All styled ingredient images are the same size, use any random one to get the dimensions
		sample_image = ing_image_objects[0].styled_image
		ing_width, ing_height = sample_image.width, sample_image.height

		# Calculate how much empty space will be left and divide it evenly (space-evenly logic)
		total_img_width = ING_COLS * ing_width
		total_img_height = ING_ROWS * ing_height
		total_h_space = FINAL_PAGE_WIDTH - total_img_width
		h_gap = total_h_space / (ING_COLS + 1)
		total_v_space = (FINAL_PAGE_HEIGHT - PS_TITLE_HEIGHT) - total_img_height
		v_gap = total_v_space / (ING_ROWS + 1)

		for page_start in range(0, len(ing_image_objects), ING_PER_PAGE):
			# Get the current set of 1 to 12 images
			page_images = ing_image_objects[page_start:page_start + ING_PER_PAGE]

			# Create a new blank white page
			page = Image.new("RGB", (FINAL_PAGE_WIDTH, FINAL_PAGE_HEIGHT), color="white")
			draw = ImageDraw.Draw(page)
			draw_page_title(draw, "Ingredients")

			for idx, img_obj in enumerate(page_images):
				row = idx // ING_COLS
				col = idx % ING_COLS

				x = int(h_gap + col * (ing_width + h_gap))
				y = int(PS_TITLE_HEIGHT + v_gap + row * (ing_height + v_gap))

				page.paste(img_obj.styled_image, (x, y))

			pages.append(page)

		# (4c) Instruction pages (3 per page)
		ins_image_objects = images_data.instruction_images
		INS_PER_PAGE = 3 

		for i in range(0, len(ins_image_objects), INS_PER_PAGE):
			page_imgs = ins_image_objects[i:i+INS_PER_PAGE]

			# Create blank page
			page = Image.new("RGB", (FINAL_PAGE_WIDTH, FINAL_PAGE_HEIGHT), color=(255, 255, 255))
			draw = ImageDraw.Draw(page)
			draw_page_title(draw, "Instructions")

			# Calculate layout
			available_height = FINAL_PAGE_HEIGHT - PS_TITLE_HEIGHT
			total_imgs_height = sum(img.styled_image.height for img in page_imgs)
			num_gaps = len(page_imgs) + 1  # space above, between, and below
			gap_height = (available_height - total_imgs_height) // num_gaps

			# Start placing images
			current_y = PS_TITLE_HEIGHT + gap_height
			for obj in page_imgs:
				img = obj.styled_image
				x = (FINAL_PAGE_WIDTH - img.width) // 2  # center horizontally
				page.paste(img, (x, current_y))
				current_y += img.height + gap_height

			pages.append(page)

		# for page in pages:
		# 	page.show()

		return pages
	
	# (5) Save the comic book on third party cloud platform
	@listen(merge_images)
	def cloud_upload(self,pages):

		comic_url = upload_comic_to_reddit(pages,self.state['recipe_data'].name)

		submission_id = comic_url.split('/')[-1]  
		preview_image_url = get_reddit_preview_image(submission_id)

		# Adding comic url into DB
		try:
			db_response = (
				supabase
				.table("workloads")
				.update({"comic_url": comic_url,"preview_image_url":preview_image_url})
				.eq("id", self.state['recipe_data'].db_id)
				.execute()
			)
			
			print("Adding comic url into DB ✅")
			# print("DB response: ",db_response)
		except (APIError) as e:
			raise Exception(f"[DB Exception] msg {e}")
		
		return pages
		
