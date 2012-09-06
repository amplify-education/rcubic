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


from RCubic.ResourceScheduler import ResourceScheduler
from random import randint
import gevent


def single_waiter(scheduler, i, sleep=3):
    print("%3d waiting..." % i)
    scheduler.request(["meow"])
    print("%3d running..." % i)
    gevent.sleep(randint(0,sleep))
    scheduler.release(["meow"])
    print("%3d done..." % i)

def multi_waiter(scheduler, i, sleep=3):
    r = randint(1,3)
    req = []
    if r == 1:
        req = ["woof", "meow"]
    elif r == 2:
        req = ["meow", "hiss"]
    elif r == 3:
        req = ["woof", "hiss",]
    #print("%3d waiting for: %s..." % (i, req))
    scheduler.request(req)
    #print("%3d running..." % i)
    gevent.sleep(randint(0, sleep))
    scheduler.release(req)
    #print("%3d done..." % i)



def test_inf_one():
    resources = { "meow": float("inf") }
    scheduler = ResourceScheduler(resources)
    threads = [ gevent.spawn(single_waiter, scheduler, i) for i in xrange(5) ]
    gevent.joinall(threads)
    assert scheduler.resources["meow"] == float("inf")

def test_limited_one():
    resources = { "meow": 2 }
    scheduler = ResourceScheduler(resources)
    threads = [ gevent.spawn(single_waiter, scheduler, i) for i in xrange(4) ]
    gevent.joinall(threads)
    assert scheduler.resources["meow"] == 2

def test_limited_multi():
    resources = { "meow": 2, "woof": 5 }
    scheduler = ResourceScheduler(resources)
    threads = [ gevent.spawn(multi_waiter, scheduler, i) for i in xrange(10) ]
    gevent.joinall(threads)
    assert scheduler.resources["meow"] == 2
    assert scheduler.resources["woof"] == 5

def test_massive_limited_multi():
    resources = { "meow": 20, "woof": 20 , "hiss": 20, "rawr": 20}
    scheduler = ResourceScheduler(resources)
    threads = [ gevent.spawn(multi_waiter, scheduler, i,0) for i in xrange(1000) ]
    gevent.joinall(threads)
    assert scheduler.resources["meow"] == 20
    assert scheduler.resources["woof"] == 20
    assert scheduler.resources["hiss"] == 20
    assert scheduler.resources["rawr"] == 20
