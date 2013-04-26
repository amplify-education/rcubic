#!/usr/bin/python

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


from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

setup(name = 'RCubic',
      version = '1.2',
      description = 'RCubic',
      # Required packages
      requires = ['MiniREST', 'lxml', 'simplejson', 'pydot', 'gevent'],
      # List what we provide and obolete for updates
      provides = ['RCubic'],
      obsoletes = ['RCubic'],
      # Main packages
      packages = ['RCubic'],
      # Command line scripts
      scripts = [
          'bin/rcubic', 'bin/rcubic-cli', 'bin/rcubic-checkin', 'bin/rcubic-migratedb'
          ],
      # Config files
      data_files = [
          ('RCubic/', ["RCubic/rcubic.xml.template"]),
          ('RCubic/web/', ["RCubic/web/index.html"]),
          ('RCubic/web/archive/', ["RCubic/web/archive/index.html"]),
          ('RCubic/web/', [
              "RCubic/web/index.html",
              "RCubic/web/archive.html"
              ]),
          ('RCubic/web/css/', [
            "RCubic/web/css/jquery.qtip.min.css",
            "RCubic/web/css/select2.css",
            "RCubic/web/css/select2.png",
            "RCubic/web/css/select2x2.png",
            "RCubic/web/css/spinner.gif"]),
          ('RCubic/web/css/syntax/', [
            "RCubic/web/css/syntax/shCore.css",
            "RCubic/web/css/syntax/shCoreFadeToGrey.css"]),
          ('RCubic/web/js/', [
            "RCubic/web/js/select2.js",
            "RCubic/web/js/jquery.min.js",
            "RCubic/web/js/jquery.ui.min.js",
            "RCubic/web/js/jquery.qtip.min.js"]),
          ('RCubic/web/js/syntax/', [
            "RCubic/web/js/syntax/shCore.js",
            "RCubic/web/js/syntax/shBrushBash.js"]),
          ('RCubic/web/css/vader/', [
            "RCubic/web/css/vader/jquery-ui-1.8.21.custom.css"]),
          ('RCubic/web/css/vader/images/', [
            "RCubic/web/css/vader/images/ui-bg_glass_95_fef1ec_1x400.png",
            "RCubic/web/css/vader/images/ui-icons_aaaaaa_256x240.png",
            "RCubic/web/css/vader/images/ui-icons_cccccc_256x240.png",
            "RCubic/web/css/vader/images/ui-icons_bbbbbb_256x240.png",
            "RCubic/web/css/vader/images/ui-bg_flat_0_aaaaaa_40x100.png",
            "RCubic/web/css/vader/images/ui-bg_inset-soft_15_121212_1x100.png",
            "RCubic/web/css/vader/images/ui-bg_highlight-hard_15_888888_1x100.png",
            "RCubic/web/css/vader/images/ui-icons_c98000_256x240.png",
            "RCubic/web/css/vader/images/ui-icons_666666_256x240.png",
            "RCubic/web/css/vader/images/ui-icons_f29a00_256x240.png",
            "RCubic/web/css/vader/images/ui-bg_highlight-soft_35_adadad_1x100.png",
            "RCubic/web/css/vader/images/ui-bg_highlight-soft_60_dddddd_1x100.png",
            "RCubic/web/css/vader/images/ui-icons_cd0a0a_256x240.png",
            "RCubic/web/css/vader/images/ui-bg_gloss-wave_16_121212_500x100.png",
            "RCubic/web/css/vader/images/ui-bg_highlight-hard_55_555555_1x100.png"]),
        ]
    )
