import uuid
import pydot

class ExecForest:
	def __init__(self):
		#todo enforce that we only have one forest
		self.trees = []

	def add_tree(self, tree):
		self.trees.append(tree)
