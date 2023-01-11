# Userify Shim <a href=https://userify.com/><img src="https://userify.com/media/userify-logo_2016-charcoal-purple-no-tagline-no-cloud.svg" align="right"></a>
### Userify SSH Key Manager

The Userify shim creates users, manages sudo permissions, etc based on
the user accounts that you've configured in the Userify web console
or through the API. It wakes up once every ten seconds or so,
checks for things to do, and goes back to sleep.

The shim is designed to be lightweight and easy to integrate and
customize into Terraform, Ansible, Cloud Formation, Chef, Puppet, etc via
the Userify dashboard, which automates the installation for you.

The Userify shim is designed to have minimal working requirements (curl,
any version of Python since 2009, the Linux adduser command, and sudo.)
These basics are built-in to most Linux distributions
including Red Hat, Debian, Ubuntu, RHEL, CentOS, SLES, Gentoo, etc.

What does the installer do?
---------------------------

*   Create /opt/userify and credentials file in it (creds.py)
*   Creates an uninstall script at /opt/userify/uninstall.sh
*   Kicks off shim between every 10 and 180 seconds (set by the server)
*   Sets the shim to automatically start on boot
*   The shim itself (the python script) automatically syncs user accounts.

Support
-------

For free, fast, and friendly support, please email support@userify.com.


Get In Touch
------------

We are available to assist with questions, custom installations, directory
integrations or deployments, and self-hosted installations.
Please contact support for assistance or open an issue in this repository.
