#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from src.crewai_recipe_comic_generator.crew import ComicGenFlow,PreProcessingFlow

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run(input_text):
    """
    Run the crew.
    """
    
    try:
        pre_process_flow = PreProcessingFlow(flow_input=input_text)
        parsed_input = pre_process_flow.kickoff()

        comic_gen_flow = ComicGenFlow(flow_input=parsed_input)
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
