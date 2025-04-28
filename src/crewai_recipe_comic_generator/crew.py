from crewai.flow.flow import Flow, listen, start


class ExampleFlow(Flow):
	def __init__(self, flow_input):
		super().__init__()
		print("finished init without processing input")

	@start()
	def fun1(self):
		print("inside fun1")

		return "fun1_output"

	@listen(fun1)
	def fun2(self):
		print("inside fun2")

		return "fun2_output"