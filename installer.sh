#! /bin/sh

# Userify Shim Installer
# Copyright (c) 2017 Userify Corporation

# How the shim works:
#
# 1. Installer creates /opt/userify/ containing:
#
#       a.  /opt/userify/creds.py
#       b.  /opt/userify/shim.sh (autostart on boot)
#       c.  /opt/userify/uninstall.sh
#       d.  /var/log/userify-shim.log (check this for output)
#
#    Review shim.sh and uninstall.sh in this file below
#    Entire /opt/userify directory and /var/log/userify-shim.log is root-only.
#
#
# 2. shim.sh, which should start on reboot, loops endlessly:
#
#       a.  download and run shim.py.
#
#       b.  shim.py reads creds.py and initiates a request for
#           the latest user list.
#
#       c.  upon making needed changes, shim.py delays before
#           exiting.
#

export RED_TEXT="[31m"
export BLUE_TEXT="[34m"
export GREEN_TEXT="[32m"
export PURPLE_TEXT="[35m"
export CYAN_TEXT="[36m"
export RESET_TEXT="[0m"

# for use only with Enterprise/Pro:
export SELFSIGNED="$1"

clear

# Install Python on distributions that might be missing it.
set +e

if [ ! $(which python) ]; then
    if [ $(which apt) ]; then
        echo "Installing Python with apt-get"
        sudo apt-get update >/dev/null
        sudo apt-get -qqy install python >/dev/null
        sudo apt-get -qqy install python-minimal >/dev/null
    elif [ $(which yum) ]; then
        echo "Installing Python with yum."
        sudo yum install -y python >/dev/null
    elif [ $(which dnf) ]; then
        echo "Installing Python with dnf"
        sudo dnf install -y python
    else
        set -e
        echo "Unable to install Python (2.6, 2.7). Please contact Userify support for assistance."
        exit 1
    fi
fi


cat << EOF

             ${BLUE_TEXT}            _--_
             ${BLUE_TEXT}           (    \\
             ${BLUE_TEXT}        --/      )
             ${BLUE_TEXT}   .-- /   \\      \\
             ${BLUE_TEXT} ./   \\            )${PURPLE_TEXT} _  __
             ${BLUE_TEXT}/${GREEN_TEXT}_   _ ___  ___ _ __${PURPLE_TEXT}(_)/ _|_   _
             ${GREEN_TEXT}| | | / __|/ _ \ '__${PURPLE_TEXT}| | |_  | | |
             ${GREEN_TEXT}| |_| \__ \  __/ |  ${PURPLE_TEXT}| |  _| |_| |
             ${GREEN_TEXT} \__,_|___/\___|_|  ${PURPLE_TEXT}|_|_|  \__, |
             ${GREEN_TEXT}                    ${PURPLE_TEXT}       |___/  ${GREEN_TEXT}tm
${RESET_TEXT}

[37;42m                Installing Userify now..                     ${RESET_TEXT}
-------------------------------------------------------------
${PURPLE_TEXT}Tip: to understand how the shim works, read the source at
${CYAN_TEXT}https://github.com/userify/shim/
${RESET_TEXT}
EOF

# to get things reset in case you are cat'ing..
export RESET_TEXT="[0m"

# Check for root
if [ "$(id -u)" != "0" ]; then
    cat << EOF >&2
${RED_TEXT}
Unfortunately, the Userify Shim requires root permissions in order to
create user accounts and manage sudoers. Please review the shim
source code at https://github.com/userify/shim
${RESET_TEXT}
EOF
    exit 1
fi


# Check for Linux
if [ "$(uname -s)" != "Linux" ]; then
    echo "${RED_TEXT}Currently, Userify supports only Linux systems.${RESET_TEXT}" >&2
fi


# Attempt to install sudo on Debian
# (might not be included on some very minimal/netinst Debian systems)
# set +e
# apt-get update 2>/dev/null
# apt-get -y install sudo 2>/dev/null
# set -e


set -e
[ -d /opt/userify ] && (
    echo "${RED_TEXT}Please remove /opt/userify, or execute
    ${GREEN_TEXT} sudo ${BLUE_TEXT}/opt/userify/uninstall.sh
${RED_TEXT}before continuing.${RESET_TEXT}" >&2
    exit 1
)


echo "${GREEN_TEXT}Creating Userify directory (/opt/userify/)${RESET_TEXT}"
mkdir -p /opt/userify/ || (
    echo "${RED_TEXT}Unable to create directory /opt/userify.${RESET_TEXT}" >&2
    exit 1
)


# Create uninstall.sh script in /opt/userify

echo "${GREEN_TEXT}Creating uninstall script (/opt/userify/uninstall.sh)${RESET_TEXT}"
cat << EOF > /opt/userify/uninstall.sh
#! /bin/sh +e

# --------------------------------------------
#
# uninstall.sh
# This script uninstalls the entire Userify agent and kills
# off any shim processes that are still running.
#
# --------------------------------------------

# Copyright (c) 2017 Userify Corp.

echo
echo
echo -------------------------------------------------------------
echo "[31mRemoving Userify...[0m"

if [ "$(id -u)" != "0" ]; then
    echo 'Need to have root privileges.'
    exit 1;
fi

# Debian, Ubuntu, RHEL:
sed -i "s/\/opt\/userify\/shim.sh \&//" \
    /etc/rc.local 2>/dev/null

# SUSE:
sed -i "s/\/opt\/userify\/shim.sh \&//" \
    /etc/init.d/after.local 2>/dev/null

# Fedora:
# systemctl disable userify-shim.service 2>/dev/null
# rm -f /etc/systemd/system/userify-shim.service 2>/dev/null

# Wipe out entire /opt/userify directory
rm -Rf /opt/userify/

# Kill off remaining shim processes
pkill shim. > /dev/null 2>&1

echo [32m

echo Finished!
echo Userify has been removed, but the user accounts it created still
echo exist and no changes have been made to them.
echo You can now install a new Userify shim as desired.
echo [0m-------------------------------------------------------------
echo
echo

EOF



if [ "x$api_id" != "x" ]; then
    echo "${GREEN_TEXT}Creating API login config (/opt/userify/creds.py)${RESET_TEXT}"
    echo -n > /opt/userify/creds.py
    chmod 0600 /opt/userify/creds.py

if [ -z "$shim_host" ]; then shim_host="shim.userify.com"; fi
if [ -z "$self_signed" ]; then self_signed="0"; fi

    # create creds configuration file
    cat <<EOF >> /opt/userify/creds.py
# Userify Credentials Configuration
# This file should be owned and readable only by root.

# This file sourced by both Python and Bash scripts, so please ensure changes
# are loadable by each.

# Instantly move this server to a different server group, even a server group
# in a different company, by replacing these with the credentials for the new
# server group.

company = "$company_name"
project = "$project_name"

api_id = "$api_id"
api_key = "$api_key"

EOF


# Create new, optional userify_config.py file

    cat <<EOF >> /opt/userify/userify_config.py
# Userify Shim Configuration

company="$company_name"
project="$project_name"

# This file sourced by both Python and Bash scripts, so please ensure changes
# are loadable by each.

# Enable this for additional verbosity in /var/log/userify-shim.log
debug=0

# Enable this to not actually make changes.
# This can also be used to temporary disable the shim.
dry_run=0

# Userify Enterprise/Pro licenses
shim_host="$shim_host"
static_host="$static_host"
self_signed=$self_signed

EOF

else
    echo "${RED_TEXT}api_id variable not found, skipping creds.py creation."
    echo "This might be a bug unless you did this on purpose."
    echo "NOTE, Userify cannot work without creds.py. Please create it yourself."
    echo ${RESET_TEXT}
fi


# Create shim.sh script in /opt/userify

echo "${GREEN_TEXT}Creating shim (/opt/userify/shim.{sh,py})${RESET_TEXT}"
cat << "EOF" > /opt/userify/shim.sh
#! /bin/bash +e

# --------------------------------------------
#
# shim.sh
# This is the script that actually calls
# shim.py.
#
# --------------------------------------------

# Copyright (c) 2017 Userify Corp.

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
curl -1 -f${SELFSIGNED}Ss https://$static_host/shim.py | $PYTHON -u 2>&1 >> /var/log/userify-shim.log

if [ $? != 0 ]; then
    # extra backoff in event of failure,
    # between one and seven minutes
    sleep $(($RANDOM%360+60))
fi

sleep 5

# call myself. fork before exiting.
/opt/userify/shim.sh &

EOF


echo "${GREEN_TEXT}Removing exit 0 from rc.local (if there)${RESET_TEXT}"
set +e
sed -i "s/^ *exit 0.*/# &/" /etc/rc.local 2>/dev/null
set -e

echo "${GREEN_TEXT}Checking Shim Startup${RESET_TEXT}"

# most Linux versions can manage with a line added to rc.local:
if [ -f /etc/rc.d/rc.local ]; then
    # RHEL7/Fedora/Amazon Linux
    distro="Linux"
    fname=/etc/rc.d/rc.local
elif [ -f /etc/rc.local ]; then
    distro="Linux"
    fname=/etc/rc.local
elif [ -f /etc/init.d/after.local ]; then
    distro="SUSE"
    fname=/etc/init.d/after.local
# elif [ -f /etc/fedora-release ]; then
#     distro="Fedora"
#     cat << EOF > /etc/systemd/system/userify-shim.service
# [Unit]
# Description=Userify Shim (userify.com)
# 
# [Service]
# Type=forking
# ExecStart=/opt/userify/shim.sh
# 
# [Install]
# WantedBy=multi-user.target
# EOF
#     systemctl enable userify-shim.service
else
    cat << EOF >&2
${RED_TEXT}
Unable to set start at bootup -- no /etc/rc.local file?
You'll have to set shim to startup on it's own: create an
init script that launches /opt/userify/shim.sh on startup.
In most distributions, this would have been a single line
in /etc/rc.local, but you may need to do something more
exotic. Please contact us with Linux version information
and we may have more information for you.${RESET_TEXT}
EOF
    exit 1
fi

# set +e
#     set +e; mv /etc/rc.local /etc/rc.local.old; set -e
#     ln -s /etc/rc.d/rc.local /etc/rc.local


# actually set up the startup
if [ "$distro" != "Fedora" ]; then
    # remove any existing lines:
    set +e
        sed -i "s/\/opt\/userify\/shim.sh \&//" "$fname" 2>/dev/null
    set -e
    echo "${GREEN_TEXT}Adding $distro Startup Script to $fname${RESET_TEXT}"
    echo >> "$fname"
    echo "/opt/userify/shim.sh &" >> "$fname"
fi

echo "${GREEN_TEXT}Setting Permissions${RESET_TEXT}"
chmod -R 700 \
    /opt/userify/ \
    /opt/userify/uninstall.sh \
    /opt/userify/shim.sh
[ -f /var/log/userify-shim.log ] && rm /var/log/userify-shim.log
touch /var/log/userify-shim.log
set +e
chmod +x /etc/rc.local 2>/dev/null
# RHEL7:
chmod +x /etc/rc.d/rc.local 2>/dev/null


echo "${GREEN_TEXT}Launching shim.sh${RESET_TEXT}"
set +e;
pkill shim. 2>/dev/null
set -e
/opt/userify/shim.sh &

echo
echo "${PURPLE_TEXT}Finished. Userify shim has been completely installed."
echo "/opt/userify/uninstall.sh as root to uninstall."
echo "debug=1 is enabled in /opt/userify/userify_config.py for extra verbosity."
echo "Please review shim output in /var/log/userify-shim.log"
# echo "(wait a few seconds..)"
# echo ${BLUE_TEXT}
# sleep 2
# output=$(cat /var/log/userify-shim.log)
# if [ "x$output" == "x" ]; then
#     echo ${RED_TEXT}
#     echo Unable to review userify-shim.log, please review it separately
#     echo to ensure the shim is working properly.
echo ${BLUE_TEXT}
echo cat /var/log/userify-shim.log
echo ${RESET_TEXT}
# else
#     echo $OUTPUT
# fi
echo ${GREEN_TEXT}
echo "Thanks for using Userify!"
echo ${RESET_TEXT}
echo -------------------------------------------------------------
echo


