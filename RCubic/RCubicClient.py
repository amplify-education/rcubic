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


from MiniREST.RESTClient import RESTClient


class RCubicClient(RESTClient):
    """Extends the RESTClient class to provide an interface to an RCubicServer.

    """

    def __init__(self, server='localhost', port=8002, *args, **kwargs):
        """Create a RCubicClient to connect to a server.

        Keyword arguments:
        server -- domain to connect to (default 'localhost')
        port -- the port to connect to (default 8002)

        """
        super(RCubicClient, self).__init__(server, port, *args, **kwargs)

    def checkInUser(self, user, checkInName, address=None, port=None, *args, **kwargs):
        """Sends a 'checkInUser' request to the RCubicServer.

        Keyword arguments:
        user -- user who is checking in
        checkInName -- the checkin response name

        """
        # user needs to be str(user) bc user is an xmpp object
        return self.getResponse("checkInUser", data={"user": str(
            user), "checkInName": checkInName, "token": self.token}, address=address, port=port, *args, **kwargs)

    def progress(self, scriptName=None, version=None, message=None, *args, **kwargs):
        """Updates the percentage of script completion.

        Keyword arguments:
        scriptName -- name of script
        version -- version name
        message -- percentage (integer [0-100])

        """
        return self.getResponse("progress", data={"scriptName": scriptName, "version": version, "kind":
                                "PROGRESS", "message": message, "token": self.token}, *args, **kwargs)

    def reclone(self, *args, **kwargs):
        """

        """
        return self.getResponse("reclone", data={"token": self.token}, *args, **kwargs)

    def reschedule(self, scriptName=None, *args, **kwargs):
        """

        """
        return self.getResponse("reschedule", data={"scriptName": scriptName, "token": self.token}, *args, **kwargs)

    def manualOverride(self, scriptName=None, *args, **kwargs):
        """

        """
        return self.getResponse(
            "manualOverride", data={"scriptName": scriptName, "token": self.token}, *args, **kwargs)

    def supported(self, feature=None, *args, **kwargs):
        """Asks the server if it supports a feature.

        """
        return self.getResponse("supported", data={"feature": feature, "token": self.token}, *args, **kwargs)

    def cancel(self, *args, **kwargs):
        """
        Asks server to gracefully exit.
        """
        return self.getResponse("cancel", data={"token": self.token}, *args, **kwargs)
