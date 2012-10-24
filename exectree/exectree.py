import uuid
import pydot
#import xml.etree.ElementTree as et
from lxml import etree as et
import gevent
from gevent import (Greenlet, event, socket)
import os
import random
#from itertools import ifilter
#from operator import methodcaller
import subprocess
import fcntl
import errno
import sys
import logging

class TreeDefinedError(RuntimeError):
	pass
class JobDefinedError(RuntimeError):
	pass
class JobError(RuntimeError):
	pass
class JobUndefinedError(RuntimeError):
	pass
class UnknownStateError(RuntimeError):
	pass
class DependencyError(RuntimeError):
	pass
class XMLError(RuntimeError):
	pass
class IterratorOverrunError(RuntimeError):
	pass


#class ExecJob(Greenlet):
class ExecJob(object):
	STATES = (0, 1, 2, 3, 4, 5, 6)
	STATE_IDLE, STATE_RUNNING, STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED, STATE_UNDEF, STATE_RESET = STATES
	DEPENDENCY_STATES = [ STATE_SUCCESSFULL, STATE_FAILED ]
	DONE_STATES = [ STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED, STATE_UNDEF ]
	SUCCESS_STATES = [ STATE_SUCCESSFULL, STATE_UNDEF ]
	ERROR_STATES = [ STATE_SUCCESSFULL, STATE_CANCELLED ]
	PRESTART_STATES = [ STATE_IDLE, STATE_UNDEF ]
	UNDEF_JOB = "-"

	STATE_COLORS = {
			STATE_IDLE:"white",
			STATE_RUNNING:"yellow",
			STATE_SUCCESSFULL:"green",
			STATE_FAILED:"red",
			STATE_CANCELLED:"blue",
			STATE_UNDEF:"gray"
	}

	def __init__(self, name="", jobpath=None, tree=None, logfile=None, xml=None, execiter=None, mustcomplete=True, subtree=None):
		#Greenlet.__init__(self)
		if xml is not None:
			if xml.tag != "execJob":
				raise XMLError("Expect to find execJob in xml.")
			try:
				name = xml.attrib["name"]
				jobpath = xml.attrib.get("jobpath", None)
				uuidi = uuid.UUID(xml.attrib["uuid"])
				mustcomplete = xml.attrib.get("mustcomplete", False) == "True"
				subtreeuuid = xml.attrib.get("subtreeuuid", None)
				logfile = xml.attrib.get("logfile", None)
			except KeyError:
				logging.error("Required xml attribute is not set")
				raise
			if logfile == "":
				logfile = None
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
		self.state = self.STATE_IDLE
		self.subtree = subtree
		self.jobpath = jobpath
		self.execiter = execiter
		self.mustcomplete = mustcomplete
		self.logfile = logfile
		self._progress = -1
		self.override = False
		self.events = {}
		for e in self.DONE_STATES:
			self.events[e] = gevent.event.Event()

	def xml(self):
		""" Generate xml Element object representing of ExecJob """
		args = {"name":str(self.name), "uuid":str(self.uuid.hex), "mustcomplete":str(self.mustcomplete)}
		if self.jobpath is not None:
			args["jobpath"] = str(self.jobpath)
		elif self.subtree is not None:
			args["subtreeuuid"] = str(self.subtree.uuid.hex)
		if self.logfile is None:
			args["logfile"] = ""
		else:
			args["logfile"] = self.logfile
		eti = et.Element("execJob", args)
		return eti

	def __str__(self):
		str="Job:{0} Tree:{1} UUID:{2} path:{3}".format(self.name, self.uuid, self.tree, self.jobpath)

	#TODO: setter for sub tree to ensure only subtrees are iterable

	@property
	def jobpath(self):
		return self._jobpath

	@jobpath.setter
	def jobpath(self, value):
		if self.subtree is not None and value is not None:
			raise JobError("jobpath cannot be used if subtree is set")
		if self.state in self.PRESTART_STATES:
			self._jobpath = value
			if value == self.UNDEF_JOB and self.state == self.STATE_IDLE:
				self.state = self.STATE_UNDEF
		else:
			raise JobError("jobpath cannot be modified after job has been started")

	@property
	def state(self):
		return self._state

	@state.setter
	def state(self, value):
		self._state = value
		if self._state in self.DONE_STATES:
			self.events[self._state].set()

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

	def _dot_node(self):
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

	def _dot_tree(self):
		subg = pydot.Subgraph(
				self.subtree.cluster_name,
				color = "blue",
			)
		if self.subtree.iterator is None:
			subg.set_label(self.name)
		else:
			subg.set_label("{0} {1}/{2}".format(self.name, self.subtree.iterator.run, self.subtree.iterator.len()))
		logging.debug(subg.to_string())
		self.subtree.dot_graph(subg)
		return subg

	def dot(self, graph):
		""" Generate dot object representing ExecJob """
		if self.jobpath is not None:
			rep = self._dot_node()
			graph.add_node(rep)
		elif self.subtree is not None:
			rep = self._dot_tree()
			graph.add_subgraph(rep)
			graph.set_compound("True")

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
		if self.jobpath is not None and self.subtree is not None:
			errors.append("subtree and jobpath of {0} are set. Only one can be set.")
		elif self.jobpath is not None:
			if self.jobpath == self.UNDEF_JOB:
				#We allow existance of no-op jobs
				pass
			elif not os.path.exists(self.jobpath):
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
		elif self.subtree is not None:
			errors.extend(self.subtree.validate())
		else:
			errors.append("subtree or jobpath of {0} must be set.")

		return errors

	def is_done(self):
		return self.state in ExecJob.DONE_STATES

	def is_success(self):
		return self.state in ExecJob.SUCCESS_STATES

	def is_cancelled(self):
		return self.state == ExecJob.STATE_CANCELLED

	def _parent_wait(self):
		for dep in self.parent_deps():
			dep.wait()

	@staticmethod
	def _popen(args, data='', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=None):
		"""Communicate with the process non-blockingly.
		http://code.google.com/p/gevent/source/browse/examples/processes.py?r=23469225e58196aeb89393ede697e6d11d88844b

		This is to be obsoleted with gevent subprocess
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
		for key in self.events.iterkeys():
			self.events[key].clear()
		self.state = self.STATE_RESET
		logging.debug("job {0} has been reset.".format(self.name))

	def cancel(self):
		logging.debug("Cancel is invoked on {0}".format(self.name))
		if self.state == self.STATE_RUNNING:
			return False
		if self.state in self.DONE_STATES:
			return True
		logging.debug("Canceling {0}".format(self.name))
		self.state = self.STATE_CANCELLED
		return True

	def start(self):
		g = Greenlet.spawn(self._run)

	def _run(self):
		if self.is_success():
			return False

		logging.debug("{0} is idling ({1})".format(self.name, self.state))
		self._parent_wait()
		if self.state in self.DONE_STATES:
			return None
		logging.debug("{0} is starting".format(self.name))

		self.state = self.STATE_RUNNING
		#rcubic.refreshStatus(self)
		if self.jobpath is not None:
			arguments = []
			arguments.append(self.jobpath)
			arguments.append(self.name)
			arguments.append(self.tree.argument())
			logging.debug("starting {0} {1}".format(self.name, arguments))
			if self.logfile is not None:
				with open(self.logfile, 'a') as fd:
					rcode = self._popen(
						arguments,
						cwd=self.tree.cwd,
						stdout=fd,
						stderr=fd
					)
			else:
				rcode = self._popen(
					arguments,
					cwd=self.tree.cwd
				)
		elif self.subtree is not None:
			logging.debug("starting {0} {1}".format(self.name, "subtree"))
			rcode = self.subtree.iterrun()
			#TODO: compute rcode
			logging.warning("Sub tree is not checked for success before proceeding")
			rcode = 0
		logging.debug("finished {0} status {1}".format(self.name, rcode))

		if rcode == 0:
			self.state = self.STATE_SUCCESSFULL
			return True
		else:
			self.state = self.STATE_FAILED
			return False

class ExecIter(object):
	def __init__(self, name=None, args=None):
		if args == None:
			self.args = []
		else:
			self.args = args
		self.run = 1
		self.valid = None
		self.name = name

	def is_exhausted(self):
		if self.run >= len(self.args):
			return True
		return False

	def len(self):
		return len(self.args)

	def increment(self, inc=1):
		if (self.run + inc) >= len(self.args):
			self.run = len(self.args)
		else:
			self.run += inc
		return self.run

	@property
	def argument(self):
		if self.run <= 1 and len(self.args)  < 1:
			return ""
		elif self.run > len(self.args):
			raise IterratorOverrunError("Iterator has no more elements")
		else:
			return self.args[self.run-1]

class ExecDependency(object):
	def __init__(self, parent, child, state=ExecJob.STATE_SUCCESSFULL):
		self.parent = parent
		self.child = child

		if state in ExecJob.STATES:
			self.state = state
		else:
			raise UnknownStateError("Unknown State")

	def _dot_add(self, parent_target, child_target, graph):
		edge = pydot.Edge(parent_target, child_target)
		if self.child.state == self.child.STATE_UNDEF:
			edge.set("color", "palegreen")
		else:
			edge.set("color", "paleblue")
		if parent_target is None:
			parent_target = "None"
		if child_target is None:
			child_target = "None"
		logging.debug("dep: {0} -> {1}".format(parent_target, child_target))
		graph.add_edge(edge)
		return edge

	def dot(self, graph):
		""" Generate dot edge object repersenting dependency """

		if self.parent.subtree is not None and self.child.subtree is not None:
			#This is a bit tricky we need to loop 2x but the real problems is that it will look UGLY
			raise NotImplementedError("Dependency between 2 subtrees is not implemented")

		parent_target = self.parent.name
		child_target = self.child.name
		if self.parent.subtree is not None:
			for leaf in self.parent.subtree.leaves():
				e = self._dot_add(leaf.name, child_target, graph)
				e.set_ltail(self.parent.subtree.cluster_name)
		elif self.child.subtree is not None:
			for stem in self.child.subtree.stems():
				e = self._dot_add(parent_target, stem.name, graph)
				e.set_lhead(self.child.subtree.cluster_name)
		else:
			self._dot_add(parent_target, child_target, graph)

	def wait(self):
		self.parent.events[self.state].wait()

	def xml(self):
		""" Generate xml Element object representing the depedency """
		args = {"parent":self.parent.uuid.hex, "child":self.child.uuid.hex, "state":`self.state`}
		eti = et.Element("execDependency", args)
		return eti


class ExecTree(object):
	def __init__(self, xml=None):
		self.jobs = []
		self.deps = []
		self.subtrees = []
		self.done_event = gevent.event.Event()
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

	@property
	def cluster_name(self):
		#pydot does not properly handle space in subtree
		name = self.name.replace(" ", "_")
		return "cluster_{0}".format(name)

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

	def add_dep(self, parent=None, child=None, state=ExecJob.STATE_SUCCESSFULL, xml=None):
		if xml is not None:
			if xml.tag != "execDependency":
				raise XMLError("Expect to find execDependency in xml.")
			parent = xml.attrib["parent"]
			child = xml.attrib["child"]
			state = int(xml.attrib["state"])
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

		dep = ExecDependency(parent, child, state)
		self.deps.append(dep)

	def argument(self):
		if self.iterator is None:
			return ""
		else:
			return self.iterator.argument

	def dot_graph(self, graph = None):
		if graph is None:
			graph = pydot.Dot(graph_type="digraph")
		for job in self.jobs:
			job.dot(graph)
		for dep in self.deps:
			dep.dot(graph)
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

	def leaves(self):
		"""
		Finds and returns all the leaf jobs of a tree
		"""
		leaves = []
		for job in self.jobs:
			leaf = True
			for dep in self.deps:
				if job == dep.parent:
					leaf = False
					break
			if leaf:
				leaves.append(job)
		return leaves

	def validate(self):
		errors = []
		stems = self.stems()

		if len(stems) == 0:
			errors.append("Tree {0} has 0 stems, must be empty.".format(self.name, stems))
		elif len(stems) > 1:
			errors.append("Tree {0} has multiple stems ({1}).".format(self.name, stems))

		for stem in stems:
			visited = []

			#do we have cycles?
			cycles = not self.validate_nocycles(stem, visited)
			if cycles:
				errors.append("Tree {0} has cycles.".format(self.name))

			#ensure that all jobs are connected
			for job in self.jobs:
				if job not in visited:
					errors.append("Not all jobs are connected within {0}.".format(self.name))
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

	def _is_done_event(self, instance):
		logging.debug("Are we done yet?")
		self.is_done()

	def is_done(self):
		for job in self.jobs:
			if job.mustcomplete:
				if not job.is_done():
					logging.debug("{0} is not done".format(job.name))
					return False
		logging.debug("Yes, we are done.")
		self.done_event.set()
		self.cancel()
		return True

	def cancel(self):
		for job in self.jobs:
			job.cancel()

	def run(self, blocking=True):
		logging.debug("About to spin up jobs for {0}".format(self.name))
		for job in self.jobs:
			for ek, ev in job.events.items():
				ev.rawlink(self._is_done_event)
			job.start()
		if blocking:
			logging.debug("Jobs have been spun up for {0}. I'm gonna chill".format(self.name))
			gevent.sleep(1)
			logging.debug("Chilling is done. Impatiently waiting for jobs of {0} to finish".format(self.name))
			#self.join()
			self.done_event.wait()
			logging.debug("Tree {0} has finished execution.".format(self.name))

	def advance(self):
		logging.debug("Advancing tree {0}.".format(self.name))
		self.done_event.clear()
		if self.iterator is not None:
			self.iterator.increment()
		for job in self.jobs:
			job.reset()

	def iterrun(self):
		if self.iterator is None:
			self.run()
			return None
		if self.iterator.is_exhausted():
			return False
		while True:
			self.run()
			if self.iterator.is_exhausted():
				break
			self.advance()

	def join(self):
		for job in self.jobs:
			job.join()

