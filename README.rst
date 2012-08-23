RCUBIC
======

Introduction
------------

Rcubic is a framework for coordinating the execution of many loosely related scripts. Rcubic will manage order of execution based on dependency specification inside the script header. Scripts can be split into groups which can be executed in different combinations provided that the dependencies can be fulfilled. During execution Rcubic will validate the sequence and display progress as steps complete.

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
* *rcubic*

  - Launches the RCubic instance which reads in rcubic.xml, analyzes dependencies, and launches jobs

* *rcubic-cli*

  A tool for interacting with a running instance of rcubic. Several options are available, including:

  - *progress*

    + Sends an http message to RCubic.py with an integer (0 - 100) of percent progress with the script

  - *reschedule*

    + Sends an http message to RCubic.py with the name of the script to relaunch

  - *override*

    + Sends an http message to RCubic.py telling it to cancel a script and set its status to *MANUALOVERRIDE*. **WARNING:** Child jobs will still run.

* *rcubic-checkin*

  - Sends an http message to R2XBot and blocks, requesting for jabber users to check in. Unblocks, once the check-in has been received, or the block has timed out. Useful for ensuring developers are on hand when a release is about to be deployed.

Configuration
`````````````
In order to operate RCubic needs a set of scripts and configuration. This can be supplied in the form of a git repository, or regular directory, with the following layout:

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


rcubic.xml Layout
:::::::::::::::::
The main configuration file for rcubic specifies the basic settings such as what the working directory is, and where to get the source data.

* *basePath* must point to a writable directory, which can optionally be served by an http server. The files from the *web* directory should be put in the basePath.
* *gitRepo* can point to a git repository location, or to a directory when *FileMode* is set to *True*.
* *gerritURL* can point to the base Gerrit URL of where the repository is being cloned from. Links to the code of the scripts will be generated based on that URL, the project, and current git head hash.
* *listenAddress* is the local bind port for the communicator
* *listenPortRange* is the port range on which the communicator tries to bind.
* *baseURL* the URL on which the web directory is served
* *scriptregex* defines a regular expression scripts must match
* *SSLKey*, *SSLCert* are used to create an SSL version of the internal communicator.
* *Token* provides some additional and simple authentication and rejects requests which do not match the token.
* *resources* specify a list of resources the *ResourceScheduler* will be able to assign to scripts. User *0* for zero, and *-1* for infinity.

::

    <?xml version="1.0"?>
    <rcubic>
        <config>
            <!-- SCM settings -->
            <option name="gitRepo" value="http://git.example.com:8080/p/project"/>
            <option name="gitBranch" value="master"/>
            <option name="gerritURL" value="https://gerrit.example.com/" />
            <option name="gerritProject" value="test.git" />
            <option name="fileMode" value="False" />

            <!-- Environment settings -->
            <option name="environment" value="staging"/>
            <option name="environmentOptions" value="validate staging production"/>

            <!-- Email settings -->
            <option name="smtpServer" value="localhost"/>
            <option name="emailSubjectPrefix" value="rcubic:" />
            <option name="emailFrom" value="user@example.com" />
            <option name="maxEmailLogSizeKB" value="2" />
            <option name="notification" value="True"/>
            <!-- Carbon copy the specified email on all outbound emails
            <option name="cc" value="user@example.com"/>
            -->

            <!-- Job settings -->
            <option name="specialGroups" value="release"/>
            <option name="specialJobs" value="release_start.sh global_start.sh"/>
            <!-- When rcubic is run with -A or -a options some jobs can get
                 disconnected from the tree. When this happens we can specify
                 what their parent job will be set to.
            -->
            <option name="hijackPoint" value="release_start.sh"/>

            <!-- RESTful communication settings -->
            <option name="listenAddress" value="localhost"/>
            <option name="listenPortRange" value="31337-31347"/>
            <!-- Uncomment this to enable secure communication.
            <option name="SSLKey" value="server.key" />
            <option name="SSLCert" value="server.crt" />
            <option name="token" value="123" />
            -->

            <!-- Web Server integration settings -->
            <option name="baseURL" value="http://localhost"/>
            <option name="basePathWeb" value="rcubic" />
            <!-- HTTP ROOT -->
            <option name="basePath" value="/srv/http/"/>

            <!-- Job Validation settings -->
            <option name="defaultRelease" value="default"/>
            <!-- script must match this regular expression to be considered valid. -->
            <option name="scriptregex" value=".*"/>
            <!-- Do no let any job run for longer than this many hours -->
            <option name="jobExpireTime" value="24"/>

        </config>
        <resources>
            <!---1 for infinity, n>=0 for exact quantity-->
            <option name="default" value="-1" />
            <option name="network" value="2" />
            <option name="cpu" value="3" />
        </resources>
    </rcubic>

config.xml Layout
:::::::::::::::::
Rcubic.xml can be extended with 'revision' specific configuration which will controll which groups will be executed as part of the run. Additionall data can be stored by nesting it in the install element, the parsing of these values is left up to the scripts.

Specifying parameters in the *config* element  will overwrite any defaults specified in rcubic.xml

::

    <?xml version="1.0"?>
    <rcubic>
        <config>
            <option name="..." value="..." />
        </config>
        <release version="rc1.0">
            <install group="GROUP_DIR_1" version="rc1.0">
                <option name='foo' value='bar'>
            </install>
            <install group="GROUP_DIR_2" version="rc1.0"/>
            <install group="GROUP_DIR_3" version="rc1.0"/>
        </release>
        <notification>
            <product name="PRODUCT" email="email1@example.com"/>
            <product name="GROUP_DIR_1" email="email2@example.com"/>
        </notification>
    </rcubic>

Script Configuration
::::::::::::::::::::


Script Format
'''''''''''''
#. Shebang (*#!/bin/bash*)
#. header
#. action

Header
''''''
* **#PRODUCT:**
  describes which application is being released. Used for sending notifications.
* **#HDEP:**
  hard dependency, describes which scripts this script depends on. They hard dependency scripts must exist (at selection), else the sequence will be considered invalid.
* **#SDEP:**
  soft dependency, the script does not have to be selected. If it is selected, the order is enforced.
* **#CDEP:**
  child dependency, is just like SDEP but it specifies what scripts cannot start until this script completes.
* **#PHASE:**
  
* **#RESOURCES:**
  the resources the script is requesting before it can run. If the script requests resources that do not exist in *rcubic.xml*, they will be ignored. Otherwise the job will not run until resources are available.

Header usage recommendations
''''''''''''''''''''''''''''
* It is good practice to use the SDEP field to define dependencies on scripts outside a particular group. This will allow for the deployment of one group without the other.

* In the general case, group should not have HDEP fields pointing to scripts outside a group. If this is necessary, then perhaps it is a hint that group should be merged.

* The **#RESOURCES:** header should be used to limit the amount of concurrently running jobs that require a specific resource, if they require a large portion of that resource. The *default* header is added to every job automatically. For example, if a job has the *network* field in the header and *rcubic.xml* has a limit of 2 on that resource, only 2 such jobs will be able to run at once.

Usage
`````

Basic execution
:::::::::::::::
*RCubic.py -r REVISION_DIR -e ENVIRONMENT*

Groups
::::::
Minimal

A group is a directory of scripts. It is good practice to put all scripts which have hard dependencies with one another in the same directory. Cross-group dependencies should be soft dependencies.

Pre-execution Validation
::::::::::::::::::::::::
Before starting up the execution sequence RCubic will run the built in validation which checks for the following:

* Dependency definitions describe a connected, acyclic graph.

* All selected groups are comprised of at least one script.

* Scripts are descendant of configured entry-point script (specialJob).

* Scripts of all selected groups are executable.

* Matches the configured regular expression pattern (scriptregex).

* Script have all the required

* All defined product definitions have a accompanying contact in the release specific config.xml

Should any of these test fail RCubic will exit without ever starting the execution sequence. By passing in the *-v* flag, validation will be invoked without starting execution sequence whether or not validation passes.

In addition to these test RCubic will also draw a dependency graph which can used to visually inspect all the dependencies.


Validation can be customized by placing scripts into the validation directory. Then, when RCubic is called with *-V* or *--extval* flags all scripts will be executed. If any of the scripts exit with non-zero code, it will be counted as failure, RCubic will exit without starting the execution sequence. Validation scripts will be passed 3 arguments: Environment, Revision string, space separated list of all selected groups.

Session mode
::::::::::::
* Allows for multiple RCubic instances to run in parallel. All generated and checked-out files are put in a dated work directory to ensure separate sessions do not overlap files.

* If any script fails, the rest will be canceled automatically, so as to not block automated builds.

Foreground mode
:::::::::::::::
* By default, RCubic will run in semi-daemonized mode, where it forks off into the background and redirects stdout/stderr to a log file. Passing in the *-f* flag alters this behavior.

* With foreground mode, events and error messages are printed to the console. RCubic will not check to see whether a group has been deployed or not.

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

  - Clicking on "Log", will open a JQueryUI Dialog, which uses bash syntax highlighting to show the output log for that script

  - Clicking on "Code", when using *fileMode* will open the code in a similar way.

  - Clicking on "Code", when not using *fileMode* will open a Gerrit link to that file based on the project/branch/hash, and *gerritURL* in *rcubic.xml*

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

    + Blue: job overrides default sequence

    + Gray: job is not defined, but also not required (soft dependency)

  - Fill/Stroke:

    + Red/Red: The script has a hard dependency, but it is not defined. This will fail validation

* Edges (dependency)

  - Pale Green: Soft dependency, script does not exist. Dependency will not be fulfilled.

  - Green: Soft dependency, script exists. Dependency will be fulfilled.

  - Red: Hard dependency, script does not exist. Dependency will not be fulfilled and validation will fail.

  - Blue: Hard dependency, script exists. Dependency will be fulfilled.
