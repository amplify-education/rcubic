#!/usr/bin/env python
from RCubic.RCubicClient import RCubicClient

import sys
import argparse

parser = argparse.ArgumentParser(description='Update RCubic with current progress')

parser.add_argument('--port', dest='port', default=8002, help='Port on which RCubic is listening', type=int)
parser.add_argument('--addr', dest='addr', default='localhost', help='Address on which RCubic is listening')
parser.add_argument('--cacert', dest='cacert', default=None, help='CACert to auth server', type=str)
parser.add_argument('--token', dest='token', default='', help='used to auth with bot server', type=str)
parser.add_argument('--script', dest='script', required=True, help='Name of script to update', type=str)
parser.add_argument('--version', dest='version', default=None, help='Script version', type=str)
parser.add_argument('--progress', dest='progress', required=True, help='Progress value (0-100)', type=int)

args = parser.parse_args()

client = RCubicClient(server=args.addr, port=args.port, CACert=args.cacert, token=args.token)
if client.progress(args.script, args.version, args.progress) == "True":
    sys.exit(0)
else:
    sys.exit(1)
