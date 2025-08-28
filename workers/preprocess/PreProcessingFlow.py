from crewai.flow.flow import Flow, listen, start
from crewai import Crew,Task,Agent,Process
import json
from difflib import SequenceMatcher
import requests
from shared.helpers import print_state,workload_status_update
from shared.pydantic_models import RecipeData
from shared.supabase_client import supabase
from shared.constants import WORKLOAD_STATUSES,IMG_GEN_LIMIT

class PreProcessingFlow(Flow):
	def __init__(self, task_input,workload_id):
		super().__init__()
		# Save to state
		self.state['task_input'] = task_input
		self.state['workload_id'] = workload_id

		print("PreProcessingFlow constructor sucess ✅")
		print_state(self.state)

	# (1) Check if the input resembles a recipe
	@start()
	def validate_recipe(self):
		workload_status_update(WORKLOAD_STATUSES['validating_recipe'])

		validator_agent = Agent(
			role="Recipe Validator",
			goal="Decide if the given input text is a valid recipe",
			backstory="You're a culinary AI with expertise in identifying recipes from natural language text.",
			verbose=True
		)

		validation_task = Task(
			description=f"""
			You are given the following user input:
			{self.state['task_input']}

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
			workload_status_update(WORKLOAD_STATUSES['failed_not_recipe'])
			raise Exception(f"[Preprocess Worker] The input text does not resemble a recipe")
		
	# (2) Extract recipe data 
	@listen(validate_recipe)
	def extract_full_recipe(self):
		workload_status_update(WORKLOAD_STATUSES['extracting_recipe'])

		task_input = self.state['task_input']

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

			{task_input}

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
			workload_status_update(WORKLOAD_STATUSES['failed_overlimit'])
			raise Exception(f"[Preprocess Worker] The input exceeds image generation limit. Current limit is {IMG_GEN_LIMIT}")
		
		self.state['recipe_data'] = parsed_result
		print_state(self.state)
	
	# (3) Search for existing similar comics 
	@listen(extract_full_recipe)
	def search_existing_comics(self):
		workload_status_update(WORKLOAD_STATUSES['searching_comics'])

		recipe_data = self.state['recipe_data']
		previous_workloads = (
			supabase.table("workloads") 
			.select("*") 
			.eq("status", "completed_w_new") 
			.order("created_at", desc=True) 
			.limit(100) 
			.execute() 
			.data
    )
		similar = []

		for workload in previous_workloads:
			current_name = recipe_data.name.lower()
			prev_name = (workload["recipe_name"] or "").strip().lower()

			# String similarity for recipe_name
			name_score = SequenceMatcher(None, current_name, prev_name).ratio()

			# Ingredient overlap score
			current_ings = {ing.name.strip().lower() for ing in recipe_data.ingredients}
			prev_ings = {ing["name"].strip().lower() for ing in workload.get("ingredients", [])}
			if current_ings and prev_ings:
				ing_overlap = len(current_ings & prev_ings) / len(current_ings | prev_ings)
			else:
				ing_overlap = 0

			# Weighted score: prioritize exact name matches, ingredients as secondary
			score = (0.7 * name_score) + (0.3 * ing_overlap)

			if score > 0.85:  
				similar.append(workload["id"])

		if len(similar) != 0:
			# Update the DB record for the current workload
			supabase.table("workloads").update({
				"recipe_name": recipe_data.name,
				"ingredients": [{"name": ing.name,"quantity":ing.quantity} for ing in recipe_data.ingredients],
				"instructions": recipe_data.instructions,
				"similar_comics": similar[-3:],
				"status": WORKLOAD_STATUSES['awaiting_user_choice']
			}).eq("id", self.state["workload_id"]).execute()
		else: 
			# Update DB with recipe details
			supabase.table("workloads").update({
				"recipe_name": recipe_data.name,
				"ingredients": [{"name": ing.name,"quantity":ing.quantity} for ing in recipe_data.ingredients],
				"instructions": recipe_data.instructions
			}).eq("id", self.state["workload_id"]).execute()

			orchestrator_url = f"http://flask_orchestrator:5000/workloads/{self.state['workload_id']}/continue-flow"
			# Prepare payload
			payload = {
				"recipe_data": {
					"name": recipe_data.name,
					"ingredients": [{"name": ing.name, "quantity": ing.quantity} for ing in recipe_data.ingredients],
					"instructions": recipe_data.instructions
				}
			}

			try:
				response = requests.put(orchestrator_url, json=payload, timeout=10)
				response.raise_for_status()
			except Exception as e:
				raise Exception(f"\n[Preprocess Worker] Failed to call orchestrator: {e}")
			
		print("PreProcessingFlow completed ✅")
