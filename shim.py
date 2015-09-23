#! /usr/bin/env python

# Userify Shim
# Copyright (c) 2012-2014 Userify

# Note: the shim can be easily installed and configured via the shim installer,
# or just installed manually after creating the creds.py file.

# base level imports

try:
    import json
except:
    import simplejson as json

# Standard Library Imports
import subprocess
import os
import os.path
import signal
import httplib
import sys
import datetime
import time
import traceback
import base64
import grp
import urllib
import random
from pprint import pprint
# catch stderr
from subprocess import PIPE as pipe

sys.path.append("/opt/userify")
import creds


try:
    import userify_config as config
except:
    import creds as config


self_signed = getattr(config, "self_signed", False)
dry_run = getattr(config, "dry_run", False)
shim_host = getattr(config, "shim_host", "configure.userify.com")
debug = getattr(config, "debug", False)


# check for self_signed
ssl_security_context = None
if self_signed:
    try:
        # fails on python < 2.6:
        import ssl
        # not avail in python < 2.7:
        ssl_security_context = (hasattr(ssl, '_create_unverified_context') 
            and ssl._create_unverified_context() or None)
    except:
        print "Self signed access attempted, but unable to open self-signed"
        print "security context. This Python may not support (or need) that."
        raise


# local_download = urllib.urlretrieve

def userdel(username, permanent=False):
    # removes user and renames homedir
    removed_dir = "/home/deleted:" + username
    home_dir = "/home/" + username
    if not permanent:
        if os.path.isdir(removed_dir):
            qexec(["/bin/rm", "-Rf", removed_dir])
        # Debian:
        qexec(["/usr/bin/pkill", "--signal", "9", "-u", username])
        # RHEL:
        qexec(["/usr/bin/pkill", "-9", "-u", username])
        qexec(["/usr/sbin/userdel", username])
        qexec(["/usr/sbin/groupdel", username])
        qexec(["/bin/mv", home_dir, removed_dir])
    else:
        qexec(["/usr/sbin/userdel", "-r", username])
        qexec(["/usr/sbin/groupdel", username])


def useradd(name, username, preferred_shell):
    removed_dir = "/home/deleted:" + username
    home_dir = "/home/" + username

    if dry_run:
        print "DRY RUN: Adding user ", name, username, preferred_shell
        return

    # restore removed home directory
    cmd = ["/usr/sbin/useradd"]
    if not os.path.isdir(home_dir) and os.path.isdir(removed_dir):
        qexec(["/bin/mv", removed_dir, home_dir])
    if not os.path.isdir(home_dir):
        cmd.append(useradd_suffix = "-m")

    cmd.append("-s")
    if preferred_shell:
        cmd.append(preferred_shell)
    else:
        cmd.append("/bin/bash")
    try:
        group_entity = grp.getgrnam(username)
        cmd.append("--gid")
        cmd.append(str(group_entity[2]))
    except KeyError:
        cmd.append("--user-group")
    cmd.append(username)
    qexec(cmd)
    fullchown(username, home_dir)
    parse_passwd()


def sudoers_add(username, perm=""):
    fname = "/etc/sudoers.d/" + username
    text = sudoerstext(username, perm)

    if dry_run:
        print "DRY RUN: Adding sudoers: ", fname, text
        return

    if perm:
        if not os.path.isfile(fname) or open(fname).read() != text:
            open(fname, "w").write(text)
            fullchmod("0440", fname)
    else:
        sudoers_del(username)


def sudoers_del(username):
    fname = "/etc/sudoers.d/" + username
    if os.path.isfile(fname):
        qexec(["/bin/rm", fname])


def sudoerstext(username, perm):
    return "\n".join((
        "# Generated by userify",
        username + " "*10 + perm, ""))


def sshkeytext(ssh_public_key):
    return "\n".join((
        "# Generated by userify",
        "# Paste your new key at console.userify.com.", ssh_public_key, ""))


def sshkey_add(username, ssh_public_key=""):

    if not ssh_public_key:
        return

    userpath = "/home/" + username
    sshpath = userpath + "/.ssh/"

    if dry_run:
        print "DRY RUN: Adding user ssh key", sshpath, ssh_public_key
        return

    failsafe_mkdir(sshpath)
    fname = sshpath + "authorized_keys"
    text = sshkeytext(ssh_public_key)
    if not os.path.isfile(fname) or open(fname).read() != text:
        open(fname, "w").write(text)
        fullchown(username, sshpath)


def fullchown(username, path):
    qexec(["chown", "-R", username+":"+username, path])


def fullchmod(mode, path):
    qexec(["chmod", "-R", mode, path])


def qexec(cmd):
    print "[shim] exec: \"" + " ".join(cmd) + '"'
    try: subprocess.check_call(cmd)
         # ,stderr=pipe, stdout=pipe)
    except:
        traceback.print_exc()
        pass


def failsafe_mkdir(path):
    try: os.mkdir(path)
    except OSError: pass


def auth(id,key):
    return base64.b64encode(":".join((creds.api_id, creds.api_key)))


def https(method, path, data=""):

    # timeout is crucial to prevent eternal hangs, but
    # wasn't available until Python 2.5 (so shim won't
    # work on ancient versions of RHEL <= 5)

    if ssl_security_context:
        h = httplib.HTTPSConnection(shim_host, timeout=30,
                context=ssl_security_context)
    else:
        h = httplib.HTTPSConnection(shim_host, timeout=30)

    headers = {
        "Accept": "text/plain, */json",
        "Authorization": "Basic " + auth(creds.api_id, creds.api_key)
    }
    h.request(method, path, data, headers)
    return h


def parse_passwd():
    # returns a list of passwd lines, ordered as
    # username, unused, uid, gid, comment, homedir, shell
    app["passwd"] = [[i.strip() for i in l.split(":")]
        for l in open("/etc/passwd").read().strip().split("\n")]
    app["passwd"] = [i if len(i)>6 else i.append("") for i in app["passwd"]]


def current_usernames():
    return [user[0] for user in app["passwd"]]


def current_userify_users():
    "get only usernames created by userify"
    return [user for user in app["passwd"] if user[4].startswith("userify-")]


def remove_user(username, permanent=False):
    # completely removes user
    if dry_run:
        print "DRY RUN: Removing user: ", username, "permanently:", permanent
        return
    try: userdel(username, permanent)
    except: pass
    try: sudoers_del(username)
    except: pass


def process_users(good_users):
    for username, user in good_users.iteritems():
        if username not in current_usernames():
            useradd(user["name"], username, user["preferred_shell"])
        if "ssh_public_key" in user:
            sshkey_add(username, user["ssh_public_key"])
        sudoers_add(username, user["perm"])
    for userrow in current_userify_users():
        username = userrow[0]
        if username not in good_users.keys():
            print "[shim] removing" + username
            remove_user(username)


def main():
    parse_passwd()
    h = https("POST", "/api/userify/configure")
    response = h.getresponse()
    text = response.read()
    failure = response.status != 200
    if debug or failure:
        print response.status, response.reason
        pprint(text)
    try:
        configuration = json.loads(text)
        if debug or failure:
            pprint(configuration)
        if failure and "error" in configuration:
            print "\n", response.reason.upper(), configuration["error"]
    except:
        failure = True
    if "error" in configuration or failure:
        return 3
    process_users(configuration["users"])
    return configuration["shim-delay"] if "shim-delay" in configuration else 1



app = {}
if __name__ == "__main__":
    try:
        print
        print '-'*30
        print "[shim] start: %s" % time.ctime()
        s = time.time()
        time_to_wait = main()
        elapsed = time.time() - s
        print "[shim] elapsed: " + str(int(elapsed * 1000)/1000.0) + "s"
        if elapsed < time_to_wait:
            print "[shim] sleeping: %s" % (time_to_wait-elapsed)
            time.sleep(time_to_wait-elapsed)
    except:
        time.sleep(3)
        # display error to stdout
        # and attempt restart via shim.sh
        raise
    print '-'*30
    print
