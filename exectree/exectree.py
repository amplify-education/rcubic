import uuid
import pydot
#import xml.etree.ElementTree as et
from lxml import etree as et
import gevent
from gevent import (Greenlet, event, socket)
import os
import random
from itertools import ifilter
from operator import methodcaller
import subprocess
import fcntl
import errno
import sys

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


class ExecJob(Greenlet):
	STATES = (0, 1, 2, 3, 4, 5)
	STATE_IDLE, STATE_RUNNING, STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED, STATE_UNDEF = STATES
	DEPENDENCY_STATES = [ STATE_SUCCESSFULL, STATE_FAILED ]
	DONE_STATES = [ STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED ]
	SUCCESS_STATES = [ STATE_SUCCESSFULL ]
	ERROR_STATES = [ STATE_SUCCESSFULL, STATE_CANCELLED ]

	STATE_COLORS = {
			STATE_IDLE:"white",
			STATE_RUNNING:"yellow",
			STATE_SUCCESSFULL:"green",
			STATE_FAILED:"red",
			STATE_CANCELLED:"blue",
			STATE_UNDEF:"gray"
	}


	def __init__(self, name="", jobpath="", tree=None, xml=None):
		Greenlet.__init__(self)
		if xml is not None:
			if xml.tag != "execJob":
				#TODO exception
				print("Error Tag is unmatched")
				return
			name = xml.attrib["name"]
			jobpath = xml.attrib["jobpath"]
			uuidi = uuid.UUID(xml.attrib["uuid"])
		else:
			uuidi = uuid.uuid4()

		self.name = name
		self.uuid = uuidi
		self._tree = tree
		self.jobpath = jobpath
		if self.jobpath == "":
			self.state = self.STATE_IDLE
		else:
			self.state = self.STATE_UNDEF
		self._progress = -1
		self.override = False
		self.event = gevent.event.Event()


	def xml(self):
		""" Generate xml Element object representing of ExecJob """
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
		""" Generate dot node object repersenting ExecJob """
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

	def parent_deps(self):
		deps = []
		for dep in self.tree.deps:
			if self == dep.child:
				deps.append(dep)
		return deps

	def child_deps(self):
		deps = []
		for dep in self.tree.deps:
			if self == dep.parent:
				deps.append(dep)
		return deps

	def children(self):
		return [dep.child for dep in self.child_deps()]

	def parents(self):
		return [dep.parent for dep in self.parent_deps()]

	def validate(self, prepend=""):
		errors = []
		if not os.path.exists(self.jobpath):
			errors.append("{0}File {1} for needed by job {2} does not exist.".format(prepend, self.jobpath, self.name))
		else:
			if not os.access(self.jobpath, os.X_OK):
				errors.append("{0}File {1} for needed by job {2} is not executable.".format(prepend, self.jobpath, self.name))
		return errors

	def is_done(self):
		return self.state in ExecJob.DONE_STATES

	def is_set(self):
		return self.event.is_set()

	def is_success(self):
		return self.state in ExecJob.SUCCESS_STATES

	def parent_events(self):
		return [ej.event for ej in self.parents()]

	def may_start(self):
		for dep in self.parent_deps():
			if dep.state != dep.parent.state:
				return False
			else:
				if dep.nature == ExecDependency.SUFFICIENT_NATURE:
					return True
		return True

	def _parent_eselect_set(self, instance):
		return self._waiter.set()

	def parent_eselect(self, timeout=None):
		self._waiter = gevent.event.Event()
		for parent in self.parents():
			parent.event.rawlink(self._parent_eselect_set)
		self._waiter.wait(timeout)
		#return ifilter(methodcaller('is_set'), parents)


	@staticmethod
	def _popen(args, data='', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=None):
		"""Communicate with the process non-blockingly.
		http://code.google.com/p/gevent/source/browse/examples/processes.py?r=23469225e58196aeb89393ede697e6d11d88844b

		This is to be obsoleted with gevent.spaw()
		"""
		p = subprocess.Popen(args, stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd)
		real_stdin = p.stdin if stdin == subprocess.PIPE else stdin
		fcntl.fcntl(real_stdin, fcntl.F_SETFL, os.O_NONBLOCK)  # make the file nonblocking
		real_stdout = p.stdout if stdout == subprocess.PIPE else stdout
		fcntl.fcntl(real_stdout, fcntl.F_SETFL, os.O_NONBLOCK)	# make the file nonblocking


		if data:
			bytes_total = len(data)
			bytes_written = 0
			while bytes_written < bytes_total:
				try:
					# p.stdin.write() doesn't return anything, so use os.write.
					bytes_written += os.write(p.stdin.fileno(), data[bytes_written:])
				except IOError:
					ex = sys.exc_info()[1]
					if ex.args[0] != errno.EAGAIN:
						raise
					sys.exc_clear()
				socket.wait_write(p.stdin.fileno())
			p.stdin.close()

		if stdout == subprocess.PIPE:
			while True:
				try:
					chunk = p.stdout.read(4096)
					if not chunk:
						break
				except IOError, ex:
					if ex[0] != errno.EAGAIN:
						raise
					sys.exc_clear()
				socket.wait_read(p.stdout.fileno())
			p.stdout.close()

		#output = ''.join(chunks)

		while True:
			returncode = p.poll()
			if returncode is not None:
				break
			else:
				gevent.sleep(1)

		return returncode

	def _run(self):
		if self.is_success():
			return False

		while not self.may_start():
			self.parent_eselect()

		#seconds = random.randrange(0, 100)
		#print("{0} started, will run for {1} seconds. ".format(self.name, seconds))
		#gevent.sleep(seconds)
		#print("{0} finised.".format(self.name))

		arguments = []
		arguments.append(self.jobpath)
		arguments.append(self.name)
		#arguments.append(`rcubic.port`)

		self.status = self.STATE_RUNNING
		#rcubic.refreshStatus(self)
		print("starting %s %s" % (self.name, arguments))
		rcode = self._popen(
			arguments,
			cwd=self.tree.cwd,
		)
		print("finished %s" % (self.name))

		if rcode == 0:
			self.state = self.STATE_SUCCESSFULL
			self.event.set()
			return True
		else:
			self.state = self.STATE_FAILED
			self.event.set()
			return False



class ExecDependency:
	NATURES = (0, 1)
	SUFFICIENT_NATURE, NECESSARY_NATURE = NATURES

	def __init__(self, parent, child, state=ExecJob.STATE_SUCCESSFULL, nature=None):
		self.parent = parent
		self.child = child

		if state in ExecJob.STATES:
			self.state = state
		else:
			raise UnknownStateError("Unknown State")

		if nature is None:
			#We accept None to make it easier to set/change default. 
			self.nature = ExecDependency.NECESSARY_NATURE
		elif nature in ExecDependency.NATURES:
			self.nature = nature
		else:
			raise UnknownStateError("Unknown Nature")

	def dot_edge(self):
		""" Generate dot edge object repersenting dependency """ 
		edge = pydot.Edge(self.parent.name, self.child.name)
		if self.nature == ExecDependency.NECESSARY_NATURE:
			if self.child.state == self.child.STATE_UNDEF:
				edge.set("color", "green")
			else:
				edge.set("color", "blue")
		else:
			if self.child.state == self.child.STATE_UNDEF:
				edge.set("color", "palegreen")
			else:
				edge.set("color", "paleblue")
		return edge

	def xml(self):
		""" Generate xml Element object representing the depedency """
		args = {"parent":self.parent.uuid.hex, "child":self.child.uuid.hex, "state":`self.state`, "nature":`self.nature`}
		eti = et.Element("execDependency", args)
		return eti


class ExecTree:
	def __init__(self, xml=None):
		self.jobs = []
		self.deps = []
		if xml == None:
			self.uuid = uuid.uuid4()
			self.name = ""
			self.href = ""
			self.cwd = "/"
			self.workdir = "/tmp/{0}".format(self.uuid)
		else:
			if xml.tag != "execTree":
				#TODO exception
				print("Error Tag is unmatched")
				return
			if xml.attrib["version"] != "1.0":
				#TODO exception
				print("Error version not supported")
				return
			self.name = xml.attrib.get("name", "")
			self.href = xml.attrib.get("href", "")
			self.uuid = uuid.UUID(xml.attrib["uuid"])
			self.cwd = xml.attrib.get("cwd", "/")
			#print("name:{0} href:{1} uuid:{2}".format(self.name, self.href, self.uuid))
			for xmljob in xml.findall("execJob"):
				self.jobs.append(ExecJob(tree=self, xml=xmljob))
			for xmldep in xml.findall("execDependency"):
				self.add_dep(xml=xmldep)

	def xml(self):
		args = {
			"version":"1.0",
			"name":self.name,
			"href":self.href,
			"uuid":self.uuid.hex,
			"cwd":self.cwd
		}
		eti = et.Element("execTree", args)
		for job in self.jobs:
			eti.append(job.xml())
		for dep in self.deps:
			eti.append(dep.xml())
		return eti

	def __getitem__(self, key):
		for job in self.jobs:
			if job.name == key:
				return job

	def find_jobs(self, needle, default=[]):
		""" Find all jobs based on their name / uuid """
		rval = [n for n in self.jobs if fnmatch.fnmatchcase(n.name, needle) or n.name.uuid.hex == needle]
		if rval:
			return rval
		else:
			return default

	def find_job(self, needle):
		""" Find job based on name or uuid """
		for job in self.jobs:
			if job.name == needle:
				return job
			elif job.uuid.hex == needle:
				return job
		return None

	def add_job(self, job):
		if self.find_job(job.name):
			raise jobDefinedError("Job with same name already part of tree")
		job.tree = self
		self.jobs.append(job)

	def add_dep(self, parent=None, child=None, state=ExecJob.STATE_SUCCESSFULL, nature=None, xml=None):
		if xml is not None:
			if xml.tag != "execDependency":
				#TODO exception
				print("Error Tag is unmatched")
				return
			parent = xml.attrib["parent"]
			child = xml.attrib["child"]
			state = int(xml.attrib["state"])
			nature = int(xml.attrib["nature"])
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

		dep = ExecDependency(parent, child, state, nature)
		self.deps.append(dep)

	def dot_graph(self):
		graph = pydot.Dot(graph_type="graph")
		for job in self.jobs:
			graph.add_node(job.dot_node())
		for dep in self.deps:
			graph.add_edge(dep.dot_edge())
		return graph

	def stems(self):
		"""
		Finds and returns first job of most unconnected graphs

		WARNING This will not find stem of subtrees with cycles
		"""
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

			for job in self.jobs:
				errors.extend(job.validate())

		return errors


	def validate_nocycles(self, job, visited, parents=None):
		""" Ensure we do not have cyclical dependencies in the tree """
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

	def run(self):
		print("About to spin up jobs")
		#TODO this class is for testing only!!!!
		for job in self.jobs:
			job.start()
		print("Jobs have been spun up. I'm gonna chill")
		#gevent.sleep(5)
		print("Chilling is done. Impatiently waiting for jobs to finish")
		for job in self.jobs:
			job.join()
		print("Normalcy restored.")

