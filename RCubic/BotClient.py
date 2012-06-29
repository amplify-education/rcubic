from MiniREST.RESTClient import RESTClient
import gevent
from gevent import event

class BotClient(RESTClient):
    """Extends the RESTClient class to provide an interface to a BotServer

    """

    def __init__(self, server='localhost', port=8001, *args, **kwargs):
        """Create a RCubicClient to connect to a server.

        Keyword arguments:
        server -- domain to connect to (default 'localhost')
        port -- the port to connect to (default 8002)

        """
        super(BotClient, self).__init__(server, port, *args, **kwargs)

    def messageUser(self, user, message, *args, **kwargs):
        """Ask the bot to send the user a message.

        Keyword arguments:
        user -- the user to whom to send
        message -- the message to send

        """
        return self.getResponse("messageUser", data = {"user": user, "message": message, "token": self.token}, *args, **kwargs)

    def waitForEvent(self, event):
        """Internal function, which waits for the event to be set.

        Keyword arguments:
        event -- the event to wait for

        """
        event.wait()

    def requestUserCheckIn(self, users, checkInName, message, server, port, room=None, anyuser=False, timeout=3600, *args, **kwargs):
        """Asks the bot to send a request for checkin to the specified users.

        Keyword arguments:
        users -- a list of users
        checkInName -- a unique identifier string for callback
        message -- accompanying message
        server -- the server to connect to
        port -- the callback port
        room -- the room to query users in
        anyuser -- bool whether any user can confirm a check in
        timeout -- how long to wait for replies (default 3600 seconds)

        """
        events = []

        # If anyuser can check in for the given room
        if anyuser and room:
            ev = event.Event()
            self.restserver.registerCheckIn(room, checkInName, ev)
            events.append(ev)
            self.getResponse("requestRoomCheckIn", data = { "checkInName": checkInName, "message": message, "room": room, 'callbackPort': port, "token": self.token}, *args, **kwargs)
        else:
            # Go through all users and parse for pm or room
            for user in users:
                ev = event.Event()
                events.append(ev)
                if room:
                    user = room+'/'+user
                else:
                    user = user+'@'+server
                self.restserver.registerCheckIn(user, checkInName, ev)
                if not room:
                    self.getResponse("requestUserCheckIn", data = {"users": [user], "checkInName": checkInName, "message": message, "room":room, 'callbackPort' : port, token:self.token}, *args, **kwargs )
            if room:
                self.getResponse("requestUserCheckIn", data= {"users": users, "checkInName": checkInName, "message": message, "room": room , 'callbackPort': port, "token":self.token}, *args, **kwargs)
        tasks = [gevent.spawn(self.waitForEvent, eve) for eve in events]
        # Wait for all check ins or timeout
        gevent.joinall(tasks, timeout=timeout)
        # Assume everyone checked in, and see if someone didn't
        # (meaning we timed out)
        ret = True
        for eve in events:
            if not eve.isSet():
                ret = False
        # Remove pongs from waiting
        self.restserver.unRegisterCheckIn(checkInName)
        return ret
