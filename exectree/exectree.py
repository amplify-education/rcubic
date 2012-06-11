import uuid
import pydot
#import xml.etree.ElementTree as et
from lxml import etree as et

class TreeDefinedError(RuntimeError):
	pass
class JobDefinedError(RuntimeError):
	pass
class JobUndefinedError(RuntimeError):
	pass
class UnknownStateError(RuntimeError):
	pass
class DependencyError(RuntimeError):
	pass

class ExecJob:
	STATES = (0, 1, 2, 3, 4, 5)
	STATE_IDLE, STATE_RUNNING, STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED, STATE_UNDEF = STATES
	DEPENDENCY_STATES = [STATE_SUCCESSFULL, STATE_FAILED]
	STATE_COLORS = {
			STATE_IDLE:"white",
			STATE_RUNNING:"yellow",
			STATE_SUCCESSFULL:"green",
			STATE_FAILED:"red",
			STATE_CANCELLED:"blue",
			STATE_UNDEF:"gray"
		}


	def __init__(self, name="", jobpath="", tree=None):
		self.name = name
		self.uuid = uuid.uuid4()
		self._tree = tree
		self.jobpath = jobpath
		if self.jobpath == "":
			self.state = self.STATE_IDLE
		else:
			self.state = self.STATE_UNDEF
		self._progress = -1
		self.override = False

	def xml(self):
		args = {"name":self.name, "uuid":self.uuid.hex, "jobpath":self.jobpath}
		eti = et.Element("execJob", args)
		return eti

	def __str__(self):
		str="Job:{0} Tree:{1} UUID:{2} path:{3}".format(self.name, self.uuid, self.tree, self.jobpath)

	@property
	def tree(self):
		return self._tree

	@tree.setter
	def tree(self, value):
		if self._tree is None:
			self._tree = value
		else:
			raise TreeDefinedError("Job already belongs to a tree")

	@property
	def progress(self):
		return self._progress

	@progress.setter
	def progress(self, value):
		if value >= 0 and value <= 100:
			self._progress = value

	def dot_node(self):
		if self.progress >= 0:
			label = "{0}\n{1}".format(self.name, self.progress)
		else:
			label = self.name
		node = pydot.Node(
			label,
			style = "filled",
			fillcolor = self.STATE_COLORS[self.state]
			)
		if self.tree.href:
			node.set("labelhref", 'foo')
			node.set("href", "{0}{1}".format(self.tree.href,self.name))
		return node

	def children(self):
		children = []
		for dep in self.tree.deps:
			if self == dep.parent:
				children.append(dep.child)
		return children

class ExecDependency:
	def __init__(self, parent, child, state=ExecJob.STATE_SUCCESSFULL):
		self.parent = parent
		self.child = child
		if state in ExecJob.STATES:
			self.state = state
		else:
			raise UnknownStateError("Unknown State")
	def dot_edge(self):
		edge = pydot.Edge(self.parent.name, self.child.name)
		if self.child.state == self.child.STATE_UNDEF:
			edge.set("color", "palegreen")
		else:
			edge.set("color", "blue")
		return edge

	def xml(self):
		args = {"parent":self.parent.uuid.hex, "child":self.child.uuid.hex, "state":`self.state`}
		eti = et.Element("execDependency", args)
		return eti


class ExecTree:
	def __init__(self, xml=None):
		if xml == None:
			self.jobs = []
			self.deps = []
			self.uuid = uuid.uuid4()
			self.name = ""
			self.href = ""
		else:
			self._from_xml(xml)

	def __getitem__(self, key):
		for job in self.jobs:
			if job.name == key:
				return job

	def find_jobs(self, name, default=[]):
		rval = [n for n in self.jobs if fnmatch.fnmatchcase(n.name, name)]
		if rval:
			return rval
		else:
			return default

	def find_job(self, name):
		for job in self.jobs:
			if job.name == name:
				return job
		return None

	def add_job(self, job):
		if self.find_job(job.name):
			raise jobDefinedError("Job with same name already part of tree")
		job.tree = self
		self.jobs.append(job)

	def add_dep(self, parent, child, state=ExecJob.STATE_SUCCESSFULL):
		#Ensure parent and child are ExecJobs
		if not isinstance(parent, ExecJob):
			parent = self.find_job(parent)
		if not isinstance(child, ExecJob):
			child = self.find_job(child)

		if parent is child:
			raise DependencyError("Child cannot be own parent ({0}).".format(parent.name))

		#Parent and Child must be members of the tree
		for k in [child, parent]:
			if k not in self.jobs:
				try:
					self.add_job(k)
				except TreeDefinedError:
					raise JobUndefinedError("Job {0} is not part of the tree {1}".format(k, tree))

		dep = ExecDependency(parent, child, state)
		self.deps.append(dep)

	def dot_graph(self):
		graph = pydot.Dot(graph_type="graph")
		for job in self.jobs:
			graph.add_node(job.dot_node())
		for dep in self.deps:
			graph.add_edge(dep.dot_edge())
		return graph

	def xml(self):
		args = {
			"version":"1.0",
			"name":self.name,
			"href":self.href,
			"uuid":self.uuid.hex
		}
		eti = et.Element("execTree", args)
		for job in self.jobs:
			eti.append(job.xml())
		for dep in self.deps:
			eti.append(dep.xml())
		return eti

	def _from_xml(self, xml):
		#TODO here
		if xml.tag != "execTree":
			#TODO exception
			print("Errror version not supported")
			return
		if xml.attrib["version"] != "1.0":
			#TODO exception
			print("Errror version not supported")
			return
		self.name = xml.attrib["name"]
		self.href = xml.attrib["href"]
		self.uuid = uuid.UUID(xml.attrib["uuid"])
		print("name:{0} href:{1} uuid:{2}".format(self.name, self.href, self.uuid))
		help(xml.find)
		for job in xml.find("execJob"):
			print(job.tag)
			print("here0")
		print("here1")


	def stems(self):
		""" WARNING This will not find stem of subtrees with cycles"""
		stems = [] 
		for job in self.jobs:
			orphan = True
			for dep in self.deps:
				if job == dep.child:
					#print("{0} -> {1}".format(dep.parent.name, job.name))
					orphan = False
					break
			#print("working on: {0}".format(job.name))
			if orphan:
				#print("appending")
				stems.append(job)
		return stems

	def validate(self):
		errors = []
		stems = self.stems()

		if len(stems) == 0:
			errors.append("Tree has 0 stems, must be empty.".format(stems))
		elif len(stems) > 1:
			errors.append("Tree has multiple stems ({0}).".format(stems))

		for stem in stems:
			visited = []

			#do we have cycles?
			cycles = not self.validate_nocycles(stem, visited)
			if cycles:
				errors.append("Tree has cycles.")
		
			#ensure that all jobs are connected
			for job in self.jobs:
				if job not in visited:
					errors.append("Not all jobs are connected.")
					break

		return errors


	def validate_nocycles(self, job, visited, parents=None):
		if parents is None:
			parents = []
		#print("validate job: {0} (parents:{1} children:{2})".format(job.name, [v.name for v in parents], [c.name for c in job.children()]))
		if job in parents:
			return False
		parents.append(job)
		if job not in visited:
			visited.append(job)
		for child in job.children():
			 if not self.validate_nocycles(child, visited, parents):
				return False
		parents.remove(job)
		return True
