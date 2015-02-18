shim
====

The Userify shim creates users, manages sudo permissions, etc based on
the user accounts that you've configured in the Userify web console (https://console.userify.com)
or through the API. It wakes up once every 90 seconds, checks for things to do,
and goes back to sleep.

The shim is designed to be extremely lightweight and easy to integrate and
customize into cloudinit, chef recipes, puppet manifests, RPMs, DEBs,...
We're here to help. If you experience any issues, let us know.

It has zero requirements beyond what is included in every major distribution today.


System Requirements
-------------------

The Userify shim is very short (please read it for yourself)
and only requires:

*  Linux 2.6 or later
*  curl (command-line), sudo
*  Python 2.6 or later (for httplib timeout, simplejson)
*  HTTPS access to shim.userify.com (currently proxies are not supported)

These basics are *built-in* to most Linux distributions made in the last five years,
including Red Hat, Debian, Ubuntu, RHEL, CentOS, SUSE, Gentoo,
and derivatives. Need FreeBSD or other UNIX? Get in touch with specific
needs.


Tested distributions: RHEL7, CentOS7, Debian 7 (wheezy) and later,
Ubuntu 12.04 and later.  (Please notify with testing results.)


What does the installer do?
---------------------------

*   Create /opt/userify and credentials file in it (creds.py)
*   Patch /etc/rc.local (/etc/init.d/after.local on SUSE)
    with a link to the daemon
*   Creates an uninstall script at /opt/userify/uninstall.sh
*   Kicks off shim every 90 seconds


Custom Integration
------------------

Want to disable automatic updates or deploy a custom Userify shim package?
The only requirements are
shim.py and creds.py (can be derived from your Userify Project page).
Don't forget to protect creds.py:

    chmod 600 /opt/userify/creds.py
    chown root:root /opt/userify/creds.py
    
    
Using an older Linux version such as RHEL5? You can easily specify a modern Python binary (2.6 or later) by setting the PYTHON environment
variable before calling shim.sh in /etc/rc.local:

    PYTHON=/usr/bin/python2.6 /opt/userify/shim.sh &


Get In Touch
------------

We are available to assist with questions, custom installations, directory
integrations or deployments, self-hosted installations, and professional
consulting. Please open an issue with your question or contact support for
assistance.


