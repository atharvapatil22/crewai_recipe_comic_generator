#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from crewai_recipe_comic_generator.crew import ComicGenFlow

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run(input_text):
    """
    Run the crew.
    """
    # mock_flow_input = {
    # "cleaned_recipe_data": {
    #     "name": "Veggie Sandwich",
    #     "ingredients": [
    #         {"name": "bread slices", "quantity": "2 pieces"},
    #         {"name": "lettuce", "quantity": "2 leaves"},
    #         {"name": "tomato", "quantity": "4 slices"},
    #     ],
    #     "instructions": [
    #         "Spread mayonnaise on one side of each bread slice.",
    #         "Layer lettuce, tomato, cucumber, and cheese slice on one bread slice.",
    #     ]
    # }
# }
    
    try:
        # Generate flow input from preprocess flow
        flow_input = input_text
        comic_gen_flow = ComicGenFlow(flow_input=flow_input)
        result = comic_gen_flow.kickoff()
        return result

    except Exception as e:
        raise Exception(f"[Application Exception] An error occurred while running the crew: {e}")


# def train():
#     """
#     Train the crew for a given number of iterations.
#     """
#     inputs = {
#         "topic": "AI LLMs"
#     }
#     try:
#         CrewaiRecipeComicGenerator().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

#     except Exception as e:
#         raise Exception(f"An error occurred while training the crew: {e}")

# def replay():
#     """
#     Replay the crew execution from a specific task.
#     """
#     try:
#         CrewaiRecipeComicGenerator().crew().replay(task_id=sys.argv[1])

#     except Exception as e:
#         raise Exception(f"An error occurred while replaying the crew: {e}")

# def test():
#     """
#     Test the crew execution and returns the results.
#     """
#     inputs = {
#         "topic": "AI LLMs"
#     }
#     try:
#         CrewaiRecipeComicGenerator().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

#     except Exception as e:
#         raise Exception(f"An error occurred while testing the crew: {e}")
