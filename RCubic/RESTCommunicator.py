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
import logging

# RESTServer imports
from MiniREST.RESTServer import RESTServer, responseCodes, responseTypes


class RESTCommunicator(RESTServer):
    """RESTCommunicator - creates a new RESTCommunicator instance.
    Extends RESTServer with custom functions.

    """

    def __init__(self, rcubic, bind='0.0.0.0', port=8002, *args, **kwargs):
        """Create a RESTCommunicator. Call 'start' to start the server.

        Keyword arguments:
        bind -- the address to which the server binds (default '0.0.0.0')
        port -- the port on which the server listens (default 8002)
        portRange -- choose first available port to listen on

        """
        super(RESTCommunicator, self).__init__(bind, port, *args, **kwargs)
        self.registerFunction('progress', self._progress, token=True)
        self.registerFunction('reclone', self._reclone, token=True)
        self.registerFunction('cancel', self._cancel, token=True)
        self.registerFunction('reschedule', self._reschedule, token=True)
        self.registerFunction('manualOverride', self._manualOverride, token=True)
        self.registerFunction('supported', self._supported, token=True)
        self.features = ['progress', 'reclone', 'reschedule', 'manualOverride', 'cancel']
        self.rcubic = rcubic

    def _progress(self, env, start_response, post):
        """Reponds to a 'progress' request and calls rcubic._updateProgress(..)

        Keyword arguments:
        env -- expects a 'data' list TODO: paramaters

        """
        logging.debug("Received Progress report for %s: %s" % (post['scriptName'], post['message']))
        resp = self.rcubic.updateProgress(post['scriptName'], post['message'])
        start_response(responseCodes[200], responseTypes['plaintext'])
        return str(resp)

    def _reclone(self, env, start_response, post):
        """Responds to a 'reclone' request and calls rcubic._initGit()

        Keyword arguments:
        env -- doesn't expect any paramaters

        """
        logging.info("Received reclone request")
        resp = self.rcubic._initGit()
        start_response(responseCodes[200], responseTypes['plaintext'])
        return str(resp)

    def _reschedule(self, env, start_response, post):
        """Reponds to a 'reschedule' request and calls rcubic.reschedule(scriptName)

        Keyword argument:
        env -- expects a 'scriptName'

        """
        scriptName = post['scriptName']
        logging.info("Received reschedule request for %s." % scriptName)
        resp = self.rcubic.reschedule(scriptName)
        start_response(responseCodes[200], responseTypes['plaintext'])
        if not resp:
            logging.warning("Reschedule request for %s failed." % post['scriptName'])
        return str(bool(resp))

    def _manualOverride(self, env, start_response, post):
        """Responds to a 'manualOverride' request and calls rcubic.manualOverride(scriptName)

        Keyword argument:
        env -- expects a scriptName

        """
        scriptName = post['scriptName']
        logging.info("Received override request for %s." % scriptName)
        resp = self.rcubic.manualOverride(scriptName)
        start_response(responseCodes[200], responseTypes['plaintext'])
        if not resp:
            logging.warning("Override request for %s failed." % scriptName)
        return str(bool(resp))

    def _supported(self, env, start_response, post):
        """Responds to a requested asking if a feature is supported

        Keyword argument:
        env -- expects a 'feature'

        """
        feature = post['feature']
        start_response(responseCodes[200], responseTypes['plaintext'])
        if feature in self.features:
            return str(True)
        else:
            return str(False)

    def _cancel(self, env, start_response, post):
        """Responds to a 'cancel' request and calls rcubic.abort()

        Keyword arguments:
        env -- doesn't expect any paramaters

        """
        logging.info("Received cancel request")
        resp = self.rcubic.abort()
        start_response(responseCodes[200], responseTypes['plaintext'])
        return str(resp)
