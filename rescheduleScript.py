#!/usr/bin/env python
from RCubic.RCubicClient import RCubicClient

import sys
import argparse
from requests.exceptions import SSLError

parser = argparse.ArgumentParser(description='Update RCubic with current progress')

parser.add_argument('--port', dest='port', default=8002, help='Port on which RCubic is listening', type=int)
parser.add_argument('--addr', dest='addr', default='localhost', help='Address on which RCubic is listening')
parser.add_argument('--cacert', dest='cacert', default=None, help='CACert to auth server', type=str)
parser.add_argument('--token', dest='token', default='', help='used to auth with bot server', type=str)
parser.add_argument('--script', dest='script', required=True, help='Name of script to update', type=str)

args = parser.parse_args()

client = RCubicClient(server=args.addr, port=args.port, CACert=args.cacert, token=args.token)
resp = ''
try:
	resp = client.reschedule(args.script)
except SSLError as e:
	print("SSL negotiation error: {0}".format(e))
	sys.exit(1)
sys.exit(0)
