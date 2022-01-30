#! /usr/bin/env python

# Userify Shim
# Copyright (c) 2015-2022 Userify Corporation
# for Python 2 or 3

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
try:
    import http.client as httplib
except:
    import httplib
import sys
import datetime
import time
import traceback
import base64
# import urllib
from pprint import pprint
import socket
import platform
import tempfile
# catch stderr
from subprocess import PIPE as pipe

try:
    from builtins import bytes
except:
    def bytes(s): return s

# Python 2.7 polyfill to re-add sslwrap to Python 2.7.9
# thanks to https://github.com/gevent/gevent/issues/477

try:

    import inspect
    __ssl__ = __import__('ssl')

    try:
        _ssl = __ssl__._ssl
    except AttributeError:
        _ssl = __ssl__._ssl2


    def new_sslwrap(sock, server_side=False, keyfile=None, certfile=None, cert_reqs=__ssl__.CERT_NONE, ssl_version=__ssl__.PROTOCOL_SSLv23, ca_certs=None, ciphers=None):
        context = __ssl__.SSLContext(ssl_version)
        context.verify_mode = cert_reqs or __ssl__.CERT_NONE
        if ca_certs:
            context.load_verify_locations(ca_certs)
        if certfile:
            context.load_cert_chain(certfile, keyfile)
        if ciphers:
            context.set_ciphers(ciphers)

        caller_self = inspect.currentframe().f_back.f_locals['self']
        return context._wrap_socket(sock, server_side=server_side, ssl_sock=caller_self)

    if not hasattr(_ssl, 'sslwrap'):
        _ssl.sslwrap = new_sslwrap

except Exception as e:
    print("Unable to load SSL polyfill: %s" % e)
    traceback.print_exc()
line_spacer = "\n" + "*" * 30

socket.setdefaulttimeout(5)
sys.path.append("/opt/userify")
import creds

try:
    import userify_config as config
except:
    import creds as config

creds.api_id = bytes(creds.api_id.encode("utf-8"))
creds.api_key = bytes(creds.api_key.encode("utf-8"))

self_signed = getattr(config, "self_signed", False)
dry_run = getattr(config, "dry_run", False)
shim_host = getattr(config, "shim_host", "configure.userify.com")
debug = getattr(config, "debug", False)
ec2md = ["instance-type", "hostname", "ami-id", "mac"]
shim_version = "20220130-1"

# begin long-running shim processing
server_rsa_public_key = ""
f = "/etc/ssh/ssh_host_rsa_key.pub"
try:
    server_rsa_public_key = open(f).read()
except Exception as e:
    print(("Unable to read %s: %s" % (f,e)))


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

# Copyright (c) 2015-2022 Userify Corp.

# wrap in an anonymous function
{

static_host="static.userify.com"
touch /opt/userify/userify_config.py
source /opt/userify/userify_config.py
[ "x$self_signed" == "x1" ] && SELFSIGNED='k' || SELFSIGNED=''

# keep userify-shim.log from getting too big
touch /var/log/userify-shim.log
[[ $(find /var/log/userify-shim.log -type f -size +524288c 2>/dev/null) ]] && \
    mv -f /var/log/userify-shim.log /var/log/userify-shim.log.1
touch /var/log/userify-shim.log
chmod -R 600 /var/log/userify-shim.log

# kick off shim.py
[ -z "$PYTHON" ] && PYTHON="$(command -v python3)"
[ -z "$PYTHON" ] && PYTHON="$(command -v python)"
curl --compressed -1 -f${SELFSIGNED}Ss https://$static_host/shim/shim.py | $PYTHON -u \
    2>&1 >>/var/log/userify-shim.log

if [ $? != 0 ]; then
    # extra backoff in event of failure,
    # randomized between one and seven minutes
    sleep $(($RANDOM%360+60))
fi

sleep 5

# call myself. fork before exiting.
/opt/userify/shim.sh &

# send output to log file.
} >> /var/log/userify-shim.log 2>&1
""".strip()

    try:
        # avoid disk writes when possible
        shim_runner = "/opt/userify/shim.sh"
        md1 = hashlib.md5(new_shim.encode("utf-8")).digest()
        md2 = hashlib.md5(open(shim_runner).read().encode("utf-8")).digest()
        if md1 == md2:
            return
        fd, tmpname = tempfile.mkstemp(dir="/opt/userify/")
        f = os.fdopen(fd, "wb")
        f.write(bytes(new_shim.encode("utf-8")))
        f.close()
        os.chmod(tmpname, 0o700)
        # atomic overwrite only if no errors
        os.rename(tmpname, shim_runner)
    except Exception as e:
        print(("Unable to update shim.sh: %s" % e))
        raise

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
        print(("Self signed access attempted, but unable to open self-signed" +
               " security context. This Python may not support (or need) that."))
        traceback.print_exc()


# local_download = urllib.urlretrieve

def userdel(username, permanent=False):
    # removes user and renames homedir
    removed_dir = "/home/deleted:" + username
    home_dir = "/home/" + username
    if not permanent:
        if os.path.isdir(removed_dir):
            qexec(["/bin/rm", "-Rf", removed_dir])
        # try multiple pkill formats until one works
        # Debian, Ubuntu:
        qexec(["/usr/bin/pkill", "--signal", "9", "-u", username])
        # RHEL, CentOS, and Amazon Linux:
        qexec(["/usr/bin/pkill", "-9", "-u", username])
        qexec(["/usr/sbin/userdel", username])
        qexec(["/bin/mv", home_dir, removed_dir])
    else:
        qexec(["/usr/sbin/userdel", "-r", username])
    parse_passwd()


def useradd(name, username, preferred_shell):
    removed_dir = "/home/deleted:" + username
    home_dir = "/home/" + username

    if dry_run:
        print(("DRY RUN: Adding user %s %s %s " % (name, username, preferred_shell)))
        return
    
    # figure out if preferred shell is available and fallback otherwise
    bins = os.listdir("/bin/")
    # this technically eliminates /sbin/nologin as an option, but in most distros it's available in /bin
    pshell = preferred_shell.replace("/bin/","").replace("/sbin/","")
    if pshell in ["nologin", "false", "true"]:
        # if this is a nologin shell, default to /bin/false if preferred shell not available.
        sh = [shell for shell in [pshell, "nologin", "false", "true"] if shell in bins]
        if sh:
            sh = sh[0]
        else:
            sh = "false"
    else:
        # if this is a regular login shell, default to /bin/bash if preferred shell not available.
        sh = [shell for shell in [pshell,"bash","sh","zsh","ksh","csh"] if shell in bins]
        if sh:
            sh = sh[0]
        else:
            sh = "sh"
    shell = "/bin/" + sh
    
    # restore removed home directory
    if not os.path.isdir(home_dir) and os.path.isdir(removed_dir):
        qexec(["/bin/mv", removed_dir, home_dir])
    if os.path.isdir(home_dir):
        useradd_suffix = ""
    else:
        useradd_suffix = "-m"
    cmd = ["/usr/sbin/useradd", useradd_suffix,
        # UsePAM no should be in /etc/ssh/sshd_config
        "--comment", "userify-" + name,
        "-s", shell,
        "--user-group", username]
    subprocess.call([i for i in cmd if i])
    fullchown(username, home_dir)
    parse_passwd()

def sanitize_sudoers_filename(username):
    return ( "/etc/sudoers.d/" + username.replace(
            ",", "-").replace(
            ".", "-").replace(
            "@", "-"))

def sudoers_add(username, perm=""):
    old_fname = "/etc/sudoers.d/" + username
    fname = sanitize_sudoers_filename(username)
    if old_fname != fname and os.path.isfile(old_fname):
        # clean up old sudoers files
        qexec(["/bin/rm", old_fname])
    text = "\n".join(("# Generated by Userify: %s" % time.ctime(),
        username + " "*10 + perm, ""))
    if dry_run:
        print(("DRY RUN: Adding sudoers: %s %s" % (fname, text)))
        return
    if not os.path.isfile(fname):
        # or open(fname).read() != text:
        open(fname, "w").write(text)
        fullchmod("0440", fname)

def sudoers_del(username):
    fname = sanitize_sudoers_filename(username)
    if dry_run:
        print(("DRY RUN: Deleting sudoers: %s" % fname))
        return
    if os.path.isfile(fname):
        qexec(["/bin/rm", fname])

def sshkeytext(ssh_public_key):
    return "\n".join((
        "# Generated by userify",
        ssh_public_key, ""))


def sshkey_add(username, ssh_public_key, pubkeyfn):

    if not ssh_public_key:
        return

    userpath = "/home/" + username
    sshpath = userpath + "/.ssh/"

    if dry_run:
        print(("DRY RUN: Adding user ssh key %s %s" % (sshpath, ssh_public_key)))
        return

    failsafe_mkdir(sshpath)
    fname = sshpath + pubkeyfn
    text = sshkeytext(ssh_public_key)
    if not os.path.isfile(fname) or open(fname).read() != text:
        open(fname, "w").write(text)
        fullchown(username, sshpath)


def ssh_privatekey_add(username, ssh_private_keys):
    for privname, privkey, pubkey in ssh_private_keys:
        userpath = "/home/" + username
        sshpath = userpath + "/.ssh/"
        if dry_run:
            print(("DRY RUN: Adding user private ssh key %s %s %s" % (sshpath, privname, privkey)))
            return
        failsafe_mkdir(sshpath)
        fname = sshpath + privname
        text = sshkeytext(privkey)
        if not os.path.isfile(fname) or open(fname).read() != text:
            open(fname, "w").write(text)
            fullchown(username, sshpath)
            fullchmod("0600", fname)
        sshkey_add(username, pubkey, privname + ".pub")


def fullchown(username, path):
    qexec(["chown", "-R", username+":"+username, path])


def fullchmod(mode, path):
    qexec(["chmod", "-R", mode, path])

def fullchmod(mode, path):
    qexec(["chmod", "-R", mode, path])


def qexec(cmd, quiet=False):
    if not quiet:
        print(("[shim] exec: \"" + " ".join(cmd) + '"'))
    try:
        return subprocess.check_call(cmd)
    except Exception as e:
        if not quiet:
            print(("ERROR executing %s" % " ".join(cmd)))
            print (e)
            print ("Retrying.. (shim.sh)")


def failsafe_mkdir(path):
    try: os.makedirs(path)
    except OSError as e:
        if e.errno != 17:
            raise


def auth():
    return b"Basic " + base64.b64encode(b":".join((creds.api_id, creds.api_key)))

def instance_metadata(keys):
    # support instance metadata features
    d = {}
    d['server_rsa_public_key'] = server_rsa_public_key
    try:
        h = httplib.HTTPConnection("169.254.169.254", timeout=.5)
        if h:
            for k in keys:
                try:
                    h.request("GET", "/latest/meta-data/%s" % k)
                    resp = h.getresponse()
                    if resp.status == 200:
                        d[k] = bytes(resp.read().encode("utf-8"))
                except:
                    pass
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
        d['linux_distribution'] = platform.linux_distribution(
            supported_dists=(
                'SuSE', 'debian', 'fedora', 'redhat', 'centos', 'mandrake',
                'mandriva', 'rocks', 'slackware', 'yellowdog', 'gentoo',
                'UnitedLinux', 'turbolinux', 'system'))
        try:
            if d['linux_distribution'] == ('', '', ''):
                d['issue'] = (open("/etc/issue").read()[:80] if
                    os.path.isfile("/etc/issue") else "")
        except:
            pass
    except:
        d['metadata_status'] = 'error'
    # identify loose keys (keyscan)
    d['loose_keys'] = []
    looseusers = {}
    for username, homedir in [(user[0], user[5]) for user in app["passwd"]]:
        sshdir = homedir + "/.ssh/"
        if os.path.isdir(sshdir):
            for fname in os.listdir(sshdir):
                # This will catch a new Userify username's key the first cycle, but not subsequent
                # cycles, because this function runs before we have the latest username list from Userify.
                # Once the new user is created, that new user will show up in current_userify_users and
                # be ignored.
                if fname not in ("deleted:authorized_keys", "known_hosts", "config") and not fname.endswith(".pub"):
                    if fname in ("authorized_keys", "authorized_keys2") and username in current_userify_users(True):
                        continue
                    if username not in looseusers: looseusers[username] = []
                    looseusers[username].append(sshdir+fname)
    for username,files in looseusers.items():
        # This format is subject to change in subsequent releases.
        d['loose_keys'].append(username+"\n"+("\n".join(files)))
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
            host, host_port, timeout=15,
            context=ssl_security_context)
    else:
        h = httplib.HTTPSConnection(
            host, host_port, timeout=15)

    if https_proxy:
        # Userify always runs on 443, even Enterprise:
        h.set_tunnel(shim_host, 443)


    headers = {
        "Accept": "text/plain, */json",
        "Authorization": auth(),
        "X-Local-IP": get_ip(),
        # removed as doesn't work on python 3:
        # "Accept-Encoding": "gzip, deflate"
    }

    data = data or {}
    data.update(instance_metadata(ec2md))
    data["hostname"] = str(socket.gethostname()) or headers["X-Local-IP"]

    # pprint(data)
    data['shim_version'] = shim_version
    data = json.dumps(data)

    try:
        h.request(method, path, data, headers)
    except Exception as e:
        print (line_spacer)
        print(("Error: %s" % e))
        # traceback.print_exc()
        print (line_spacer)
        t = 300 + 60 * random.random()
        print(("[shim] sleeping: %ss" % int(t)))
        time.sleep(t)
        # display error to stdout
        # and attempt restart via shim.sh

    return h


def parse_passwd():
    # returns a list of passwd lines, ordered as
    # username, unused, uid, gid, comment, homedir, shell
    app["passwd"] = [[i.strip() for i in l.split(":")]
        for l in open("/etc/passwd").read().strip().split("\n")]
    app["passwd"] = [i if len(i)>6 else i.append("") for i in app["passwd"] if len(i)>4]


def system_usernames():
    "returns all usernames in /etc/passwd"
    return [user[0] for user in app["passwd"]]


def current_userify_users(usernames_only=False):
    "get only usernames created by userify"
    return [
        user[0] if usernames_only else user
            for user in app["passwd"] if user[4].startswith("userify-")]


def remove_user(username, permanent=False):
    # completely removes user
    if dry_run:
        print(("DRY RUN: Removing user: %s permanently: %s"% (username, permanent)))
        return
    try: userdel(username, permanent)
    except: pass
    try: sudoers_del(username)
    except: pass


def process_users(defined_users):

    for username, user in defined_users.items():

        # if the user already exists on the system and we didn't create it, skip.
        if username in system_usernames() and username not in current_userify_users(usernames_only=True):
            print(("ERROR: Ignoring username %s which conflicts with an " % username +
                "existing non-Userify user on this system!\n" +
                "To allow the shim to take over this user account, please run:\n" +
                'sudo usermod -c "userify-%s" %s' % (username, username)))
            continue

        # if the username doesn't exist, create it:
        if username not in system_usernames():
            try:
                useradd(user["name"], username, user["preferred_shell"])
            except Exception as e:
                print(("Unable to add user %s: %s" % (username, e)))

        # user now exists; set SSH public key
        if "ssh_public_key" in user:
            try:
                sshkey_add(username, user["ssh_public_key"], "authorized_keys")
            except Exception as e:
                print(("Unable to add SSH key for user %s: %s" % (username, e)))

        # also set SSH private key if provided.
        if "ssh_private_keys" in user and user["ssh_private_keys"]:
            try:
                ssh_privatekey_add(username, user["ssh_private_keys"])
            except Exception as e:
                print(("Unable to add SSH private key for user %s: %s" % (username, e)))

        # set up sudoers as well:
        if "perm" in user and user["perm"]:
            try:
                sudoers_add(username, user["perm"])
            except Exception as e:
                print(("Unable to configure sudo for user %s: %s" % (username, e)))
        else:
            sudoers_del(username)

    for userrow in current_userify_users():
        username = userrow[0]
        if username not in list(defined_users.keys()):
            print(("[shim] removing " + username))
            try:
                remove_user(username)
            except Exception as e:
                print(("Unable to remove user %s: %s" % (username, e)))


def main():
    parse_passwd()
    h = https("POST", "/api/userify/configure")
    if not h or not getattr(h, "sock"):
        time.sleep(1)
        return main()
    h.sock.settimeout(60)
    response = h.getresponse()
    text = response.read()
    failure = response.status != 200
    if debug or failure:
        print(("%s %s" % (response.status, response.reason)))
    configuration = {"error": "Unknown error parsing configuration"}
    try:
        configuration = json.loads(text.decode('utf-8'))
        if debug:
            pprint(configuration)
        if failure and "error" in configuration:
            print(("%s %s" % (response.reason.upper(), configuration["error"])))
    except Exception as e:
        failure = True
        print (line_spacer)
        print(("Error: %s" % e))
        # traceback.print_exc()
        pprint(text)
        print (line_spacer)
    if failure or "error" in configuration:
        return 180 + 60 * random.random()
    process_users(configuration["users"])
    install_shim_runner()

    # set hostname if set on server
    if "hostname" in configuration:
        try:
            hostname = str(configuration["hostname"])
            if socket.gethostname() != hostname:
                socket.sethostname(hostname)
                open("/etc/hostname", "w").write(hostname + "\n")
                # should set in /etc/hosts as well so
                # that sudo doesn't complain
                hosts = open("/etc/hosts").read().split("\n")
                line = "127.0.0.1 " + hostname + " # set by userify shim"
                if line not in hosts:
                    hosts.insert(1, line)
                    open("/etc/hosts", "w").write("\n").join(hosts)
        except Exception as e:
            print(("Unable to set hostname: %s" % e))

    # take over users if enabled and any are found
    if "takeover_users" in configuration and configuration["takeover_users"]:
        for username in configuration["takeover_users"]:
            if username in system_usernames():
                qexec(["usermod", "-c", "userify-%s" % username, username])

    # disable root SSH login keys if enabled and one exists
    if "disable_root_ssh_key" in configuration and configuration["disable_root_ssh_key"]:
        rootssh="/root/.ssh/"
        for fname in "authorized_keys", "authorized_keys2":
            if os.path.isfile(rootssh+fname):
                qexec(["/bin/mv", "-f", rootssh+fname, rootssh+"deleted:"+fname])

    return configuration["shim-delay"] if "shim-delay" in configuration else 1


app = {}
if __name__ == "__main__":
    try:
        print (line_spacer)
        print(("[shim] %s start: %s" % (shim_version, time.ctime())))
        s = time.time()
        try:
            time_to_wait = int(main())
        except Exception as e:
            print (line_spacer)
            print(("Error: %s" % e))
            print (line_spacer)
            # traceback.print_exc()
            time_to_wait = 180 + 60 * random.random()
            raise
        elapsed = time.time() - s
        if debug:
            print(("[shim] elapsed: " + str(int(elapsed * 1000)/1000.0) + "s"))
        if elapsed < time_to_wait:
            print(("[shim] sleeping: %ss" % int(time_to_wait-elapsed)))
            time.sleep(time_to_wait-elapsed)
    except Exception as e:
        print (line_spacer)
        print(("Error: %s" % e))
        print (line_spacer)
        t = 180 + 60 * random.random()
        print(("[shim] sleeping: %ss" % int(t)))
        time.sleep(t)
        # display error to stdout
        # and attempt restart via shim.sh
        raise
