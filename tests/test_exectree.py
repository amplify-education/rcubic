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
import functools

class TestET(unittest.TestCase):
	def setUp(self):
		#logger = logging.getLogger('')
		#logger.setLevel(logging.DEBUG)

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

	def _tearDown(self):
		shutil.rmtree(self.workdir, False)


	def _logfile_init(self, job):
		fd, path = tempfile.mkstemp(prefix="{0}_inst".format(job.name), dir=self.workdir)
		os.fdopen(fd).close()
		job.logfile = path

	def _logfile_read(self, job):
		with open(job.logfile) as log:
			return log.read()

	def _newjob(self, name, tree=None, vexec=True, vfile=True, exitcode=0, maxsleep=3, append=""):
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
			os.write(fd, append)
			os.write(fd, "exit {0}\n".format(exitcode))
			os.close(fd)
			if vexec:
				seven_five_five = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
				os.chmod(path, seven_five_five)
		else:
			#we use a tmpdir so we can be reasonably sure this file does not exist..
			path = "{0}/noexist_wh9oddaklj".format(self.workdir)
		job = exectree.ExecJob(name, path, arguments=[name])
		if tree is not None:
			tree.add_job(job)
		return job

	def test_graph(self, tree=None, target=None):
		""" Generate and render graph """
		if tree == None:
			tree = self.tree
		graph = tree.dot_graph()
		#self.assertIs(graph, Graph)
		self.assertTrue(isinstance(graph, pydot.Graph))

		#TODO validate the file somehow
		if target == None:
			target = "{0}/et.png".format(self.workdir)
		graph.write_png(target)

		logging.debug(graph.to_string())


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
		v = self.tree.validate()
		try:
			self.assertNotEqual(v, [])
		except:
			logging.debug(v)
			raise


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

		logging.debug("tree1:\n {0}".format(etree.tostring(xmltree1, pretty_print=True)))
		logging.debug("tree2:\n {0}".format(etree.tostring(xmltree2, pretty_print=True)))
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

	def test_undef_job(self):
		"""Add an undefined job to exectree"""
		job4 = self._newjob("jum", self.tree, vexec=False)
		job4.jobpath = job4.UNDEF_JOB
		self.tree.add_dep(self.job3, job4)

		self.test_validation()
		self.test_execution()
		self.test_graph()

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
		""" Run trees with itterated subtrees """

		ltree = exectree.ExecTree()
		ltree.name = "local tree"
		ljob1 = self._newjob("sal", ltree)
		self._logfile_init(ljob1)

		ljob2 = self._newjob("sov", ltree)
		ltree.add_dep(ljob1, ljob2)

		job4 = exectree.ExecJob("sym", subtree=ltree)
		self.tree.add_job(job4)
		self.tree.add_dep(self.job3, job4)

		job5 = self._newjob("soi", self.tree)
		self.tree.add_dep(job4, job5)

		arguments = ["qwe", "asd", "zxc"]
		ltree.iterator = exectree.ExecIter("test", arguments)

		#Each time ljob1 executes increment counter
		self.ljob1_count = 0
		ljob1.events[exectree.ExecJob.STATE_SUCCESSFULL].rawlink(self._test_treetarator_count_incr)

		with gevent.Timeout(30):
			runreturn = self.tree.run()

		#Confirm that we see all 3 arguments
		text = self._logfile_read(ljob1)
		last = 0
		for arg in arguments:
			last = text.find(self.my_arg_str_match.format(arg), last)
			self.assertTrue(last >= 0)

		self.assertIsNone(runreturn)
		self.assertTrue(ltree.is_done())
		self.assertTrue(self.tree.is_done())
		logging.debug("{0} == {1}".format(self.ljob1_count, len(arguments)))
		self.assertTrue(self.ljob1_count == len(arguments))
		self.test_graph(target="{0}/cyt.png".format(self.workdir))

	def test_resource_validation(self):
		""" Resource validation """
		resource = exectree.ExecResource(self.tree, "test", 1)
		self.job1.resources.append(resource)
		self.assertEqual(self.tree.validate(), [])

		self.tree.resources.remove(resource)
		self.assertNotEqual(self.tree.validate(), [])

		self.tree.resources.append(resource)
		self.test_xml()

	def _test_resource_evhandler(self, times, state, event):
		times[state] = time.time()

	def test_resource_use(self):
		""" Run tree with resources """
		resource = exectree.ExecResource(self.tree, "r3", 1)
		times = {}
		jobs = [self.job2, self.job3]
		i = 0
		while i < 5:
			job = self._newjob("pol{0}".format(i), self.tree)
			self.tree.add_dep(self.job1, job)
			jobs.append(job)
			i += 1
		for j in jobs:
			j.logfile = "/dev/null"
			j.resources.append(resource)
			times[j] = {}
			for ev in [j.STATE_RUNNING, j.STATE_SUCCESSFULL]:
				h = functools.partial(self._test_resource_evhandler, times[j], ev)
				j.events[ev].rawlink(h)
		with gevent.Timeout(30):
			self.tree.run()
		self.assertTrue(self.tree.is_done())
		self.assertTrue(self.tree.is_success())
		logging.debug("times {0}".format(times))

		#No jobs overlapped?
		for job in jobs:
			for sjob in jobs:
				if job == sjob:
					continue
				jr = times[job][job.STATE_RUNNING]
				js = times[job][job.STATE_SUCCESSFULL]
				sjr = times[sjob][sjob.STATE_RUNNING]
				sjs = times[sjob][sjob.STATE_SUCCESSFULL]
				self.assertTrue(
					(jr > sjr and jr > sjs)
					or
					(jr < sjr and jr < sjs)
				)

	def test_fail_reschedule_succeed(self):
		""" Reschedule failed job """
		tfd, tpath = tempfile.mkstemp(dir=self.workdir)
		os.close(tfd)

		logging.debug("tempfile: {0}".format(tpath))
		append = "if [ -e {0} ]; then exit 1; fi\n".format(tpath)
		job4 = self._newjob("qor", self.tree, append=append)
		job5 = self._newjob("qam", self.tree)
		self.tree.add_dep(self.job3, job4)
		self.tree.add_dep(job4, job5)

		self._logfile_init(job4)

		with gevent.Timeout(10):
			self.tree.run(blocking=False)
			logging.debug("Tree started, waiting for failure")
			logging.debug("dirs before: {0}".format(os.listdir(self.workdir)))
			job4.events[job4.STATE_FAILED].wait()
			os.remove(tpath)
			logging.debug("dirs after: {0}".format(os.listdir(self.workdir)))
			logging.debug("Failure detected, resetting and restarting job")
			logging.debug("job4 log: {0}".format(self._logfile_read(job4)))
			job4.reset()
			job4.start()
			logging.debug("job started")
			self.tree.join()

		self.assertTrue(job4.execcount == 2)
		self.assertTrue(self.tree.is_done())

if  __name__ == '__main__':
	unittest.main()
