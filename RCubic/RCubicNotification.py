#!/usr/bin/env python
# vim: ts=4 et sts filetype=python

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

""" This module provides communication abstraction for rcubic"""

from email.mime.text import MIMEText
import smtplib
import logging


class RCubicNotification(object):

    """Manages notification groups and handles sending of messages"""

    def __init__(
            self, emailfrom='rcubic@example.com', subject='rcubic:',
            server='localhost', carboncopy=''
        ):
        self.email = {}
        self.enabled = True
        self.emailfrom = emailfrom
        self.subject = subject
        self.server = server
        self.carboncopy = carboncopy

    def disable(self):
        """Disable all outbound communication"""
        if self.enabled == True:
            logging.debug("Notifications have been disabled.")
        self.enabled = False

    def add_email(self, group, email):
        """Add mapping betwen group and email"""
        self.email[group.lower()] = email

    def send(self, groups, subject, message):
        """Send message"""
        if self.enabled:
            msg = MIMEText(message)
            recipients = []
            for group in groups:
                if group.lower() in self.email:
                    recipients.append(self.email[group.lower()])
                else:
                    logging.info(
                        "Failed so send notification to group {0},"
                        "no matching email".format(group)
                    )
            recipients.append(self.carboncopy)
            msg['Subject'] = "{0} {1} {2}".format(
                self.subject, ", ".join(groups), subject)
            msg['From'] = self.emailfrom
            msg['To'] = ', '.join(recipients)
            try:
                smtp = smtplib.SMTP(self.server)
                smtp.sendmail(self.emailfrom, recipients, msg.as_string())
                smtp.quit()
                return True
            except Exception, err:
                logging.exception(
                    "Sending email failed! Message: {0} Error:"
                    .format(msg, err)
                )
                return False
        else:
            logging.debug("Notification skipped: {0}, {1}, {2}"
                .format(groups, subject, message)
            )
            return False

    def has_groups(self, groups):
        """Return all groups which don't have matching email"""
        return [ group for group in groups if group.lower() not in self.email ]
