#!/usr/bin/env python
from RCubic.RCubicClient import RCubicClient

import sys
import argparse

parser = argparse.ArgumentParser(description='Ask RCubic if it supports a feature')

parser.add_argument('--port', dest='port', default=8002, help='Port on which RCubic is listening', type=int)
parser.add_argument('--addr', dest='addr', default='localhost', help='Address on which RCubic is listening')
parser.add_argument('--cacert', dest='cacert', default=None, help='CACert to auth server', type=str)
parser.add_argument('--token', dest='token', default='', help='used to auth with bot server', type=str)
parser.add_argument('--feature', dest='feature', required=True, help='Name of to ask if supported', type=str)

args = parser.parse_args()

client = RCubicClient(server=args.addr, port=args.port, CACert=args.cacert, token=args.token)
if client.supported(args.feature) == "True":
    sys.exit(0)
else:
    sys.exit(1)
