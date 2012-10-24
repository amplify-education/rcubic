#!/usr/bin/python
# vim: ts=4 et filetype=python



from distutils.core import setup
setup(name = 'exectree',
      version = '1.0',
      description = 'ExecTree is a library for organizing execution of many scripts in a tree like dependency hierarchy',
      # Required packages
      requires = [ 'pydot', 'gevent', 'lxml'],
      # List what we provide and obolete for updates
      provides = ['exectree'],
      obsoletes = ['exectree'],
      # Seperate modules
      # Main packages
      packages = ['exectree'],
      )
