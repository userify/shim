# Userify Shim <a href=https://userify.com/><img src="https://userify.com/media/userify-logo_2016-charcoal-purple-no-tagline-no-cloud.svg" align="right"></a>
### Open Source agent for the Userify EC2 SSH Key Manager
#### Customizable deployment for enterprise datacenters and the cloud

[Tour] (https://userify.com/tour/)  ·   [Sign Up] (https://dashboard.userify.com/#action=signup)

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
*  HTTPS access (currently proxies are not supported)

These basics are *built-in* to most Linux distributions made in the last five years,
including Red Hat, Debian, Ubuntu, RHEL, CentOS, OpenSUSE, Gentoo,
and derivatives.

Tested distributions: RHEL6, RHEL7, CentOS7, Amazon Linux, Ubuntu (min 10.04LTS), Debian (min 6).
Although currently no BSD-based UNIX (incl OS X) is supported, we are looking forward to that soon.


What does the installer do?
---------------------------

*   Create /opt/userify and credentials file in it (creds.py)
*   Patch /etc/rc.local (/etc/init.d/after.local on SUSE)
    with a link to the daemon
*   Creates an uninstall script at /opt/userify/uninstall.sh
*   Kicks off shim every 90 seconds


Using older versions of Linux
-----------------------------

Using an older Linux version such as RHEL5 where the default Python 2.4 is nearly ten years old? You'll need to install
a Python 2.7 RPM (check DAG's repo) which will leave your existing Python 2.4 available for system usage.
Then set the PYTHON environment variable to your new version of Python in /etc/rc.local as follows:

    PYTHON=/usr/bin/python2.6 /opt/userify/shim.sh &

(Note: installer.sh will no longer start shim.sh automatically.)


Enterprise Support Available
----------------------------

For free integration support, please email support@userify.com.

To get signed up with a paid enterprise support package, please email enterprise@userify.com.


Get In Touch
------------

We are available to assist with questions, custom installations, directory
integrations or deployments, self-hosted installations, and professional
consulting. Please open an issue with your question or contact support for
assistance.


