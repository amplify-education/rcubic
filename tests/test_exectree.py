#!/usr/bin/python

from exectree import exectree
import unittest
import pydot
#import xml.etree.ElemeddntTree as elemtree
from lxml import etree

class TestET(unittest.TestCase):
	def setUp(self):
		self.tree = exectree.ExecTree()
		self.job1 = exectree.ExecJob("foo", "/tmp/foo")
		self.job2 = exectree.ExecJob("bar", "/tmp/bar")
		self.job3 = exectree.ExecJob("baz", "/tmp/baz")
		self.tree.add_job(self.job1)
		self.tree.add_job(self.job2)
		self.tree.add_job(self.job3)
		self.tree.add_dep(self.job1, self.job2)
		self.tree.add_dep(self.job1, self.job3)


	def test_graph(self):
		""" Generate and render graph """
		graph = self.tree.dot_graph()
		#self.assertIs(graph, Graph)
		self.assertTrue(isinstance(graph, pydot.Graph))

		#TODO cleanup and validate the file somehow
		graph.write_png("/tmp/et.png")


	def test_multistem(self):
		""" multistem detection """
		job4 = exectree.ExecJob("fiz", "/tmp/fiz")
		job5 = exectree.ExecJob("buz", "/tmp/buz")
		job6 = exectree.ExecJob("fez", "/tmp/fez")
		self.tree.add_job(job4)
		self.tree.add_job(job5)
		self.tree.add_job(job6)
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
		job4 = exectree.ExecJob("fiz", "/tmp/fiz")
		self.tree.add_job(job4)
		#graph = self.tree.dot_graph()
		#graph.write_png("/tmp/et1.png")
		#stems = self.tree.stems()
		#print("stems: {0}".format([stem.name for stem in stems]))
		self.assertNotEqual(self.tree.validate(), [])

	def test_unreachable_job(self):
		""" Unconnected job detection """
		job4 = exectree.ExecJob("fiz", "/tmp/fiz")
		job5 = exectree.ExecJob("buz", "/tmp/buz")
		self.tree.add_job(job4)
		self.tree.add_job(job5)
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

		print("tree1: {0}".format(xmlstr1))
		print("tree2: {0}".format(xmlstr2))
		self.assertEqual(xmlstr1, xmlstr2)

if  __name__ == '__main__':
	unittest.main()
