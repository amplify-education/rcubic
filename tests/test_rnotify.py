#!/usr/bin/python
# vim: ts=4 et sts filetype=python
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

import unittest
from RCubic.RCubicNotification import RCubicNotification

defgroup="foo"
defemail="foo@example.com"


class TestRN(unittest.TestCase):

    def setUp(self):
        self.notify = RCubicNotification()

    def test_add_email(self, group=defgroup, email=defemail):
        """Add an email by group name"""
        self.notify.add_email(group, email)
        self.assertEquals(self.notify.email[group], email)

    def test_disable(self):
        """Test disabling of notification"""
        self.notify.disable()
        self.assertFalse(self.notify.enabled)

    def test_send(self, group=defgroup):
        """Test sending email
        We cannot do a full test as we cannot rely on mailserver being
        there. Maybe make a fake smtp lib?"""
        self.test_add_email()
        rval = self.notify.send([group], "test", "message")
        # must assume failure as local mail sever probably does not exist
        self.assertFalse(rval)

    def test_send_disabled(self, group=defgroup):
        """Test not sending email, disabled mode"""
        self.test_disable()
        self.test_send(group=defgroup)

    def test_send_badgroup(self):
        self.test_send("bar")

    def test_has_groups(self):
        """Test group look up functionality"""
        self.assertTrue(self.notify.has_groups([defgroup]))
