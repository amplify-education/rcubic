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


import os
import sys
import time
import subprocess
import re
import errno
import fcntl
import sqlite3
import logging
from operator import attrgetter

import gevent
from gevent import socket


class VersionCompareError(Exception):
    pass


class FatalRuntimeError(RuntimeError):
    pass


def dict_by_attr(series, name):
    a = attrgetter(name)
    return dict((a(item), item) for item in series)


def popenNonblock(args, data='', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=None, logFile=None):
    """Communicate with the process non-blockingly.

    If logFile is defined print the process's output line by line to that file
    """
    if logFile:
        f = open(logFile, 'a')
        stdout = f
        stderr = f
    p = subprocess.Popen(args, stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd)
    real_stdin = p.stdin if stdin == subprocess.PIPE else stdin
    fcntl.fcntl(real_stdin, fcntl.F_SETFL, os.O_NONBLOCK)  # make the file nonblocking
    real_stdout = p.stdout if stdout == subprocess.PIPE else stdout
    fcntl.fcntl(real_stdout, fcntl.F_SETFL, os.O_NONBLOCK)  # make the file nonblocking

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

    chunks = []
    if stdout == subprocess.PIPE:
        while True:
            try:
                chunk = p.stdout.read(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            except IOError:
                ex = sys.exc_info()[1]
                if ex[0] != errno.EAGAIN:
                    raise
                sys.exc_clear()
            socket.wait_read(p.stdout.fileno())
        p.stdout.close()

    output = ''.join(chunks)

    while True:
        returncode = p.poll()
        if returncode is not None:
            break
        else:
            gevent.sleep(1)

    return (returncode, output)


class LogToDB(object):
    def __init__(self, dbPath):
        self.dbPath = dbPath
        newdb = (not os.path.exists(self.dbPath))
        self.conn = sqlite3.connect(self.dbPath)
        self.conn.isolation_level = None  # set to autocommit
        if newdb:
            self._initDB(self.conn)
        else:
            self._checkDBVersion(self.conn)

    def _initDB(self, conn):
        # TODO does githead have to be in primary key?
        query = "CREATE TABLE events (time integer, groupe text, version text, githead text, job text, status text, " \
                                " PRIMARY KEY (time, groupe, job, status))"
        self.conn.execute(query)
        query = "CREATE TABLE latest_events (time integer, groupe text, version text, githead text, job text, status text, " \
                                " FOREIGN KEY (time, groupe, job, status) REFERENCES event(time, groupe, job, status), " \
                                " UNIQUE (groupe, job))"
        self.conn.execute(query)
        query = "CREATE TABLE rcubic_db_support(db_version text unique)"
        self.conn.execute(query)
        query = 'INSERT INTO rcubic_db_support VALUES("1.0")'
        self.conn.execute(query)
        self.conn.commit()

    def _checkDBVersion(self, conn):
        try:
            rows = list(self.conn.execute('SELECT db_version from rcubic_db_support where db_version="1.0"'))
        except:
            raise FatalRuntimeError("Unsupported db_version. Please migrate")

    def saveStatus(self, group, version, status, githead=None, job="NONE"):
        if job.upper() == "NONE":
            job = job.upper()
        timestamp = int(time.time())
        self.conn.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?)", (timestamp, group, version, githead, str(job), status))
        self.conn.execute("INSERT OR REPLACE INTO latest_events VALUES (?,?,?,?,?,?)", (timestamp, group, version, githead, str(job), status))
        self.conn.commit()
        return True

    def isNewestVersion(self, group, version, successStatus):
        """Check if the latest group entry with status SUCCEEDED and job NONE is newer than version."""
        query = "SELECT version FROM events WHERE groupe = ? AND JOB = ? AND status = ? ORDER BY time DESC LIMIT 1"
        rows = list(self.conn.execute(query, (group, 'NONE', successStatus)))
        if rows:
            try:
                return self.verComp(version, rows[0][0]) > 0
            except VersionCompareError:
                logging.warning(
                        "Versions ({0}, {1}) cannot be compared due to format error for group {2}."
                        .format(version, rows[0][0], group)
                )
                return True
        else:
            return True

    # def getUnfinished(self, group=None):
    #	query = "SELECT * FROM latest_events WHERE status = ? "
    #	if group:
    #		result = self.conn.execute(query + " AND groupe = ? ", (Status.STARTED, group))
    #	else:
    #		result = self.conn.execute(query, (Status.STARTED,))
    #	return list(result)

    # def closeUnfinished(self, group, job):
    # probably a good idea to log when ever this is run because it mucks with audit log
    #	unfinishedEntries = self.getUnfinished(group)
    #	for entry in unfinishedEntries:
    #		if entry[3] == job:
    #			self.saveStatus(entry[1], entry[2], Status.FAILED, entry[3])
    # def getStatus(self, group, version, job=None):
    #	"""Returns single most relavant 'Status' update matching criteria from arguments."""
    #	query = "SELECT status FROM latest_events WHERE groupe = ? AND version = ? "
    #	if job:
    #		result = self.conn.execute(query + " AND job = ? ", (group, version, job))
    #	else:
    #		result = self.conn.execute(query, (group, version))
    #	stati = [row[0] for row in result]
    #	importance = [Status.FAILED, Status.QUEUED, Status.STARTED, Status.SUCCEEDED]
    #	for imp in importance:
    #		if imp in stati:
    #			return imp
    #	return "NONE"
    @classmethod
    def verComp(cls, a, b):
        #-1 b greater
        # 0 same
        # 1 a greater
        alphas = re.compile(r"[a-zA-Z]")
        rev = re.compile(r"[-_~]")
        dots = re.compile(r"[.,]")

        a = re.sub(alphas, "", a)
        a = rev.split(a, 1)
        a[0] = dots.split(a[0])

        b = re.sub(alphas, "", b)
        b = rev.split(b, 1)
        b[0] = dots.split(b[0])

        while len(a[0]) < len(b[0]):
            a[0].append(0)
        while len(b[0]) < len(b[0]):
            b[0].append(0)

        for a1, b1 in zip(a[0], b[0]):
            try:
                a1 = int(a1)
                b1 = int(b1)
            except ValueError:
                raise VersionCompareError("Integer conversion failure")
            if a1 == b1:
                continue
            elif a1 > b1:
                return 1
            elif a1 < b1:
                return - 1
        if len(a) == len(b):
            if len(a) == 1:
                return 0
            else:
                return cls.verComp(a[1], b[1])
        elif len(b) > len(a):
            return 1
        elif len(a) > len(b):
            return - 1
