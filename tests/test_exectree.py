#!/usr/bin/python

from exectree import exectree
import unittest
import pydot
from lxml import etree
import shutil
import os
import tempfile
import stat
import random
import time
import gevent
import logging

#class FooBar(RuntimeError):
#	pass

class TestET(unittest.TestCase):
	def setUp(self):
		self.workdir = tempfile.mkdtemp(prefix="rct")
		self.my_arg_str_print = "echo \"MYARGS_WERE: {0}\"\n"
		self.my_arg_str_match = "MYARGS_WERE: {0}"

		self.tree = exectree.ExecTree()
		self.tree.name = "Base Tree"
		self.job1 = self._newjob("foo", self.tree)
		self.job2 = self._newjob("bar", self.tree)
		self.job3 = self._newjob("baz", self.tree)
		self.tree.add_dep(self.job1, self.job2)
		self.tree.add_dep(self.job1, self.job3)

	def teardDown(self):
		shutil.rmtree(self.workdir, False)

	def _newjob(self, name, tree=None, vexec=True, vfile=True, exitcode=0, maxsleep=3):
		"""
		Create job file, job and return the ExecJob

		tree: which tree to add the job to
		vexec: if False, don't make job file executable
		vfile: if False. don't write a job file
		"""
		if vfile:
			fd, path = tempfile.mkstemp(prefix=name, dir=self.workdir)
			os.write(fd, "#!/bin/bash\n")
			os.write(fd, self.my_arg_str_print.format("$2"))
			os.write(fd, "echo \"hello my name is {0}\"\n".format(name))
			if maxsleep > 0:
				os.write(fd, "sleep \"{0}\"\n".format(random.randrange(0, maxsleep)))
			os.write(fd, "exit {0}\n".format(exitcode))
			os.close(fd)
			if vexec:
				seven_five_five = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
				os.chmod(path, seven_five_five)
		else:
			#we use a tmpdir so we can be reasonably sure this file does not exist..
			path = "{0}/noexist_wh9oddaklj".format(self.workdir)
		job = exectree.ExecJob(name, path)
		if tree is not None:
			tree.add_job(job)
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
		job4 = self._newjob("fiz", self.tree)
		job5 = self._newjob("buz", self.tree)
		job6 = self._newjob("fez", self.tree)
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
		self.tree.add_dep(self.job2, self.job3)
		self.tree.add_dep(self.job3, self.job2)
		job4 = self._newjob("fiz", self.tree)
		#graph = self.tree.dot_graph()
		#graph.write_png("/tmp/et1.png")
		#stems = self.tree.stems()
		#print("stems: {0}".format([stem.name for stem in stems]))
		self.assertNotEqual(self.tree.validate(), [])

	def test_validation(self, tree=None):
		""" Validate a tree """
		if tree is None:
			tree = self.tree
		self.assertEqual(tree.validate(), [])

	def test_unreachable_job(self):
		""" Unconnected job detection """
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("fiz", self.tree)
		job5 = self._newjob("buz", self.tree)
		self.tree.add_dep(job4, job5)
		self.tree.add_dep(job5, job4)
		self.assertNotEqual(self.tree.validate(), [])


	def test_xml(self, tree=None):
		""" xml export import export match """
		if tree is None:
			tree = self.tree

		tree1 = tree
		xmltree1  = tree1.xml()
		xmlstr1 = etree.tostring(xmltree1)

		tree2 = exectree.ExecTree(xmltree1)
		xmltree2 = tree2.xml()
		xmlstr2 = etree.tostring(xmltree2)

		#print("tree1:\n {0}".format(etree.tostring(xmltree1, pretty_print=True)))
		#print("tree2:\n {0}".format(etree.tostring(xmltree2, pretty_print=True)))
		self.assertEqual(xmlstr1, xmlstr2)

	def test_execjob_nofile(self):
		""" Validates error on no job file"""
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("yut", self.tree, vfile=False)
		self.tree.add_dep(self.job3, job4)
		self.assertNotEqual(self.tree.validate(), [])


	def test_execjob_noexec(self):
		""" Validates error on unexecutable job file"""
		self.assertEqual(self.tree.validate(), [])
		job4 = self._newjob("fet", self.tree, vexec=False)
		self.tree.add_dep(self.job3, job4)
		self.assertNotEqual(self.tree.validate(), [])


	def test_subtree(self):
		""" Test ExecTree subtrees """
		ltree = exectree.ExecTree()
		ltree.name = "local tree"
		ljob1 = self._newjob("yup", ltree)
		ljob2 = self._newjob("yak", ltree)
		ltree.add_dep(ljob1, ljob2)

		job4 = exectree.ExecJob("rez", subtree=ltree)
		self.tree.add_job(job4)
		self.tree.add_dep(self.job3, job4)

		#Ensure xml export import works
		self.test_xml()


		#Lets break subtree in several differnt ways to ensure it fails validation
		job4.subtree = None
		self.assertNotEqual(self.tree.validate(), [])

		job4.jobpath = "lsadadd"
		self.assertNotEqual(self.tree.validate(), [])

		job4.subtree = ltree
		self.assertNotEqual(self.tree.validate(), [])
		job4.jobpath = None

		#And that the tree is valid
		self.test_validation()

		with gevent.Timeout(10):
			self.tree.run()

		self.assertTrue(ltree.is_done())
		self.assertTrue(self.tree.is_done())

	def test_crosstree_dep(self):
		""" Detect dependencies between jobs in different trees """
		ltree = exectree.ExecTree()
		job4 = self._newjob("lop", ltree)
		with self.assertRaises(exectree.JobUndefinedError):
			self.tree.add_dep(self.job3, job4)

	def test_execution(self):
		""" Run tree and check all jobs finish """
		with gevent.Timeout(10):
			self.tree.run()
		self.assertTrue(self.tree.is_done())


	def test_incomplete_tree(self):
		""" Run tree with failed and sans mustcomplete jobs """
		job4 = self._newjob("war", self.tree, exitcode=1, maxsleep=0)
		job4.mustcomplete = False

		job5 = self._newjob("wex", self.tree, maxsleep=0)
		job5.mustcomplete = False

		job6 = self._newjob("wop", self.tree, maxsleep=0)
		self.tree.add_dep(self.job1, job4)
		self.tree.add_dep(job4, job5)
		self.tree.add_dep(job4, job6, state=exectree.ExecJob.STATE_FAILED)

		with gevent.Timeout(10):
			self.tree.run()

		self.assertTrue(job4.is_done())
		self.assertFalse(job4.is_success())
		self.assertTrue(job5.is_done())
		self.assertTrue(job5.is_cancelled())
		self.assertTrue(job6.is_done())
		self.assertTrue(self.tree.is_done())

	def _test_treetarator_count_incr(self, foo):
		self.ljob1_count += 1

	def test_treetarator(self):
		""" Test ExecTree subtrees with iteration """

		ltree = exectree.ExecTree()
		ltree.name = "local tree"
		ljob1 = self._newjob("sal", ltree)
		ljob1_file_fd, ljob1_file_path = tempfile.mkstemp(prefix="{0}_inst".format(ljob1.name), dir=self.workdir)
		os.fdopen(ljob1_file_fd).close
		ljob1.logfile = ljob1_file_path
		ljob2 = self._newjob("sov", ltree)
		ltree.add_dep(ljob1, ljob2)

		job4 = exectree.ExecJob("sym", subtree=ltree)
		self.tree.add_job(job4)
		self.tree.add_dep(self.job3, job4)

		arguments = ["qwe", "asd", "zxc"]
		ltree.iterator = exectree.ExecIter("test", arguments)

		#Each time ljob1 executes increment counter
		self.ljob1_count = 0
		ljob1.events[exectree.ExecJob.STATE_SUCCESSFULL].rawlink(self._test_treetarator_count_incr)

		with gevent.Timeout(30):
			runreturn = self.tree.run()

		#Confirm that we see all 3 arguments
		ljob1_file_fd = open(ljob1_file_path)
		text = ljob1_file_fd.read()
		ljob1_file_fd.close()
		last = 0
		for arg in arguments:
			last = text.find(self.my_arg_str_match.format(arg), last)
			self.assertTrue(last >= 0)

		self.assertIsNone(runreturn)
		self.assertTrue(ltree.is_done())
		self.assertTrue(self.tree.is_done())
		self.assertTrue(self.ljob1_count == len(arguments))

if  __name__ == '__main__':
	unittest.main()
