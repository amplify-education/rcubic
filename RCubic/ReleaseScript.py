import os, re, gevent, subprocess, logging, fnmatch
import simplejson
from RCubic.ScriptStatus import Status
from RCubic.RCubicUtilities import popenNonblock, ConfigurationError, FatalRuntimeError

import logging

class ReleaseScriptManager(object):
	def __init__(self, rcubic):
		self.releaseScripts = []
		self.specialJobs = []
		self.gparentCompileSuccess = None
		self.longestName = 0
		self.groups = []
		self.rcubic = rcubic

	def __iter__(self):
		return iter(self.releaseScripts)

	def __str__(self):
		str = "ReleaseScriptManager:\n"
		for releaseScript in self.releaseScripts:
			str += "\t%s\n" %(releaseScript)
		return str

	def remove(self, releaseScript):
		try:
			self.releaseScripts.remove(releaseScript)
			return True
		except KeyError:
			return False

	def add(self, releaseScript):
		tmp = self.find(releaseScript.name)
		if tmp:
			self.remove(tmp)
			logging.info("overriding %s" %(releaseScript.name))
			releaseScript.setOverride()
		self.releaseScripts.append(releaseScript)
		if len(releaseScript.name) > self.longestName:
			self.longestName = len(releaseScript.name)

	def findall(self, name, default=[]):
		rval = [n.name for n in self.releaseScripts if fnmatch.fnmatchcase(n.name, name)]
		if rval:
			return rval
		else:
			return default

	def find(self, name):
		for releaseScript in self.releaseScripts:
			if releaseScript.name == name:
				return releaseScript
		return None

	def findPhase(self, phase):
		rs = []
		for releaseScript in self.releaseScripts:
			if releaseScript.phase == phase:
				rs.append(releaseScript.name)
		return rs

	def expandglobs(self):
		for rs in self.releaseScripts:
			for deps in [rs.sdep, rs.cdep]:
				for dep in deps:
					matches = self.findall(dep)
					if matches:
						deps.remove(dep)
						deps.extend(matches)

	def convertcdep(self):
		"""Convert all cdeps to sdeps"""
		for script in self.releaseScripts:
			for cdep in script.cdep:
				dep = self.find(cdep)
				if dep is not None:
					dep.sdep.append(script.name)

	def inferParents(self):
		#TODO remove outer loop, throw into dict.
		for phase in ReleaseScript.Phase.all:
			inferredParents = self.findPhase(ReleaseScript.Phase.prev(phase))
			for script in self.releaseScripts:
				if script.phase == phase:
					script.idep.extend(inferredParents)

	def addGroup(self, dir, group, version, phase, filter=None):
		if filter is None:
			filter = {}
		count = 0
		if not os.path.exists("%s/%s" %(dir, group)):
			return count
		for file in os.listdir("%s/%s" %(dir, group)):
			if file.startswith("%s_" %(group)):
				#if filter is set see if file is in either positive or negative filter and select it accordingly
				if (not filter) \
					or (filter["positiveFilter"] and file in filter["files"]) \
					or (not filter["positiveFilter"] and file not in filter["files"]):
					self.add(ReleaseScript("%s/%s/%s" %(dir, group, file), version, phase, self))
					count += 1
		self.groups.append(group)
		return count

	def toDot(self, url=None, basePathTrimLen=0, arborescent=False):
		str = ""
		for releaseScript in self.releaseScripts:
			str += "%s\n" %(releaseScript.toDotNode(url, basePathTrimLen))
		for releaseScript in self.releaseScripts:
			str += "%s\n" %(releaseScript.toDotEdge(arborescent))
		return "digraph G {\ngraph [bgcolor=transparent];\n%s}" %(str)

	def toJSON(self, arborescent=False):
		nodes = { }
		for releaseScript in self.releaseScripts:
			name, color, progress, others = releaseScript.toJSONNode(arborescent)
			nodes[name] = {}
			nodes[name]["status"] = color
			nodes[name]["progress"] = progress
			for o in others:
				name, color, progress = o
				if not name in nodes:
					nodes[name] = {}
					nodes[name]["status"] = color
					nodes[name]["progress"] = progress
		return simplejson.dumps(nodes)

	def isDAG(self):
		"""Checks to ensure scripts are arranged in Directed Acyclic Graph.
		Cyclicality is tested by gparent compile so we just need to check that
		graph is connected"""
		firstJobs = []
		for rs in self.releaseScripts:
			if [dep for dep in rs.hdep + rs.sdep + rs.idep if self.find(dep)]:
				#script has some 'active' dependencies.
				rs.dagPass = True
			else:
				logging.debug("gparents of %s: %s" %(rs.name, rs.gparent))
				firstJobs.append(rs.name)
				if rs.name in self.specialJobs:
					rs.dagPass = True
		if len(firstJobs) > 1:
			logging.debug("DAG is disconnected. First jobs: %s" % firstJobs)
			return False
		return True

	def validate(self):
		errorMessages = ""

		for releaseScript in self.releaseScripts:
			errorMessage = releaseScript.validate()
			if errorMessage:
				errorMessages += "%s" %(errorMessage)

		if not self.gparentCompileSuccess:
			errorMessages += "\tFailed recusion check for cycles in dependencies.\n"
			#When we hit this state the other validation information is not very reliable

		if len(self.specialJobs) == 0:
			raise FatalRuntimeError("ERROR: special jobs must be set before validation")

		if not self.isDAG():
			errorMessages += "\tDAG is violated:\n"
			for rs in self.releaseScripts:
				if not rs.dagPass:
					errorMessages += "\t\t%s\n" %rs.name

		if errorMessages == "":
			return True
		else:
			return errorMessages

	def isDone(self):
		for rs in self.releaseScripts:
			if not rs.isDone():
					return False
		return True

	def isSuccess(self):
		for rs in self.releaseScripts:
			if not rs.isSuccess():
					return False
		return True

	def isGroupSuccess(self, group):
		for rs in self.releaseScripts:
			if rs.group == group:
				if not rs.isSuccess():
						return False
		return True

	def countGroups(self, excludes):
		counted = []
		for rs in self.releaseScripts:
			if rs.group in counted:
				continue
			if rs.group in excludes:
				continue
			counted.append(rs.group)
		return len(counted)

	def gparentCompile(self):
		try:
			for rs in self.releaseScripts:
				rs.gparentCompile()
			self.gparentCompileSuccess = True
			return True
		except RuntimeError:
			#Lazy mans cycle detection
			self.gparentCompileSuccess = False
			return False

	def queueJobs(self):
		for rs in self.releaseScripts:
			rs.initEvents()
		return [rs.queue for rs in self.releaseScripts]

	def abortJobs(self):
		for rs in self.releaseScripts:
			if rs.status == Status.QUEUED or rs.status == Status.BLOCKED:
				rs.status = Status.CANCELLED
			#we must clear all events to ensure jobs are flushed out
			rs.event.set()

#AKA AIS
class ReleaseScript(object):
	class Phase(dict):
		all = ("EARLY", "DEFAULT", "LATE", "NONE")
		EARLY, DEFAULT, LATE, NONE = all

		@classmethod
		def prev(cls, phase):
			return cls.all[cls.all.index(phase)-1]

	def __init__(self, script, version, phase, manager):
		self.script = script
		#TODO deps should be converted to a dict see adep()
		self.hdep = [] #hard dependency
		self.sdep = [] #soft dependency
		self.idep = [] #inferred dependency
		self.cdep = [] #child dependencies
		self.resources = [] #needed resources
		self.gparent = []
		self.products = []
		self.override = False
		self._status = Status.NONE
		self.version = version
		self.containsTrap = False
		self.regexok = False
		self.dagPass = None
		self.validSyntax = None
		self.isExecutable = False
		self.group = ""
		self.name = ""
		self.progress = -1
		self.phase = phase
		self.monitoredEvents = []
		self.event = gevent.event.Event()
		self.stdout = ""
		self.hasFailed = False
		self.manager = manager
		self.gitHead = ""
		self.nodeColors = {Status.STARTED:'yellow', Status.SUCCEEDED:'green', Status.FAILED:'red', Status.CANCELLED:'blue', Status.MANUALOVERRIDE:'pink', Status.BLOCKED:'darkorange'}

		regexName = re.compile("[^/]*$")
		matchName = regexName.search(script)
		if not matchName:
			raise ConfigurationError("Error: Could not determine AIS name from '%s'." %(script))
		else:
			self.name = matchName.group(0)

		regexGroup = re.compile("[^_]+")
		matchGroup = regexGroup.search(self.name)
		if not matchGroup:
			raise ConfigurationError("Error: Could not determine the group to which '%s' belongs." %(self.name))
		else:
			self.group = matchGroup.group(0)

		self.accessCheck()
		self.parseScript()
		self.syntaxCheck()

	def __str__(self):
		return "Script: %s (%s) depending on: %s %s %s" % (
			self.name,
			self.status,
			" ".join(["(%s)" % dep for dep in self.sdep]),
			" ".join(["[%s]" % dep for dep in self.idep]),
			" ".join(["{%s}" % dep for dep in self.hdep])
			)

	def queue(self):
		rcubic = self.manager.rcubic

		#Since queue is also used to re-schedule we need to be carefull about
		#what jobs we can start. Either never started or failed ones.
		#if self.status != Status.FAILED or self.status != Status.NONE:
		#	print("error, status is %s" % self.status)
		if self.status == Status.SUCCEEDED:
			return False

		self.status = Status.QUEUED
		self.stdout = ""

		for event in self.monitoredEvents:
			event.wait()

		if self.status == Status.CANCELLED:
			logging.info("Cancelled job %s" % self.name)
			rcubic.refreshStatus(self)
			return False

		self.gitHead = rcubic.gitHead
		arguments = []
		arguments.append(self.script)
		arguments.append(self.version)
		arguments.append(rcubic.environment)
		arguments.append(self.script)
		arguments.append(str(rcubic.port))
		if not rcubic.token == None:
			arguments.append("--token=%s" % rcubic.token)

		self.status = Status.BLOCKED
		rcubic.refreshStatus(self)
		self.manager.rcubic.resourceScheduler.request(self.resources)

		self.status = Status.STARTED
		rcubic.refreshStatus(self)
		rcode, self.stdout = popenNonblock(
			arguments,
			cwd=rcubic.releaseDir,
			logFile="%s/work/log/%s.log" %((self.manager.rcubic.config["basePath"], self.name))
			)

		self.manager.rcubic.resourceScheduler.release(self.resources)
		if rcode == 0:
			self.status = Status.SUCCEEDED
			rcubic.refreshStatus(self)
			self.event.set()
			return True
		else:
			self.status = Status.FAILED
			rcubic.refreshStatus(self)
			return False


	def gparentCompile(self):
		"""Finds all 'live' grandparents of a job and saves them to rs.gparent."""
		#Not exactly efficient hash tables might help memory foot print.
		deps = self.hdep + self.sdep + self.idep
		if self.gparent:
			return self.gparent + deps
		else:
			for parent in deps:
				parent = self.manager.find(parent)
				if parent:
					for gparent in parent.gparentCompile():
						if gparent in self.gparent:
							continue
						self.gparent.append(gparent)
			return self.gparent + deps

	def setOverride(self):
		self.override = True

	@property
	def adep(self):
		deps = dict()
		deps.update(dict([(dep, 'hdep') for dep in self.hdep]))
		deps.update(dict([(dep, 'sdep') for dep in self.sdep]))
		deps.update(dict([(dep, 'idep') for dep in self.idep]))
		return deps

	def isDone(self):
		if self.status in [ Status.SUCCEEDED, Status.FAILED, Status.CANCELLED, Status.MANUALOVERRIDE]:
			return True
		return False

	def isSuccess(self):
		if self.status in [ Status.SUCCEEDED, Status.MANUALOVERRIDE ]:
			return True
		return False

	@property
	def isFailed(self):
		if self.status == Status.FAILED:
			return True
		return False

	def updateProgress(self, progress):
		try:
			progress = int(progress)
		except ValueError:
			return False
		if progress < 0:
			return False
		if progress > 100:
			return False
		if progress >= self.progress:
			self.progress = progress
			return True
		return False

	@property
	def status(self):
		return self._status

	@status.setter
	def status(self, status):
		if status not in Status.all:
			raise FatalRuntimeError("ERROR: Setting status to unknown value")
		self._status = status
		if self.isFailed:
			self.hasFailed = True

	def syntaxCheck(self):
		with open("/dev/null", "w") as devnull:
			process = subprocess.Popen(["bash", "-n", self.script], stdout=devnull, stderr=devnull)
		self.validSyntax = process.wait() == 0
		return self.validSyntax

	#Preps a job to be run out of sequnce
	#this proccess seems backwards. It seems like adding all the jobs first and deleting the ones that are not needed is more flexible
	def hijack(self, hijackPoint):
		for hdep in self.hdep:
			if not self.manager.find(hdep):
				self.hdep.remove(hdep)
		#TODO There might be a smarter way to reset dependencies in the case of a hijack?
		if not self.hdep and self.phase != self.Phase.EARLY :
			self.hdep.append(hijackPoint)

	def accessCheck(self):
		self.isExecutable = os.access(self.script, os.X_OK)

	def parseScript(self):
		f = open(self.script)
		script = f.read()

		self.hdep = self._getHeader("HDEP", script)
		self.sdep = self._getHeader("SDEP", script)
		self.cdep = self._getHeader("CDEP", script)
		self.resources = self._getHeader("RESOURCES", script)
		self.resources.append("default")
		self.products = self._getHeader("PRODUCT", script)

		try:
			phase = self._getHeader("PHASE", script)[0].upper()
			if phase in ReleaseScript.Phase.all:
				self.phase = phase
		except IndexError:
			pass

		trapRe = re.compile("^[^#]*trap\s.*\s(EXIT|0)", re.MULTILINE)
		if trapRe.search(script):
			self.containsTrap = True

		if "scriptregex" in self.manager.rcubic.config:
			self.regexok = bool(
				re.search(self.manager.rcubic.config["scriptregex"], script, re.MULTILINE)
				)
		f.close()

	def _getHeader(self, header, script):
		headerRe = re.compile("^[\s]*#%s:.*$" %(header), re.MULTILINE)
		line = headerRe.search(script)
		if line:
			return self._parseHeaderLine(line.group(0))
		else:
			return []

	def _parseHeaderLine(self, line):
		begin = re.compile("^#[A-Z0-9]+:[\s]*")
		seperator = re.compile("[,;\s]+")
		retVal = seperator.split(begin.sub("", line, 1))
		while True:
			try:
				retVal.remove("")
			except ValueError:
				break
		return retVal

	def toJSONNode(self, arborescent=False):
		colors = {
			'sdep' : {'undefnode':'gray', 'undefedge':'palegreen', 'node':'green'},
			'idep' : {'undefnode':'gray', 'undefedge':'palegreen', 'node':'gold4'},
			'hdep' : {'undefnode':'red', 'undefedge':'red', 'node':'blue'}
		}
		color = "white"
		others = [ ]
		if self.status in self.nodeColors:
			color = self.nodeColors[self.status]
		for dep, kind in self.adep.iteritems():
			if arborescent:
				if dep in self.gparent:
					continue
				if not self.manager.find(dep):
					others.append([dep, colors[kind]['undefnode'], -1])
		return (self.name, color, self.progress, others)

	def toDotNode(self, url=None, basePathTrimLen=0):

		str = "\t\"%s\" [style=\"filled\"" %(self.name)
		if self.status in self.nodeColors:
			str += ", fillcolor=\"%s\"" %(self.nodeColors[self.status])
		else:
			str += ", fillcolor=\"white\""

		#if self.progress >= 0:
			#str += ", label=\"%s\\n%d%%\"" %(self.name, self.progress)

		if self.override:
			str += ", color=\"blue\""

		if url:
			if self.manager.rcubic.config["fileMode"]:
				str += ", href=\"%s/%s\"" %(self.manager.rcubic.config["basePath"][len(self.manager.rcubic.originalBasePath):], self.script[basePathTrimLen:])
			else:
				# If job hasn't started yet, guess to use the rcubic head
				if(self.gitHead == ""):
					gitHead = self.manager.rcubic.gitHead
				else:
					gitHead = self.gitHead
				str += ", href=\"%s/gitweb?p=%s;a=blob;f=%s;hb=%s\"" % (self.manager.rcubic.config["gerritURL"],self.manager.rcubic.config["gerritProject"], self.script[basePathTrimLen:].lstrip('/'), gitHead)

		str += "];"
		return str

	def toDotEdge(self, arborescent=False):
		str=""
		colors = {
			'sdep' : {'undefnode':'gray', 'undefedge':'palegreen', 'node':'green'},
			'idep' : {'undefnode':'gray', 'undefedge':'palegreen', 'node':'gold4'},
			'hdep' : {'undefnode':'red', 'undefedge':'red', 'node':'blue'}
		}
		for dep, kind in self.adep.iteritems():
			if arborescent:
				if dep in self.gparent:
					continue
			if not self.manager.find(dep):
					str += "\t\"%s\" [color=\"%s\" href=\"http://geocities/bl@ckh0le\"];" %(dep, colors[kind]['undefnode'])
					str += "\t\"%s\" -> \"%s\" [color=\"%s\"];\n" %(dep, self.name, colors[kind]['undefedge'])
			else:
				str += "\t\"%s\" -> \"%s\" [color=\"%s\"];\n" %(dep, self.name, colors[kind]['node'])
		return str

	def validate(self):
		str = ""
		depCount = 0

		if not self.isExecutable:
			str += "\tThe script %s is not executable.\n" %(self.script)

		if self.name == "":
			str += "\tCannot determine name of %s\n" %(self.script)
		if self.group == "":
			str += "\tCannot determine group of %s\n" %(self.script)

		if self.products == []:
			str += "\tProduct name not defined in %s.\n" %(self.script)

		#TODO: clean this code to use isDAG style
		for hdep in self.hdep:
			if not self.manager.find(hdep):
				str += "\tcannot locate '%s', needed for '%s'\n" %(hdep, self.name)
			else:
				depCount += 1
		for sdep in self.sdep:
			if self.manager.find(sdep):
				depCount += 1
		if depCount <= 0 and self.name not in self.manager.specialJobs:
				str += "\t%s must be a descendant of specialJobs (%s) but its not.\n" %(self.name, ",".join(self.manager.specialJobs))

		globex = re.compile(".*[][*?].*")
		for hdep in self.hdep:
			match = globex.search(hdep)
			if match:
				str += "\t%s contains globs in hdep: %s.\n" %(self.name, match.group(0))

		if self.phase == ReleaseScript.Phase.NONE:
			str += "\tPhase of job %s is not known.\n" %(self.name)
		if self.containsTrap:
			str += "\t%s contains it's own 'EXIT' trap.\n" %(self.name)
		if not self.regexok:
			str += "\t%s does not match required regex.\n" %(self.name)
		if not self.validSyntax:
			str += "\t%s does not pass syntax check.\n" %(self.name)
		if str:
			return str
		else:
			return None

	def initEvents(self):
		deps = []
		for dep, kind in self.adep.iteritems():
			if dep in self.gparent:
				continue
			depInst = self.manager.find(dep)
			if depInst is not None:
				self.monitoredEvents.append(depInst.event)
			elif kind == "hdep":
				raise FatalRuntimeError("ERROR: Unreachable hard dependency. At this phase it should be impossible")
