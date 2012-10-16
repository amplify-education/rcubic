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
import logging

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
class XMLError(RuntimeError):
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

	def __init__(self, name="", jobpath=None, tree=None, xml=None, execiter=None, mustcomplete=False, subtree=None):
		Greenlet.__init__(self)
		if xml is not None:
			if xml.tag != "execJob":
				raise XMLError("Expect to find execJob in xml.")
			try:
				name = xml.attrib["name"]
				jobpath = xml.attrib.get("jobpath", None)
				uuidi = uuid.UUID(xml.attrib["uuid"])
				mustcomplete = xml.attrib.get("mustcomplete", False) == "True"
				subtreeuuid = xml.attrib.get("subtreeuuid", None)
			except KeyError:
				logging.error("Required xml attribute is not set")
				raise
			if jobpath == "":
				jobpath = None
			if tree is None and subtreeuuid is not None:
				raise JobUndefinedError(
					"The tree the job belongs to needs to be known so we can find subtree"
				)
			elif subtreeuuid is not None:
				subtreeuuid = uuid.UUID(subtreeuuid)
				subtree = tree.find_subtree(subtreeuuid, None)
				if subtree is None:
					raise TreeDefinedError("The referenced subtree cannot be found.")
		else:
			uuidi = uuid.uuid4()

		self.name = name
		self.uuid = uuidi
		self._tree = tree
		self.jobpath = jobpath
		self.execiter = execiter
		self.mustcomplete = mustcomplete
		if self.jobpath == "":
			self.state = self.STATE_IDLE
		else:
			self.state = self.STATE_UNDEF
		self._progress = -1
		self.override = False
		self.event = gevent.event.Event()
		self.subtree = subtree

	def xml(self):
		""" Generate xml Element object representing of ExecJob """
		args = {"name":str(self.name), "uuid":str(self.uuid.hex), "mustcomplete":str(self.mustcomplete)}
		if self.jobpath is not None:
			args["jobpath"] = str(self.jobpath)
		elif self.subtree is not None:
			args["subtreeuuid"] = str(self.subtree.uuid.hex)
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
		if (
				(self.jobpath is None and self.subtree is None)
				or
				(self.jobpath is not None and self.subtree is not None)
			):
			errors.append("subtree or jobpath must be set")

		if self.jobpath is not None:
			if not os.path.exists(self.jobpath):
				errors.append(
					"{0}File {1} for needed by job {2} does not exist."
					.format(prepend, self.jobpath, self.name)
				)
			else:
				if not os.access(self.jobpath, os.X_OK):
					errors.append(
						"{0}File {1} for needed by job {2} is not executable."
						.format(prepend, self.jobpath, self.name)
					)
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
		"""
		Returns true when job may start. That is all dependencies are fulfilled.
		"""
		logging.debug("processing may start for {0}".format(self.name))
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
		"""
		Create event, tell all parents to set it using rawlink. Wait untill event is set.
		"""
		self._waiter = gevent.event.Event()
		for event in self.parent_events():
			event.rawlink(self._parent_eselect_set)
		self._waiter.wait(timeout)
		gevent.sleep(1)
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

		while True:
			returncode = p.poll()
			if returncode is not None:
				break
			else:
				gevent.sleep(1)

		return returncode

	def reset(self):
		""" Prepares jobs to be executed again"""
		self.event.clear()
		self.state = self.STATE_IDLE

	def cancel(self):
		logging.debug("Cancel is invoked on {0}".format(self.name))
		if self.state == self.STATE_RUNNING:
			return False
		if self.state in self.DONE_STATES:
			return True
		logging.debug("Canceling {0}".format(self.name))
		self.state = self.STATE_CANCELLED
		self.event.set()
		return True

	def _run(self):
		if self.is_success():
			return False

		logging.debug("{0} is idling".format(self.name))
		while not self.may_start():
			self.parent_eselect()
		logging.debug("{0} is starting".format(self.name))

		#seconds = random.randrange(0, 100)
		#print("{0} started, will run for {1} seconds. ".format(self.name, seconds))
		#gevent.sleep(seconds)
		#print("{0} finised.".format(self.name))

		arguments = []
		arguments.append(self.jobpath)
		arguments.append(self.name)
		#arguments.append(`rcubic.port`)

		self.state = self.STATE_RUNNING
		#rcubic.refreshStatus(self)
		logging.debug("starting {0} {1}".format(self.name, arguments))
		if self.jobpath is not None:
			rcode = self._popen(
				arguments,
				cwd=self.tree.cwd,
			)
		elif self.subtree is not None:
			rcode = self.subtree.run()
		logging.debug("finished {0}".format(self.name))

		if rcode == 0:
			self.state = self.STATE_SUCCESSFULL
			self.event.set()
			return True
		else:
			self.state = self.STATE_FAILED
			self.event.set()
			return False

class ExecIter(object):
	def __init__(self, name=None, args=None):
		self.jobs = {}
		if args == None:
			self.args = []
		else:
			self.args = args
		self.run = 0
		self.valid = None
		self.name = name

	def increment(self, inc):
		if (self.run + inc) >= len(self.args):
			self.run += inc
		else:
			self.run = len(self.args)
		return self.run

	def argument(self):
		return self.args[self.run]

class ExecDependency(Greenlet):
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


class ExecTree(object):
	def __init__(self, xml=None):
		self.jobs = []
		self.deps = []
		self.subtrees = []
		if xml == None:
			self.uuid = uuid.uuid4()
			self.name = ""
			self.href = ""
			self.cwd = "/"
			self.workdir = "/tmp/{0}".format(self.uuid)
			self.iterator = None
		else:
			if xml.tag != "execTree":
				raise XMLError("Expect to find execTree in xml.")
			if xml.attrib["version"] != "1.0":
				raise XMLError("Tree config file version is not supported")
			self.name = xml.attrib.get("name", "")
			self.href = xml.attrib.get("href", "")
			self.uuid = uuid.UUID(xml.attrib["uuid"])
			self.cwd = xml.attrib.get("cwd", "/")
			#print("name:{0} href:{1} uuid:{2}".format(self.name, self.href, self.uuid))
			for xmlsubtree in xml.findall("execTree"):
				self.subtrees.append(ExecTree(xmlsubtree))
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
			if job.subtree is not None:
				eti.append(job.subtree.xml())
			#else:
			#	print("job {0} does not have a subtree.".format(job.name))
			eti.append(job.xml())
		for dep in self.deps:
			eti.append(dep.xml())
		return eti

	def __str__(self):
		return ("Subtree_{0}_{1}".format(self.name, self.uuid))

	def __getitem__(self, key, default=None):
		for job in self.jobs:
			if job.name == key:
				return job
		return default

	def find_subtree(self, uuid, default=None):
		for subtree in self.subtrees:
			if subtree.uuid == uuid:
				return subtree
		return default

	def find_jobs(self, needle, default=[]):
		""" Find all jobs based on their name / uuid """
		rval = [n for n in self.jobs if fnmatch.fnmatchcase(n.name, needle) or n.name.uuid.hex == needle]
		if rval:
			return rval
		else:
			return default

	def find_job(self, needle, default=None):
		""" Find job based on name or uuid """
		for job in self.jobs:
			if job.name == needle:
				return job
			elif job.uuid.hex == needle:
				return job
		return default

	def add_job(self, job):
		if self.find_job(job.name):
			raise jobDefinedError("Job with same name already part of tree")
		job.tree = self
		self.jobs.append(job)

	def add_dep(self, parent=None, child=None, state=ExecJob.STATE_SUCCESSFULL, nature=None, xml=None):
		if xml is not None:
			if xml.tag != "execDependency":
				raise XMLError("Expect to find execDependency in xml.")
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
					logging.warning("Implicitly adding job {0} to tree {1} via dependency.".format(k.name, self.name))
				except TreeDefinedError:
					raise JobUndefinedError("Job {0} is not part of the tree: {1}.".format(k.name, self.name))

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

	def advance(self):
		if self.iterator is not None:
			self.iterator.increment()
		for job in self.jobs:
			job.reset()

	def is_done(self):
		for job in self.jobs:
			if job.mustcomplete:
				if not job.is_done():
					return False
		return True

	def cancel(self):
		for job in self.jobs:
			job.cancel()

	def run(self, blocking=True):
		logging.debug("About to spin up jobs")
		for job in self.jobs:
			job.start()
		if blocking:
			logging.debug("Jobs have been spun up. I'm gonna chill")
			gevent.sleep(1)
			logging.debug("Chilling is done. Impatiently waiting for jobs to finish")
			self.join()
			logging.debug("Normalcy restored.")

	def join(self):
		for job in self.jobs:
			job.join()

