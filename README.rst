RCUBIC
======

Introduction
------------

Rcubic is a framework for coordinating the execution of many loosely related scripts. Rcubic will manage order of execution based on dependency specification inside the script header. Scripts can be split into groups which can be executed in different combinations provided that the dependencies can be fulfiled. During execution Rcubic will validate the sequence and display progress as steps complete.

.. contents::

Use cases
---------
* Release orchestration

* Process automation


Getting Started
---------------

Installation
````````````

Prerequisites
:::::::::::::
 * python libraries:

   - gevent__

     + greenlet__

   - lxml__

   - simplejson__ (standard in python > 2.6)

   - orderedict__ (standard in python > 2.7)

   - python-requests__

   - MiniREST__

 * Applications

   - git__

   - graphviz__

__ http://www.gevent.org/
__ http://pypi.python.org/pypi/greenlet
__ http://lxml.de/
__ http://pypi.python.org/pypi/simplejson/
__ http://pypi.python.org/pypi/ordereddict
__ http://docs.python-requests.org/en/latest/index.html
__ http://github.com/minirestsomwherehere
__ http://git-scm.com/
__ http://www.graphviz.org/

How to install
::::::::::::::
#. Use *setup.py*
#. Copy the default *rcubic.xml.template* from the RCubic module directory and rename it to *rcubic.xml*. Default location is the directory of *RCubic.run*. A different path can be specified with the *--conf* option.
#. Optional: copy the *web* directory from the RCubic module directory to a directory which is served over http. Use this as your *basePath*
#. Start RCubic.run

Usage guide
-----------

Executables
````````````
* RCubic.run

  - Launches the RCubic instance which reads in rcubic.xml, analyzes dependencies, and launches jobs

* updateProgress.py

  - Sends an http message to RCubic.py with an integer (0 - 100) of percent progress with the script

* rescheduleScript.py

  - Sends an http message to RCubic.py with the name of the script to relaunch

* manualOverride.py

  - Sends an http message to RCubic.py telling it to cancel a script and set its status to *MANUALOVERRIDE*. **WARNING:** Children will still run.

* waitForCheckins.py (optional)

  - Sends an http message to R2XBot and blocks, requesting for jabber users to check in. Unblocks, once the checkin has been recieved, or the block has timed out. Usefull for ensuring developers are on hand when a release is about to be deployed.

Step configuration
``````````````````
In order to operate Rcubic needs a set of scripts and configuration. This can be supplied in the form of a git repository, or regular directory, with the following layout:

::

    RELEASE_DIR/
      config.xml
    GROUP_DIR_1/
      GROUP_DIR_2/
        GROUP_DIR_2_name.sh
        GROUP_DIR_2_name2.sh
        ...
      GROUP_DIR_3/
        GROUP_DIR_3_name.sh
        GROUP_DIR_3_name2.sh
        ...

config.xml Layout
:::::::::::::::::
Along with the aformentioned layout, RCubic will look for *GROUP_DIR_2* and *GROUP_DIR_3* inside of *GROUP_DIR_1* and parse those scripts to create the dependency tree for deployment. Specifying parameters in the *<config></config>* tags will overwrite any defaults specified in rcubic.xml

::

    <?xml version="1.0"?>
    <wgr>
        <config>
            <option name="..." value="..." />
        </config>
        <release version="rc1.0">
            <install group="GROUP_DIR_1" version="rc1.0"/>
            <install group="GROUP_DIR_2" version="rc1.0"/>
            <install group="GROUP_DIR_3" version="rc1.0"/>
        </release>
        <notification>
            <product name="PRODUCT" email="email1@example.com"/>
            <product name="GROUP_DIR_1" email="email2@example.com"/>
        </notification>
    </wgr>

rcubic.xml Layout
:::::::::::::::::
* *basePath* must point to a writable directory, which can optionaly be served by an http server. The files from the *web* directory should be put in the basePath. 
* *gitRepo* can point to a git repository location, or to a directory when *FileMode* is set to *True*. 
* *gerritURL* can point to the base gerrit url of where the repository is being cloned from. Links to the code of the scripts will be generated based on that url, the project, and current git head hash.
* *listenAddress* is the local bind port for the communicator
* *listenPortRange* is the port range on which the communicator tries to bind. 
* *baseURL* the url on which the web directory is served
* *scriptregex* defines a regex scripts must match
* *SSLKey*, *SSLCert* are used to create an SSL version of the internal communicator. 
* *Token* provides some additional and simple authentication and rejects requests which do not match the token.
* *resources* specify a list of resources the *ResourceScheduler* will be able to assign to scripts. User *0* for zero, and *-1* for infinity.

::

    <?xml version="1.0"?>
    <wgr>
        <config>
            <option name="basePath" value="/srv/http/"/>
            <option name="archivePath" value="/srv/http/archive" />
            <option name="hostListLocation" value="hostList"/>
            <option name="gitRepo" value="http://git.example.com:8080/p/project"/>
            <option name="gitBranch" value="master"/>
            <option name="gerritURL" value="https://gerrit.example.com/" />
            <option name="fileMode" value="False" />
            <option name="environmentOptions" value="validate currentQA futureQA staging production"/>
            <option name="specialGroups" value="release"/>
            <option name="smtpServer" value="localhost"/>
            <option name="emailSubjectPrefix" value="WGR:" />
            <option name="emailFrom" value="user@example.com" />
            <option name="notification" value="True"/>
            <option name="specialJobs" value="release_start.sh global_start.sh"/>
            <option name="hijackPoint" value="release_start.sh"/>
            <option name="listenAddress" value="localhost"/>
            <option name="listenPortRange" value="31337-31347"/>
            <option name="baseURL" value="http://localhost"/>
            <option name="jobExpireTime" value="24"/>
            <option name="defaultRelease" value="default"/>
            <option name="environment" value="environment"/>
            <!-- scriptregex defines things a script must match -->
            <option name="scriptregex" value="^[^#]*source\s+\.\./(helper\.sh|recipes/[^\s]*\.sh)"/>
            <option name="SSLKey" value="server.key" />
            <option name="SSLCert" value="server.crt" />
            <option name="token" value="123" />
        </config>
        <resources>
            <option name="default" value="-1" />
            <option name="network" value="2" />
            <option name="cpu" value="3" />
       </resources>
    </wgr>

Script Layout
:::::::::::::
#. Shebang (*#!/bin/bash*)
#. header
#. action script

Header
::::::
* **#PRODUCT:**
  describes which application is being released. Used for sending notifications.
* **#HDEP:**
  hard dependency, describes which scripts this script depends on. They hard dependency scripts must exist (at selection), else the sequence will be considered invalid.
* **#SDEP:**
  soft depenendency, the script does not have to be selected. If it is selected, the order is enforced.
* **#RESOURCES:**
  the resources the script is requesting before it can run. If the script requests resources that do not exist in *rcubic.xml*, they will be ignored. Otherwise the job will not run until resources are available.

Header usage recommendations
::::::::::::::::::::::::::::
* It is good practice to use the SDEP field to define dependencies on scripts outside a particular group. This will allow for the deployment of one group without the other.

* In the general case, group should not have HDEP fields pointing to scripts outside a group. If this is necessary, then perhaps it is a hint that group should be merged.

* The **#RESOURCES:** header should be used to limit the amount of concurrently running jobs that require a specific resource, if they require a large portion of that resource. The *default* header is added to every job automaically. For example, if a job has the *network* field in the header and *rcubic.xml* has a limit of 2 on that resource, only such jobs will be able to run at once.

Usage
`````

Basic execution
:::::::::::::::
*RCubic.py -r RELEASE_DIR -e ENVIRONMENT*

Validation
::::::::::
If *Rcubic.py* is run with the *-v* flag, the program will validate the script headers, output a dependency graph, and exit. This is useful for validating the dependency tree.

Groups
::::::
A group is a directory of scripts. It is good practice to put all scripts which have hard dependencies with one another in the same directory. Cross-group dependencies should be soft dependencies.

Session mode
::::::::::::
* Allows for multiple RCubic instances to run in parallel. All generated and checked-out files are put in a dated work directory to ensure seperate sessions do not overlap files.

* If any script fails, the rest will be canceled automatically, so as to not block automated builds.

Foreground mode
:::::::::::::::
* By default, RCubic will run in semi-daemonized mode, where it forks off into the background and redirects stdout/stderr to a log file.

* With foreground mode, no logging is done and everything is printed to the console. RCubic will not check to see whether a group has been deployed or not.

Web Interface
:::::::::::::
* If you do the optional step to copy the *web* directory to a directory which is served over http, and use it as your base path, you will be able to use the web interface.

* Your http tree should look like this:

::

  /srv/http/index.html
  /srv/http/js/
  /srv/http/css/
  RCubic would create a directory /srv/http/work/, which it would print out as acessible via: http://localhost/?prefix=work
  Archives would be accessible in the created /srv/http/archive/ directory with: http://localhost/?prefix=archive/UUID where UUID is the UUID in the archive directory

* The graph will refresh every 10 seconds

* Clicking on a node, will bring up a popup menu.

  - Clicking on "Log", will open a JQueryUI Dialog, which uses bash syntax hilighting to show the output log for that script

  - Clicking on "Code", when using *fileMode* will open the code in a similar way.

  - Clicking on "Code", whien not using *fileMode* will open a gerrit link to that file based on the project/branch/hash, and *gerritURL* in *rcubic.xml*

Graph Legend
::::::::::::
* Node (script)

  - Fill:

    + Yellow: script started

    + Green: scripted finished successfully

    + Red: script finished with a failure

    + Blue: script canceled

    + Pink: manual override by user

    + White: script has not yet run

    + Gray: script status is missing. Graph might have changed: refresh page.

    + Dark Orange: script blocked waiting for resource

  - Stroke:
   
    + Black: nominal

    + Blue: job overrrides default sequence

    + Gray: job is not defined, but also not required (soft dependency)

  - Fill/Stroke:

    + Red/Red: The script has a hard dependency, but it is not defined. This will fail validation

* Edges (dependency)

  - Palegreen: Soft dependency, script does not exist. Dependency will not be fulfilled.

  - Green: Soft dependency, script exists. Dependency will be fullfilled.

  - Red: Hard dependency, script does not exist. Dependency will not be fullfilled and validation will fail.

  - Blue: Hard depdendency, script exists. Dependency will be fullfilled.
