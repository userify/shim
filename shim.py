#! /usr/bin/env python

# Userify Shim
# Copyright (c) 2012-2016 Userify

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
import hashlib
import os.path
import signal
import random
import httplib
import sys
import datetime
import time
import traceback
import base64
import urllib
from pprint import pprint
import socket
import platform
import tempfile
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
ec2md = ["instance-type", "hostname", "ami-id", "mac"]
shim_version = "04012016-1"


def install_shim_runner():
    "Updates or installs the shim.sh shim runner"
    new_shim = """#! /bin/bash +e

# --------------------------------------------
#
# shim.sh
# Calls shim.py.
# """ + shim_version + """
#
# --------------------------------------------

# Copyright (c) 2016 Userify Corp.

static_host="static.userify.com"
source /opt/userify/userify_config.py
[ "x$self_signed" == "x1" ] && SELFSIGNED='k' || SELFSIGNED=''

# keep userify-shim.log from getting too big
touch /var/log/userify-shim.log
[[ $(find /var/log/userify-shim.log -type f -size +524288c 2>/dev/null) ]] && \
    mv -f /var/log/userify-shim.log /var/log/userify-shim.log.1
touch /var/log/userify-shim.log
chmod -R 600 /var/log/userify-shim.log

# kick off shim.py
[ -z "$PYTHON" ] && PYTHON="$(which python)"
curl -f${SELFSIGNED}Ss https://$static_host/shim.py | $PYTHON -u >>/var/log/userify-shim.log 2>&1

if [ $? != 0 ]; then
    # extra backoff in event of failure,
    # randomized between one and seven minutes
    sleep $(($RANDOM%360+60))
fi

sleep 5

# call myself. fork before exiting.
/opt/userify/shim.sh &
""".strip()

    # avoid disk writes when possible
    shim_runner = "/opt/userify/shim.sh"
    md1 = hashlib.md5(new_shim).digest()
    md2 = hashlib.md5(open(shim_runner).read()).digest()
    if md1 == md2:
        return
    fd, tmpname = tempfile.mkstemp()
    f = os.fdopen(fd, "wb")
    f.write(new_shim)
    f.close()
    os.chmod(tmpname, 0o700)
    # atomic overwrite only if no errors
    os.rename(tmpname, shim_runner)

# huge thanks to Purinda Gunasekara at News Corp
# for secure https_proxy code updates.

def retrieve_https_proxy():
    https_proxy = ""
    https_proxy_port = 443
    if 'https_proxy' in os.environ:
        https_proxy = os.environ['https_proxy'].strip()
        if https_proxy.startswith("http"):
            https_proxy = https_proxy.replace("https://","",1)
            https_proxy = https_proxy.replace("http://","",1)
            if ":" in https_proxy:
                https_proxy, https_proxy_port = https_proxy.split(":")
                https_proxy_port = int(''.join(c for c in https_proxy_port if c.isdigit()))
    return https_proxy, https_proxy_port

# check for self_signed for Userify Enterprise.
# (Userify Cloud will always be properly signed.)
# Python 2.7 requires ssl_security_context for self-signed.
# Configurable in userify_config.py

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
        traceback.print_exc()


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
        qexec(["/bin/mv", home_dir, removed_dir])
    else:
        qexec(["/usr/sbin/userdel", "-r", username])


def useradd(name, username, preferred_shell):
    removed_dir = "/home/deleted:" + username
    home_dir = "/home/" + username

    if dry_run:
        print "DRY RUN: Adding user ", name, username, preferred_shell
        return

    # restore removed home directory
    if not os.path.isdir(home_dir) and os.path.isdir(removed_dir):
        qexec(["/bin/mv", removed_dir, home_dir])
    if os.path.isdir(home_dir):
        useradd_suffix = ""
    else:
        useradd_suffix = "-m"
    cmd = ["/usr/sbin/useradd", useradd_suffix,
        "--comment", "userify-" + name,
        "-s", preferred_shell if preferred_shell else "/bin/bash",
        "--user-group", username]
    subprocess.call([i for i in cmd if i])
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
    try:
        subprocess.check_call(cmd)
    except Exception, e:
        print "ERROR executing %s" % " ".join(cmd)
        print e
        print "Retrying.. (shim.sh)"
    except:
        traceback.print_exc()
        print "ERROR executing %s" % " ".join(cmd)
        print "Retrying.. (shim.sh)"


def failsafe_mkdir(path):
    try: os.mkdir(path)
    except OSError: pass


def auth(id,key):
    return base64.b64encode(":".join((creds.api_id, creds.api_key)))

def instance_metadata(keys):
    # support instance metadata features
    d = {}
    try:
        h = httplib.HTTPConnection("169.254.169.254", timeout=.5)
    except:
        h = None
    try:
        if h:
            for k in keys:
                h.request("GET", "/latest/meta-data/%s" % k)
                resp = h.getresponse()
                if resp.status == 200:
                    d[k] = resp.read()
    except:
        pass
    try:
        d['machine'] = platform.machine()
        d['node'] = platform.node()
        d['platform'] = platform.platform()
        d['processor'] = platform.processor()
        d['python_build'] = platform.python_build()
        d['python_version'] = platform.python_version()
        d['release'] = platform.release()
        d['system'] = platform.system()
        d['version'] = platform.version()
        d['uname'] = platform.uname()
        d['linux_distribution'] = platform.linux_distribution(supported_dists=(
            'SuSE', 'debian', 'fedora', 'redhat', 'centos', 'mandrake', 'mandriva',
            'rocks', 'slackware', 'yellowdog', 'gentoo', 'UnitedLinux', 'turbolinux',
            'system'))
        if d['linux_distribution'] == ('', '', ''):
            d['issue'] = (open("/etc/issue").read() if
                os.path.isfile("/etc/issue") else "")
    except:
        d['metadata_status'] = 'error'
    return d

def get_ip():
    # http://stackoverflow.com/a/28950776
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # this may fail if not network access at all is available
        s.connect(('10.255.255.255', 0))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def https(method, path, data=""):

    # timeout is crucial to prevent eternal hangs, but
    # wasn't available until Python 2.5 (so shim won't
    # work on ancient versions of RHEL <= 5)

    https_proxy, https_proxy_port = retrieve_https_proxy()
    host = shim_host
    host_port = 443

    if https_proxy:
        host = https_proxy
        host_port = https_proxy_port

    # ssl_security_context required for
    # Userify Enterprise w/ self-signed certs
    # and Python 2.7

    if ssl_security_context:
        h = httplib.HTTPSConnection(
            host, host_port, timeout=30,
            context=ssl_security_context)
    else:
        h = httplib.HTTPSConnection(
            host, host_port, timeout=30)

    if https_proxy:
        # Userify always runs on 443, even Enterprise:
        h.set_tunnel(shim_host, 443)

    data = data or {}
    data.update(instance_metadata(ec2md))
    data['shim_version'] = shim_version
    data = json.dumps(data)

    headers = {
        "Accept": "text/plain, */json",
        "Authorization": "Basic " + auth(creds.api_id, creds.api_key),
        "X-Local-IP": get_ip()
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
    configuration = {"error": "Unknown error parsing configuration"}
    try:
        configuration = json.loads(text)
        if debug or failure:
            pprint(configuration)
        if failure and "error" in configuration:
            print "\n", response.reason.upper(), configuration["error"]
    except:
        failure = True
        traceback.print_exc()
    if failure or "error" in configuration:
        return 3
    process_users(configuration["users"])
    install_shim_runner()
    return configuration["shim-delay"] if "shim-delay" in configuration else 1



app = {}
if __name__ == "__main__":
    try:
        print
        print '-'*30
        print "[shim] %s start: %s" % (shim_version, time.ctime())
        s = time.time()
        try:
            time_to_wait = int(main())
        except:
            traceback.print_exc()
            time_to_wait = 300 + 60 * random.random()
        elapsed = time.time() - s
        print "[shim] elapsed: " + str(int(elapsed * 1000)/1000.0) + "s"
        if elapsed < time_to_wait:
            print "[shim] sleeping: %ss" % int(time_to_wait-elapsed)
            time.sleep(time_to_wait-elapsed)
    except:
        traceback.print_exc()
        t = 300 + 60 * random.random()
        print "[shim] sleeping: %ss" % int(t)
        time.sleep(t)
        # display error to stdout
        # and attempt restart via shim.sh
    print '-'*30
    print
