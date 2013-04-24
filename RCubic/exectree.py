# vim: ts=4 noet filetype=python
# This file is part of RCubic
#
# Copyright (c) 2012 Wireless Generation, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import uuid
import os
import random
import subprocess
import fcntl
import errno
import sys
import logging
import simplejson
import re
import fnmatch

from lxml import etree as et
import gevent
from gevent import (Greenlet, event, socket)
import pydot


class TreeDefinedError(RuntimeError):
    pass


class TreeUndefinedError(RuntimeError):
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


# class ExecJob(Greenlet):
class ExecJob(object):
    STATES = (0, 1, 2, 3, 4, 5, 6, 7)
    STATE_IDLE, STATE_RUNNING, STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED, STATE_UNDEF, STATE_RESET, STATE_BLOCKED = STATES
    DEPENDENCY_STATES = [STATE_SUCCESSFULL, STATE_FAILED]
    DONE_STATES = [STATE_SUCCESSFULL, STATE_FAILED, STATE_CANCELLED, STATE_UNDEF]
    SUCCESS_STATES = [STATE_SUCCESSFULL, STATE_UNDEF]
    ERROR_STATES = [STATE_FAILED, STATE_CANCELLED]
    PRESTART_STATES = [STATE_IDLE, STATE_UNDEF, STATE_BLOCKED]
    UNDEF_JOB = "-"

    STATE_COLORS = {
        STATE_IDLE: "white",
        STATE_RUNNING: "yellow",
        STATE_SUCCESSFULL: "lawngreen",
        STATE_FAILED: "red",
        STATE_CANCELLED: "deepskyblue",
        STATE_UNDEF: "gray",
        STATE_BLOCKED: "darkorange",
        STATE_RESET: "white"
    }

    def __init__(self, name="", jobpath=None, tree=None, logfile=None, xml=None, execiter=None, mustcomplete=True, subtree=None, arguments=None, resources=None, href="", tcolor="lavender"):
        if arguments is None:
            arguments = []
        if resources is None:
            resources = []
        if xml is not None:
            if tree is None:
                # TODO make tree param required
                raise TreeUndefinedError("Tree is not known")
            if xml.tag != "execJob":
                raise XMLError("Expect to find execJob in xml.")
            try:
                name = xml.attrib["name"]
                jobpath = xml.attrib.get("jobpath", None)
                uuidi = uuid.UUID(xml.attrib["uuid"])
                mustcomplete = xml.attrib.get("mustcomplete", False) == "True"
                subtreeuuid = xml.attrib.get("subtreeuuid", None)
                logfile = xml.attrib.get("logfile", None)
                href = xml.attrib.get("href", "")
                tcolor = xml.attrib.get("tcolor", tcolor)
            except KeyError:
                logging.error("Required xml attribute is not found.")
                raise
            for arg in xml.findall("execArg"):
                try:
                    arguments.append(arg.attrib["value"])
                except KeyError:
                    logging.error(
                        "Argument of is missing required xml attribute ({0}:{1})."
                        .format(
                            legenditem.base,
                            legenditem.sourceline
                        )
                    )
                    raise
            resources = []
            for resource in xml.findall("execResource"):
                fr = tree.find_resource(resource.attrib["uuid"])
                if fr is not None:
                    resources.append(fr)
            if logfile == "":
                logfile = None
            if jobpath == "":
                jobpath = None
            elif subtreeuuid is not None:
                subtreeuuid = uuid.UUID(subtreeuuid)
                subtree = tree.find_subtree(subtreeuuid, None)
                if subtree is None:
                    raise TreeDefinedError(
                        "The referenced subtree cannot be found."
                    )

        else:
            uuidi = uuid.uuid4()

        self.events = {}
        for e in self.STATES:
            self.events[e] = gevent.event.Event()
        self.statechange = gevent.event.Event()
        self.name = name
        self.uuid = uuidi
        self._tree = tree
        self._state = None
        self.state = self.STATE_IDLE
        self.subtree = subtree
        self.jobpath = jobpath
        self.execiter = execiter
        self.mustcomplete = mustcomplete
        self.logfile = logfile
        self._progress = -1
        self.override = False
        self.arguments = arguments
        self.resources = resources
        self.execcount = 0
        self.failcount = 0
        self.href = href
        self.tcolor = tcolor

    def xml(self):
        """ Generate xml Element object representing of ExecJob """
        args = {
            "name": str(self.name),
            "uuid": str(self.uuid.hex),
            "mustcomplete": str(self.mustcomplete),
            "href": str(self.href),
            "tcolor": self.tcolor
        }
        if self.jobpath is not None:
            args["jobpath"] = str(self.jobpath)
        elif self.subtree is not None:
            args["subtreeuuid"] = str(self.subtree.uuid.hex)
        if self.logfile is None:
            args["logfile"] = ""
        else:
            args["logfile"] = self.logfile
        eti = et.Element("execJob", args)

        if self.arguments is not None:
            for arg in self.arguments:
                eti.append(et.Element("execArg", {"value": arg}))

        if self.resources is not None:
            for resource in self.resources:
                eti.append(et.Element("execResource", {"uuid": str(resource.uuid.hex)}))

        return eti

    def __str__(self):
        return "<ExecJob {0}>".format(self.name)

    # TODO: setter for sub tree to ensure only subtrees are iterable

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
            raise JobError(
                "jobpath cannot be modified after job has been started"
            )

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if value not in self.STATES:
            raise UnknownStateError("Job state cannot be changed to {0}.".format(value))
        if self._state == value:
            return
        self._state = value
        self.statechange.set()
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

    def _dot_node(self, font):
        if self.progress >= 0:
            label = "{0}\n{1}".format(self.name, self.progress)
        else:
            label = self.name
        kw = {
            "style": "filled",
            "fillcolor": self.STATE_COLORS[self.state],
            "color": self.tcolor,
            "penwidth": "3",
            "fontname": font,
        }
        if self.href:
            kw["href"] = "\"{0}\"".format(self.href)
        node = pydot.Node(label, **kw)
        return node

    def _dot_tree(self, font):
        subg = pydot.Subgraph(
            self.subtree.cluster_name,
            color="deepskyblue",
            fontname=font
        )
        if self.subtree.iterator is None:
            subg.set_label(self.name)
        else:
            subg.set_label(
                "{0} {1}/{2}".
                format(
                    self.name,
                    self.subtree.iterator.run,
                    self.subtree.iterator.len()
                )
            )
        self.subtree.dot_graph(subg)
        return subg

    def dot(self, graph, font):
        """ Generate dot object representing ExecJob """
        if self.jobpath is not None:
            rep = self._dot_node(font)
            graph.add_node(rep)
        elif self.subtree is not None:
            rep = self._dot_tree(font)
            graph.add_subgraph(rep)
            graph.set_compound("True")

    def has_defined_anscestors(self):
        # caching results will peformance
        for parent in self.parents():
            if parent.is_defined():
                return True
            elif parent.has_defined_anscestors():
                return True
        return False

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
            errors.append(
                "subtree and jobpath of {0} are set. Only one can be set."
                .format(self.name)
            )
        elif self.jobpath is not None:
            if self.jobpath == self.UNDEF_JOB:
                # We allow existance of no-op jobs
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

    def is_failed(self):
        return self.state == ExecJob.STATE_FAILED

    def is_cancelled(self):
        return self.state == ExecJob.STATE_CANCELLED

    def is_defined(self):
        return self.state != ExecJob.STATE_UNDEF

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
        if self.state == self.STATE_RUNNING:
            return False
        if self.state in self.DONE_STATES:
            return True
        logging.debug("Canceling {0}".format(self.name))
        self.state = self.STATE_CANCELLED
        return True


    def _release_resources(self, resources):
        logging.debug("releasing: {0}".format(resources))
        for r in resources:
            r.release()

    def _acquire_resources(self, acquire_timeout=60, max_attempts=1000):
        if len(self.resources) < 1:
            return True
        self.state = self.STATE_BLOCKED
        reserved = []
        lastacquire = False
        backofftime = len(self.resources) * acquire_timeout
        attempt = 0
        while True:
            for resource in self.resources:
                if resource.reserve(timeout=acquire_timeout):
                    reserved.append(resource)
                    lastacquire = True
                else:
                    lastacquire  = False
                    break
            if lastacquire == False:
                attempt += 1
                self._release_resources(reserved)
                gevent.sleep(backofftime + random.randint(0, acquire_timeout))
                if max_attempts > 0 and attempt >= max_attempts:
                    break
            else:
                break
        self.state = self.STATE_IDLE
        return lastacquire

    def read_log(self, size):
        if self.logfile is None:
            return ""
        try:
            with open(self.logfile, 'r') as fd:
                fd.seek(0, 2)
                filesize = fd.tell()
                fd.seek(max(-size, -filesize), 2)
                return fd.read()
        except:
            logging.exception("Failed to read log file")
            return ""

    def start(self):
        if self.state == self.STATE_UNDEF:
            logging.debug("{0} is short circuiting ({1})".format(self.name, self.state))
            self.events[self.STATE_SUCCESSFULL].set()
            return True
        if self.is_success():
            return False
        g = Greenlet.spawn(self._run)
        return True

    def _run(self):
        logging.debug("{0} is idling ({1})".format(self.name, self.state))
        self._parent_wait()
        if self.state in self.DONE_STATES:
            return None

        if not self._acquire_resources():
            self.state = self.STATE_FAILED
            logging.warning(
                    "Resource deadlock prevention exceeded max attemps for {0}.".
                    format(self.name)
            )
            return False

        try:
            logging.debug("{0} is starting".format(self.name))
            self.state = self.STATE_RUNNING
            # rcubic.refreshStatus(self)
            if self.jobpath is not None:
                args = [self.jobpath]
                if self.arguments is not None:
                    args.extend(self.arguments)
                if self.tree.argument() is not None:
                    args.append(self.tree.argument())
                logging.debug("starting {0} {1}".format(self.name, args))
                if self.logfile is not None:
                    with open(self.logfile, 'a') as fd:
                        rcode = self._popen(
                            args,
                            cwd=self.tree.cwd,
                            stdout=fd,
                            stderr=fd
                        )
                else:
                    rcode = self._popen(
                        args,
                        cwd=self.tree.cwd
                    )
            elif self.subtree is not None:
                logging.debug("starting {0} {1}".format(self.name, "subtree"))
                rcode = self.subtree.iterrun()
                # TODO: compute rcode
                logging.warning("Sub tree is not checked for success before proceeding")
                rcode = 0
            logging.debug("finished {0} status {1}".format(self.name, rcode))
        finally:
            self._release_resources(self.resources)

        self.execcount += 1
        if rcode == 0:
            self.state = self.STATE_SUCCESSFULL
            return True
        else:
            self.failcount += 1
            self.state = self.STATE_FAILED
            return False


class ExecIter(object):
    def __init__(self, name=None, args=None):
        if args == None:
            self.args = []
        else:
            self.args = args
        self.run = 0
        self.valid = None
        self.name = name

    def __str__(self):
        return "<ExecIter {0}>".format(self.name)

    def is_exhausted(self):
        logging.debug("is_exhausted {0}>{1}".format(self.run, len(self.args)))
        if self.run >= len(self.args):
            return True
        return False

    def len(self):
        return len(self.args)

    def increment(self, inc=1):
        self.run += inc
        return self.run < len(self.args)

    @property
    def argument(self):
        if len(self.args) <= 0:
            return ""
        elif self.run > len(self.args):
            return self.args[len(self.args)-1]
        return self.args[self.run]


class ExecResource(object):
    def __init__(self, tree, name="", avail=0, xml=None):
        if xml is not None:
            if xml.tag != "execResource":
                raise XMLError("Expect to find execResource in xml.")
            name = xml.attrib.get("name", "")
            uuidi = uuid.UUID(xml.attrib["uuid"])
            avail = xml.attrib.get("avail", -1)
        else:
            uuidi = uuid.uuid4()
        self.name = name
        self.avail = avail
        self.used = 0
        self.event = gevent.event.Event()
        self.uuid = uuidi
        tree.resources.append(self)

    def __str__(self):
        return "<ExecResource {0}>".format(self.name)

    def xml(self):
        args = {
            "name": str(self.name),
            "uuid": str(self.uuid.hex),
            "avail": str(self.avail),
        }
        eri = et.Element("execResource", args)
        return eri

    def reserve(self, blocking=True, timeout=None):
        if self.avail < 0:
            return True
        if self.used < self.avail:
            self.used += 1
        elif blocking:
            try:
                with gevent.Timeout(timeout):
                    while self.used >= self.avail:
                        if self.event.wait(1):
                            self.event.clear()
                    self.used += 1
            except gevent.timeout.Timeout:
                return False
        else:
            return False
        return True

    def release(self):
        if self.avail < 0:
            return
        if self.used <= 0:
            self.used = 0
        else:
            self.used -= 1
        self.event.set()


class ExecDependency(object):
    def __init__(self, parent, child, state=ExecJob.STATE_SUCCESSFULL):
        self.parent = parent
        self.child = child
        self.color = {"undefined": "palegreen", "defined": "deepskyblue"}

        if state in ExecJob.STATES:
            self.state = state
        else:
            raise UnknownStateError("Unknown State")

    def _dot_add(self, parent_target, child_target, graph):
        edge = pydot.Edge(parent_target, child_target)
        if self.parent.is_defined():
            edge.set_color(self.color["defined"])
        else:
            edge.set_color(self.color["undefined"])
        if parent_target is None:
            parent_target = "None"
        if child_target is None:
            child_target = "None"
        graph.add_edge(edge)
        return edge

    def __str__(self):
        return "<ExecDependency {0}-{1}>".format(self.parent.name, self.child.name)

    def dot(self, graph):
        """ Generate dot edge object repersenting dependency """

        if self.parent.subtree is not None and self.child.subtree is not None:
            # This is a bit tricky we need to loop 2x but the real problems is that it will look UGLY
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
        args = {"parent": self.parent.uuid.hex, "child": self.child.uuid.hex, "state": `self.state`, "dcolor": self.color["defined"], "ucolor": self.color["undefined"]}
        eti = et.Element("execDependency", args)
        return eti


class ExecTree(object):
    def __init__(self, xml=None):
        self.jobs = []
        self.deps = []
        self.subtrees = []
        self.done_event = gevent.event.Event()
        self._done = False
        self.resources = []
        self.cancelled = False
        self.started = False
        self.legend = {}
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
            # print("name:{0} href:{1} uuid:{2}".format(self.name, self.href, self.uuid))
            for xmlres in xml.findall("execResource"):
                ExecResource(self, xml=xmlres)
            for xmlsubtree in xml.findall("execTree"):
                self.subtrees.append(ExecTree(xmlsubtree))
            for xmljob in xml.findall("execJob"):
                self.jobs.append(ExecJob(tree=self, xml=xmljob))
            for xmldep in xml.findall("execDependency"):
                self.add_dep(xml=xmldep)
            for legenditem in xml.findall("legendItem"):
                try:
                    key = legenditem.attrib["name"]
                    value = legenditem.attrib["value"]
                    self.legend[key] = value
                except KeyError:
                    logging.error(
                        "Legend item is missing required xml attribute ({0}:{1})."
                        .format(
                            legenditem.base,
                            legenditem.sourceline
                        )
                    )
                    raise

    @property
    def cluster_name(self):
        # pydot does not properly handle space in subtree
        name = self.name.replace(" ", "_")
        return "\"cluster_{0}\"".format(name)
        # return "\"cluster_{0}\"".format(self.name)

    def xml(self):
        args = {
            "version": "1.0",
            "name": self.name,
            "href": self.href,
            "uuid": self.uuid.hex,
            "cwd": self.cwd
        }
        eti = et.Element("execTree", args)
        for job in self.jobs:
            if job.subtree is not None:
                eti.append(job.subtree.xml())
            # else:
            #	print("job {0} does not have a subtree.".format(job.name))
            eti.append(job.xml())
        for dep in self.deps:
            eti.append(dep.xml())
        for resource in self.resources:
            eti.append(resource.xml())
        for key, value in self.legend.iteritems():
            eti.append(et.Element("legendItem", {key: value}))
        return eti

    def __str__(self):
        return "<ExecTree {0}>".format(self.name)

    def __getitem__(self, key, default=None):
        for job in self.jobs:
            if job.name == key:
                return job
        return default

    def find_resource(self, needle, default=None):
        for resource in self.resources:
            if resource.uuid.hex == needle:
                return resource
            elif resource.name == needle:
                return resource
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
            raise JobDefinedError("Job with same name ({0}) already part of tree".format(job))
        if job.subtree is not None and job.subtree not in self.subtrees:
            self.subtrees.append(job.subtree)
        job.tree = self
        self.jobs.append(job)

    def add_dep(self, parent=None, child=None, state=ExecJob.STATE_SUCCESSFULL, xml=None):
        colors = None
        dep = None
        if xml is not None:
            if xml.tag != "execDependency":
                raise XMLError("Expect to find execDependency in xml.")
            parent = xml.attrib["parent"]
            child = xml.attrib["child"]
            state = int(xml.attrib["state"])
            colors = {"undefined": xml.attrib["ucolor"], "defined": xml.attrib["dcolor"]}

        # Ensure parent and child are ExecJobs
        if not isinstance(parent, ExecJob):
            parent = self.find_job(parent, parent)
            if not isinstance(parent, ExecJob):
                raise JobUndefinedError("Job {0} is needed by {2} but is not defined in (tree: {1}).".format(parent, self.name, child))
        if not isinstance(child, ExecJob):
            child = self.find_job(child, child)
            if not isinstance(child, ExecJob):
                raise JobUndefinedError("Child job {0} is not defined in tree: {1}.".format(child, self.name))

        # Parent and Child must be members of the tree
        for k in [child, parent]:
            if k not in self.jobs:
                raise JobUndefinedError("Job {0} is not part of the tree: {1}.".format(k.name, self.name))

        if parent is child:
            raise DependencyError("Child cannot be own parent ({0}).".format(parent.name))

        if parent not in child.parents():
            dep = ExecDependency(parent, child, state)
            self.deps.append(dep)
        else:
            logging.warning("Duplicate dependency.")

        if colors is not None:
            dep.color = colors

        return dep

    def argument(self):
        if self.iterator is None:
            return None
        else:
            return self.iterator.argument

    def _gparent_compile(self, job, gparents):
        parents = job.parents()
        if job in gparents:
            return gparents[job] + parents
        gparents[job] = []
        for parent in parents:
            # we don't use extend to dedupe
            for e in self._gparent_compile(parent, gparents):
                if e not in gparents[job]:
                    gparents[job].append(e)
        return gparents[job] + parents

    def dot_graph(self, graph=None, arborescent=False, font="sans-serif"):
        if graph is None:
            graph = pydot.Dot(
                graph_type="digraph",
                bgcolor="black",
                fontcolor="deepskyblue",
                fontname=font
            )
        for job in self.jobs:
            job.dot(graph, font)
        if arborescent:
            gparents = {}
            for job in self.jobs:
                self._gparent_compile(job, gparents)
            for dep in self.deps:
                if dep.parent not in gparents[dep.child]:
                    dep.dot(graph)
        else:
            for dep in self.deps:
                dep.dot(graph)
        if len(self.legend) > 0:
            legend = ""
            for key, value in self.legend.iteritems():
                legend = "{2}{0}:\t{1}\\n".format(key, value, legend)
            legend = "\"{0}\"".format(legend)
            sg = pydot.Subgraph("noncelegendnonce", rank="sink")
            sg.add_node(
                pydot.Node(
                    "noncelegendnonce",
                    shape="box",
                    margin="0",
                    label=legend,
                    color="deepskyblue",
                    fontcolor="deepskyblue",
                    fontname=font
                )
            )
            graph.add_subgraph(sg)
        return graph

    def _rjobs(self):
        "generates all jobs, even those belonging to subtrees"
        for job in self.jobs:
            yield job
            if job.subtree is not None:
                for sjob in job.subtree._rjobs():
                    yield sjob

    def json_status(self, status=None):
        if status is None:
            status = {}
        for job in self._rjobs():
            status[job.name] = {
                "status": job.STATE_COLORS[job.state],
                "progress": job.progress
            }
            if job.subtree is not None and job.subtree.iterator is not None:
                status[job.name]["iteration"] = "{0}/{1}".format(
                    job.subtree.iterator.run,
                    job.subtree.iterator.len()
                )
        return simplejson.dumps(status)

    # dot's html map output is: "x,y x,y x,y"
    # but it should be: "x,y,x,y,x,y"
    FIXCOORD = re.compile(' (?=[\d]*,[\d]*)')

    def write_status(self, svg, json, overwrite=False, arborescent=True):
        if overwrite or not os.path.exists(svg):
            with open(svg, "w") as sfd:
                g = self.dot_graph(arborescent=arborescent)
                logging.debug(g.to_string())
                c = self.FIXCOORD.sub(',', g.create_svg())
                sfd.write(c)
        with open(json, "w") as jfd:
            jfd.write(self.json_status())

    def stems(self):
        """
        Finds and returns first job of most unconnected graphs

        WARNING This will not find stem of subtrees with cycles
        """
        stems = []
        for job in self.jobs:
            if job.has_defined_anscestors() or not job.is_defined():
                continue
            stems.append(job)
        return stems

    def leaves(self):
        """
        Finds and returns all the leaf jobs of a tree
        """
        leaves = []
        for job in self.jobs:
            if len(job.child_deps()) > 0:
                leaves.append(job)
        return leaves

    def validate(self):
        errors = []
        stems = self.stems()

        if len(stems) == 0:
            errors.append("Tree {0} is empty, has 0 stems."
                .format(self.name, stems)
            )
        elif len(stems) > 1:
            errors.append(
                "Tree {0} has multiple stems ({1})."
                .format(
                    self.name,
                    " ".join([stem.name for stem in stems])
                )
            )

        for stem in stems:
            visited = []

            cycles = not self.validate_nocycles(stem, visited)
            if cycles:
                errors.append("Tree {0} has cycles.".format(self.name))

            # What jobs are not connected to stem?
            unconnected = []
            for job in self.jobs:
                if job.is_defined() and job not in visited:
                    unconnected.append(job)
            if len(unconnected) > 0:
                errors.append(
                    "The jobs {0} are not connected to {1}."
                    .format([job.name for job in unconnected], stem.name)
                )

        for job in self.jobs:
            errors.extend(job.validate())

        return errors


    def validate_nocycles(self, job, visited, parents=None):
        """ Ensure we do not have cyclical dependencies in the tree """
        if parents is None:
            parents = []
        # logging.debug("validate job: {0} (parents:{1} children:{2})".format(job.name, [v.name for v in parents], [c.name for c in job.children()]))
        if job in parents:
            return False
        parents.append(job)
        if job not in visited:
            visited.append(job)
        for child in job.children():
            if child in visited:
                continue
            if not self.validate_nocycles(child, visited, parents):
                return False
        parents.remove(job)
        return True

    def _is_done_event(self, instance):
        self.is_done()

    def is_done(self):
        for job in self.jobs:
            if job.mustcomplete:
                if not job.is_done():
                    logging.debug("{0} is not done".format(job.name))
                    return False
        self.done_event.set()
        self.cancel()
        self.done = True
        return True

    def is_success(self):
        for job in self.jobs:
            if not job.is_success():
                return False
        return True

    def cancel(self):
        if self.cancelled:
            return
        for job in self.jobs:
            job.cancel()

    def run(self, blocking=True, timeout=None):
        logging.debug("About to spin up jobs for {0}".format(self.name))
        for job in self.jobs:
            for ek, ev in job.events.items():
                ev.rawlink(self._is_done_event)
            job.start()
        self.started = True
        if blocking:
            try:
                with gevent.Timeout(timeout):
                    logging.debug(
                        "Jobs have been spun up for {0}. I'm gonna chill"
                        .format(self.name)
                    )
                    gevent.sleep(1)
                    logging.debug(
                        "Chilling is done. Impatiently waiting for jobs of {0} to finish"
                        .format(self.name)
                    )
                    self.join()
                    logging.debug(
                        "Tree {0} has finished execution."
                        .format(self.name)
                    )
            except gevent.timeout.Timeout:
                logging.warning("Execution of tree exceeded time limit ({0} seconds).".format(timeout))
                self.cancel()
                return

    # TODO make event based
    def _json_updater(self, path):
        while not self._done:
            gevent.sleep(5)
            logging.debug("updating json")
            with open(path, "w") as fd:
                fd.write(self.json_status())

    def spawn_json_updater(self, path):
        Greenlet.spawn(self._json_updater, path)

    def advance(self):
        logging.debug("Advancing tree {0}.".format(self.name))
        self.done_event.clear()
        if self.iterator is not None:
            inc = self.iterator.increment()
        else:
            inc = True
        if inc:
            for job in self.jobs:
                job.reset()

    def iterrun(self):
        if self.iterator is None:
            logging.debug("Iterator is none")
            self.run()
            return None
        if self.iterator.is_exhausted():
            logging.debug("Iterator is exhausted")
            return False
        while True:
            self.run()
            self.advance()
            if self.iterator.is_exhausted():
                break

    def join(self):
        self.done_event.wait()

    def extend_args(self, args):
        for job in self.jobs:
            job.arguments.extend(args)
        for subtree in self.subtrees:
            subtree.extend_args(args)
