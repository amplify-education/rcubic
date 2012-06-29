# Rest server
from MiniREST.RESTServer import RESTServer, responseCodes, responseTypes

class RCubicServer(RESTServer):
    """RCubicServer - creates a new RCubicServer instance.
    Extends RESTServer with custom functions.

    """

    def __init__(self, *args, **kwargs):
        """Create a RCubicServer. Call 'start' to start the server.

        Keyword arguments:
        bind -- the address to which the server binds (default '0.0.0.0')
        port -- the port on which the server listens (default 8000)

        """
        super(RCubicServer, self).__init__(*args, **kwargs)
        self.recievedCheckIns = { }
        self.registerFunction('checkInUser', self.checkInUser)

    def checkInUser(self, env, start_reponse, post):
        """Responds to a 'checkInUser' request by calling set() on the waiting event.

        Keyword arguments:
        env -- exepects 'user' and 'checkInName' in POST.

        """
        user = post['user']
        checkInName = post['checkInName']
        # Try an 'anyuser' room check in
        vs = user.split('/')
        try:
            self.recievedCheckIns[checkInName][vs[0]].set()
        except KeyError:
            self.recievedCheckIns[checkInName][user].set()
        start_reponse(responseCodes[200], responseTypes['plaintext'])
        return 'OK'

    def registerCheckIn(self, user, checkInName, ev):
        """Internal function which records the reference to an event to wake up
        once a checkIn is recieved.

        Keyword arguments:
        user -- the user
        checkInName -- unique string identifier

        """
        if not checkInName in self.recievedCheckIns:
            self.recievedCheckIns[checkInName] = { }
        self.recievedCheckIns[checkInName][user] = ev

    def unRegisterCheckIn(self, checkInName):
        """Internal function which deletes all events waiting for 'checkInName'.
        Calls set() on all of them before returning.

        Keyword arguments:
        checkInName -- the checkIn events to delete

        """
        try:
            events = self.recievedCheckIns.pop(checkInName)
            for event in events:
                events[event].set()
            return True
        except KeyError:
            return False
