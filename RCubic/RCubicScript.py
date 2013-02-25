# vim: ts=4 noet filetype=python
# This file is part of RCubic
#
#Copyright (c) 2012 Wireless Generation, Inc.
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import os
import logging
import time
import re
import fnmatch
from RCubic import exectree
from lxml import etree
import subprocess


class ConfigurationError(Exception):
	pass


class RCubicScript(object):
	def __init__(self, filepath, version, override, phase, logdir, whitelist, blacklist, regexval, group):
		self.path = filepath
		self.name = filepath.split("/")[-1]
		self.version = version
		self.override = override
		self.logfile = "{0}/{1}.log".format(logdir, self.name)

		with open(self.path) as fd:
			script = fd.read()
		self.hdep = self._param_split(self._get_param(script, "HDEP"))
		self.sdep = self._param_split(self._get_param(script, "SDEP"))
		self.cdep = self._param_split(self._get_param(script, "CDEP"))
		self.idep = self._get_param(script, "IDEP", None)
		self.iterator = self._param_split(self._get_param(script, "ITER"))
		self.resources = self._param_split(self._get_param(script, "RESOURCES"))
		self.resources.append("default")
		self.products = self._param_split(self._get_param(script, "PRODUCT"))
		sphase = self._param_split(self._get_param(script, "PHASE"))
		self.group = group
		if regexval is None:
			self.regexval = True
		else:
			r = regexval.search(script)
			self.regexval = r is not None
		self.href = ""

		if len(sphase) >= 1:
			phase = RCubicScriptParser.PHASES[sphase[0]]
		self.phase = phase

		if len(blacklist) > 0 and self.name in blacklist:
			self.path="-"
		elif len(whitelist) > 0 and self.name not in whitelist:
			self.path="-"

	def _get_param(self, script, field, default=None):
		fieldre = re.compile("^#%s:.*$" %(field), re.MULTILINE)
		begin = re.compile("^#[A-Z0-9]+:[\s]*")
		line = fieldre.search(script)
		if line:
			return begin.sub("", line.group(0), 1)
		else:
			return default

	def _param_split(self, param):
		val = []
		if param is not None:
			seperator = re.compile("[,;\s]+")
			val = seperator.split(param)
			while "" in val:
				val.remove("")
		return val

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

class RCubicGroup(object):
	def __init__(self, element):
		try:
			self.version = element.attrib["version"]
			self.name = element.attrib["group"]
		except KeyError:
			raise ConfigurationError(
				"Element on line %i of %s is missing version or group attributes."
				%(element.sourceline, element.base)
			)

		try:
			self.phase = RCubicScriptParser.PHASES[
				element.attrib.get("phase", "DEFAULT").upper()
			]
		except:
			raise ConfigurationError(
				"Attribute phase on line %i of %s has unrecognized value: '%s'."
				%(element.sourceline, element.base, self.phase)
			)

		def booler(element, attrib, default):
			value = element.attrib.get(attrib, default).lower()
			if value not in ["true", "false"]:
				raise ConfigurationError(
					"Attribute {0} is not (true|false) on line {1} of {2}."
					.format(attrib, element.sourceline, element.base)
				)
			return value == "true"

		self.autoselect = booler(element, "autoSelect", "true")
		self.fulloverride = booler(element, "fullOverride", "false")
		self.forceselect = False
		self.scripts = []

	def __str__(self):
		return self.name

	def is_success(self):
		for script in self.scripts:
			if not script.job.is_success():
				return False
		return True

	def is_done(self):
		for script in self.scripts:
			if not script.job.is_done():
				return False
		return True

	def add_script(self, rs, override=False):
		if override:
			logging.debug("{0} is being overriden by {1}".format(rs.name, rs.path))
			for script in self.scripts:
				if script.name == rs.name:
					self.scripts.remove(script)
					break
		self.scripts.append(rs)


class RCubicScriptParser(object):
	PHASES = {"DEFAULT":0, "EARLY":-1, "LATE":1}
	def __init__(self, groups, logdir, workdir, whitelist, blacklist, regexval, resources):
		self.groups = groups
		self.logdir = logdir
		self.workdir = workdir
		if blacklist and whitelist:
			logging.warning("Conflicting whitelist/blacklist option. Ignoring blacklist.")
			blacklist = []
		elif blacklist is None:
			blacklist = []
		elif whitelist is None:
			whitelist =[]
		self.blacklist = blacklist
		self.whitelist = whitelist
		if regexval is not None:
			regexval = re.compile(regexval, re.MULTILINE)
		self.regexval = regexval
		self.resources = resources
		self.unusedresources = []
		self.tree = None
		self.subtrees = {}

	def scripts(self):
		scripts = []
		for group in self.groups:
			for script in group.scripts:
				scripts.append(script)
		return scripts

	def read_dirs(self, directory, override=False):
		failed_groups = []
		for group in self.groups:
			groupdir = "{0}/{1}".format(directory, group)
			logging.debug("processing group {0} {1} {2}.".format(group.name, groupdir, override))
			if not override:
				if not os.path.exists(groupdir):
					failed_groups.append(group)
					continue
				if group.fulloverride:
					continue
			else:
				if not os.path.exists(groupdir):
					continue
			for filename in os.listdir(groupdir):
				filepath = "{0}/{1}".format(groupdir, filename)
				if filename.startswith("{0}_".format(group)):
					rs = RCubicScript(
						filepath,
						group.version,
						override,
						group.phase,
						self.logdir,
						self.whitelist,
						self.blacklist,
						self.regexval,
						group,
					)
					group.add_script(rs, override)
				else:
					logging.debug(
							"Skipping {0}/{1}, does not start with {2}_."
							.format(filepath, group)
						)

	def _glob_expand(self, deps):
		rval = []
		for dep in deps:
			matched = False
			for script in self.scripts():
				if fnmatch.fnmatchcase(script.name, dep):
					#we return script names instead of job instances to let
					#ExecTree handle dangling deps
					rval.append(script.name)
					matched = True
			if not matched:
				rval.append(dep)
		return rval

	def eval_args(self, script):
		logging.debug("iterator: {0}, cwd: {1}".format(script.iterator, self.workdir))
		with open("/dev/null", "w") as devnull:
			if hasattr(subprocess, "check_output"):
				output = subprocess.check_output(script.iterator, stderr=devnull, cwd=self.workdir)
			else:
				p = subprocess.Popen(script.iterator, stdout=subprocess.PIPE, stderr=devnull, cwd=self.workdir)
				output = p.communicate()[0]
		seperator = re.compile("[,;\s]+")
		args = seperator.split(output)
		while "" in args:
			args.remove("")
		logging.debug("Arguments {0}".format(args))
		return args

	def set_href(self, gerrit, project, githash, repopath):
		logging.debug("set hrefs")
		for script in self.scripts():
			script.href = "{0}/gitweb?p={1};a=blob;f={2};hb={3}".format(
				gerrit, project, script.path[len(repopath)+1:], githash
			)

	def init_tree(self):
		self.tree = exectree.ExecTree()
		self.tree.cwd = self.workdir
		self.tree.name = "rcubic"

		#Initialize all sub trees
		for script in self.scripts():
			if len(script.iterator) > 0:
				tree = exectree.ExecTree()
				tree.cwd = self.workdir
				tree.name = script.name
				tree.iterator = exectree.ExecIter(
					"{0}_iter".format(script.name),
					self.eval_args(script)
				)
				self.subtrees[script.name] = tree

		#Initialize Resources
		for resource, limit in self.resources.items():
			exectree.ExecResource(self.tree, resource, limit)

		#Initialize jobs and add to trees
		for script in self.scripts():
			script.job = exectree.ExecJob(
				script.name,
				script.path,
				logfile=script.logfile,
				arguments=[script.version],
				href=script.href
			)
			if script.name in self.subtrees:
				script.job.jobpath = None
				script.job.subtree = self.subtrees[script.name]
			if script.override:
				script.job.tcolor = "deepskyblue"
			for resource in script.resources:
				r = self.tree.find_resource(resource)
				if r is None:
					if resource not in self.unusedresources:
						self.unusedresources.append(resource)
				else:
					script.job.resources.append(r)
			if script.idep is None:
				self.tree.add_job(script.job)
			else:
				#todo handle exception nicely
				self.subtrees[script.idep].add_job(script.job)
		#Check for undefined resources
		if len(self.unusedresources) > 0:
			logging.warning(
				"Resources referenced but not defined: {0}."
				.format(", ".join(self.unusedresources))
			)

		#Initialize and set up dependencies
		for script in self.scripts():
			logging.debug("proccessing script: {0}".format(script.name))
			if script.idep is None:
				tree = self.tree
			else:
				tree = self.subtrees[script.idep]

			for dep in self._glob_expand(script.hdep):
				try:
					d = tree.add_dep(dep, script.job)
				except exectree.JobUndefinedError:
					if script.job.is_defined():
						raise
					dep = exectree.ExecJob(dep, "-", mustcomplete=False)
					tree.add_job(dep)
					d = tree.add_dep(dep, script.job)
				d.color = {"defined":"deepskyblue", "undefined":"red"}
			for dep in self._glob_expand(script.sdep):
				try:
					d = tree.add_dep(dep, script.job)
				except exectree.JobUndefinedError:
					dep = exectree.ExecJob(dep, "-", mustcomplete=False)
					tree.add_job(dep)
					d = tree.add_dep(dep, script.job)
				d.color = {"defined":"lawngreen", "undefined":"palegreen"}
			for cdep in self._glob_expand(script.cdep):
				#logging.debug("adding dep to ")
				try:
					d = tree.add_dep(script.job, cdep)
				except exectree.JobUndefinedError:
					cdep = exectree.ExecJob(cdep, "-", mustcomplete=False)
					tree.add_job(cdep)
					d = tree.add_dep(script.job, cdep)
				d.color = {"defined":"lawngreen", "undefined":"palegreen"}
			#stems = self.tree.stems()
			for pdep in self.scripts():
				#if pdep.phase < script.phase and pdep.job in stems:
				if pdep.phase < script.phase and pdep.idep is None and script.idep is None:
					d = tree.add_dep(pdep.job, script.job)
					if d is None:
						continue
					d.color = {"defined":"gold2", "undefined":"gold2"}
		#logging.debug("tree:\n{0}".format(etree.tostring(self.tree.xml(), pretty_print=True)))
		return self.tree

