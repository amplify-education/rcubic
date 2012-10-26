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
from exectree import exectree
from lxml import etree


class RcubicScript(object):
	def __init__(self, name, path, hdep, sdep, cdep, resources, products, phase=0):
		self.name = name
		self.path = path
		self.hdep = hdep
		self.sdep = sdep
		self.cdep = cdep
		self.resources = resources
		self.products = products
		self.job = None
		self.phase = phase

class RCubicGroup(object):
	def __init__(self, name, phase=0, version=None):
		self.name = name
		self.phase = phase
		self.version = version

	def __str__(self):
		return self.name

class RCubicScriptParser(object):
	PHASES = {"DEFAULT":0, "EARLY":-1, "LATE":1}
	def __init__(self, directory, groups):
		self.directory = directory
		self.groups = groups
		self.scripts = []

	def read_dirs(self):
		failed_groups = []
		for group in self.groups:
			directory = "{0}/{1}".format(self.directory, group)
			if not os.path.exists(directory):
				failed_groups.append(group)
				continue
			files = 0
			for filename in os.listdir(directory):
				filepath = "{0}/{1}".format(directory, filename)
				if filename.startswith("{0}_".format(group)):
					self.parse_script(filepath, group.phase)
				else:
					logging.debug(
							"Skipping {0}/{1}, does not start with {2}_."
							.format(filepath, group)
						)

	def parse_script(self, filepath, phase=0):
		f = open(filepath)
		script = f.read()
		name = filepath.split("/")[-1]
		hdep = self._get_header_field(script, "HDEP")
		sdep = self._get_header_field(script, "SDEP")
		cdep = self._get_header_field(script, "CDEP")
		resources = self._get_header_field(script, "RESOURCES")
		products = self._get_header_field(script, "PRODUCT")
		sphase = self._get_header_field(script, "PHASE")
		if len(sphase) >= 1:
			phase = RCubicScriptParser.PHASES[sphase[0]]

		rs = RcubicScript(name, filepath, hdep, sdep, cdep, resources, products, phase)
		self.scripts.append(rs)

		"""
		logging.debug("Script: {0}\n\t{1}\n\t{2}\n\t{3}\n\t{4}\n\t{5}\n\t{6}"
			.format(
				filepath,
				hdep,
				sdep,
				cdep,
				resources,
				products,
				phase,
			)
		)
		"""

	def init_tree(self):
		self.tree = exectree.ExecTree()
		for script in self.scripts:
			script.job = exectree.ExecJob(
				script.name,
				script.path
			)
			self.tree.add_job(script.job)
		for script in self.scripts:
			for dep in script.hdep:
				d = self.tree.add_dep(dep, script.job)
				d.color = {"defined":"deepskyblue", "undefined":"red"}
			for dep in script.sdep:
				try:
					d = self.tree.add_dep(dep, script.job)
				except exectree.JobUndefinedError:
					dep = exectree.ExecJob(dep, "-", mustcomplete=False)
					self.tree.add_job(dep)
					d = self.tree.add_dep(dep, script.job)
				d.color = {"defined":"lawngreen", "undefined":"palegreen"}
			for cdep in script.cdep:
				try:
					d = self.tree.add_dep(script.job, dep)
				except exectree.JobUndefinedError:
					dep = self.tree.add_job(
						exectree.ExecJob(dep, "-", mustcomplete=False)
					)
					d = self.tree.add_dep(script.job, dep)
				d.color = {"defined":"lawngreen", "undefined":"palegreen"}
			stems = self.tree.stems()
			for pdep in self.scripts:
				#if pdep.phase < script.phase and pdep.job in stems:
				if pdep.phase < script.phase:
					d = self.tree.add_dep(pdep.job, script.job)
					if d is None:
						continue
					d.color = {"defined":"gold2", "undefined":"gold2"}
		logging.debug("tree:\n{0}".format(etree.tostring(self.tree.xml(), pretty_print=True)))
		return self.tree

	def _get_header_field(self, script, field):
		fieldre = re.compile("^[\s]*#%s:.*$" %(field), re.MULTILINE)
		line = fieldre.search(script)
		val = []
		if line:
			line = line.group(0)
			begin = re.compile("^#[A-Z0-9]+:[\s]*")
			seperator = re.compile("[,;\s]+")
			val = seperator.split(begin.sub("", line, 1))
			while True:
				try:
					val.remove("")
				except ValueError:
					break
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


if __name__ == "__main__":
	dpp12_time = '%Y-%m-%d %H:%M:%S' + str.format('{0:+06.2f}', float(time.altzone) / 3600).replace(".", "")
	log_format = logging.Formatter('[%(asctime)s] | %(filename)s | %(process)d | %(levelname)s | %(message)s', datefmt=dpp12_time)
	handler = logging.StreamHandler()
	handler.setFormatter(log_format)
	logger = logging.getLogger('')
	logger.setLevel(logging.INFO)
	logger.setLevel(logging.DEBUG)
	logger.addHandler(handler)

	groups = [
		RCubicGroup("mhcburstbatch"),
		RCubicGroup("mhcburstalgo"),
		RCubicGroup("global", phase=-1),
		RCubicGroup("release")
	]
	rp = RCubicScriptParser("/home/isukhanov/vcs/release_ais/release/", groups)
	rp.read_dirs()
	tree = rp.init_tree()

	graph = tree.dot_graph()rborescent=True
	graph.write_png("/tmp/foo.png")
	graph.write_dot("/tmp/foo.dot")





