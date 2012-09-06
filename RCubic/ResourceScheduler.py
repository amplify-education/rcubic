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


import gevent
import gevent.coros
import gevent.event
import gevent.greenlet

class ResourceScheduler(object):
    """Assigns a collection of resources

    """

    def __init__(self, resources):
        """Create a new Resourse scheduler (non-blocking).

        Keyword argument:
        resources -- a dictionary of resource (string) to quantity (int)

        """
        self.resources = resources
        # Create the set of available resources
        self.available = set([])
        self.allresources = set([])
        for x in self.resources.keys():
            self.allresources.add(x)
            if self.resources[x] > 0:
                self.available.add(x)
        self.requests = [ ]
        self.event = gevent.coros.Semaphore(value=0)
        self.lock = gevent.coros.RLock()
        self.r = gevent.greenlet.Greenlet(self._reschedule)
        self.r.start()

    def _reschedule(self):
        """The scheduler loop.
        Waits for a semaphore to be incremented when a resource is released

        """
        while True:
            # Wait for a release event
            self.event.acquire()
            # Synchronized
            self.lock.acquire()
            # Go through all requests
            self.requests[:] = [x for x in self.requests if not self._allocate(x)]
            # Release synchronized
            self.lock.release()

    def _allocate(self, request):
        """Allocates resources. Returns True for success and False for failure.
        Uses set intersections to easily check for availability.

        Keyword arguments:
        request -- set of resources to be requested

        """
        # Intersect against all types to filter out ones we can limit
        if(len(request['resources'].intersection(self.available)) == len(request['resources'].intersection(self.allresources))):
            # Decrement counters
            for r in request['resources']:
                try:
                    self.resources[r] = self.resources[r] - 1
                    # Remove from available if no more
                    if self.resources[r] == 0:
                        self.available.remove(r)
                except KeyError:
                    pass
            # Free request
            request['event'].set()
            return True
        else:
            return False

    def request(self, resources):
        """Request resources. Blocks until resources available.

        Keyword arguments:
        resources -- the requested resources (a list of strings)

        """
        # Synchronize
        self.lock.acquire()
        # Create event
        e = gevent.event.Event()
        req = {'resources': set(resources), 'event': e}
        # Try scheduling it now
        if(not self._allocate(req)):
            # If we can't then add it to the general list
            self.requests.append(req)
        self.lock.release()
        e.wait()
        
    def release(self, resources):
        """Release resources. Temporarily blocking.

        Keyword arguments:
        resources -- the resources to free (a list of strings)

        """
        self.lock.acquire()
        for r in resources:
            try:
                self.resources[r] = self.resources[r] + 1
                if self.resources[r] == 1:
                    self.available.add(r)
            except KeyError:
                pass
        self.lock.release()
        # Signal scheduler
        self.event.release()
