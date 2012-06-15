#!/usr/bin/python

from exectree import exectree
import unittest
import pydot
#import xml.etree.ElemeddntTree as elemtree
from lxml import etree
import shutil
import os
import tempfile

class TestET(unittest.TestCase):
	def setUp(self):
		self.workdir = tempfile.mkdtemp(prefix="rct")

		self.tree = exectree.ExecTree()
		self.job1 = self._newjob("foo")
		self.job2 = self._newjob("bar")
		self.job3 = self._newjob("baz")
		self.tree.add_dep(self.job1, self.job2)
		self.tree.add_dep(self.job1, self.job3)

	def teardDown(self):
		shutil.rmtree(self.workdir, False)

	def _newjob(self, name, vexec=True, vfile=True, vadd=True):
		"""
		Create job file, job and return the ExecJob

		vexec: if False, don't make job file executable
		vfile: if False. don't write a job file
		vadd: if False, don't add job to tree
		"""
		if vfile:
			fd, path = tempfile.mkstemp(prefix=name, dir=self.workdir)
			os.write(fd, "#!/bin/bash")
			os.write(fd, "echo \"hello my name is {0}\"".format(name))
			os.close(fd)
			if vexec:
				os.chmod(path, 755)
		else:
			#we use a tmpdir so we can be reasonably sure this file does not exist..
			path = "{0}/noexist_wh9oddaklj".format(self.workdir)
		job = exectree.ExecJob(name, path)
		if vadd:
			self.tree.add_job(job)
		return job

	def test_graph(self):
		""" Generate and render graph """
		graph = self.tree.dot_graph()
		#self.assertIs(graph, Graph)
		self.assertTrue(isinstance(graph, pydot.Graph))

		#TODO cleanup and validate the file somehow
		graph.write_png("/tmp/et.png")


	def test_multistem(self):
		""" multistem detection """
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("fiz")
		job5 = self._newjob("buz")
		job6 = self._newjob("fez")
		#print("jobs: {0}".format([job.name for job in self.tree.jobs]))
		self.tree.add_dep(job4, job5)

		#graph = self.tree.dot_graph()
		#graph.write_png("/tmp/et1.png")

		stems = self.tree.stems()
		#print("stems: {0}".format([stem.name for stem in stems]))

		self.assertEqual(len(stems), 3)
		#self.assertIn(job4, stems)
		#self.assertNotIn(job5, stems)
		self.assertTrue(job4 in stems)
		self.assertFalse(job5 in stems)
		self.assertTrue(job6 in stems)
		self.assertNotEqual(self.tree.validate(), [])


	def test_own_parent(self):
		""" Detect bootstrap paradox """
		self.assertRaises(exectree.DependencyError, self.tree.add_dep, self.job1, self.job1)

	def test_cycles(self):
		""" Cycle detection """
		self.assertEqual(self.tree.validate(), [])

		self.tree.add_dep(self.job2, self.job3)
		self.tree.add_dep(self.job3, self.job2)
		job4 = self._newjob("fiz")
		#graph = self.tree.dot_graph()
		#graph.write_png("/tmp/et1.png")
		#stems = self.tree.stems()
		#print("stems: {0}".format([stem.name for stem in stems]))
		self.assertNotEqual(self.tree.validate(), [])

	def test_unreachable_job(self):
		""" Unconnected job detection """
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("fiz")
		job5 = self._newjob("buz")
		self.tree.add_dep(job4, job5)
		self.tree.add_dep(job5, job4)
		self.assertNotEqual(self.tree.validate(), [])


	def test_xml(self):
		""" xml export import export match """
		tree1 = self.tree
		xmltree1  = tree1.xml()
		xmlstr1 = etree.tostring(xmltree1)

		tree2 = exectree.ExecTree(xmltree1)
		xmltree2 = tree2.xml()
		xmlstr2 = etree.tostring(xmltree2)

		#print("tree1: {0}".format(xmlstr1))
		#print("tree2: {0}".format(xmlstr2))
		self.assertEqual(xmlstr1, xmlstr2)

	def test_execJob_nofile(self):
		""" Validates error on no job file"""
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("yut", vfile=False)
		self.tree.add_dep(self.job3, job4)
		self.assertNotEqual(self.tree.validate(), [])


	def test_execJob_noexec(self):
		""" Validates error on unexecutable job file"""
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("fet", vexec=False)
		self.tree.add_dep(self.job3, job4)
		self.assertNotEqual(self.tree.validate(), [])

if  __name__ == '__main__':
	unittest.main()
