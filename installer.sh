#! /bin/sh

# Userify Shim Installer
# Copyright (c) 2011-2015 Userify Corporation


if [ "$(id -u)" != "0" ]; then
    cat << EOF >&2
Unfortunately, the Userify Shim requires root permissions in order to
create user accounts and manage sudoers.  The Shim is open source; please
feel free to audit the code for security.
EOF
    exit 1
fi

if [ "$(uname -s)" != "Linux" ]; then
    echo "Currently, Userify supports only Linux systems." >&2
fi

# on older apt-get systems, attempt to install sudo
set +e
apt-get update >/dev/null; apt-get -y install sudo >/dev/null
set -e

echo "Installing Userify and halting on errors."


set -e
echo "Creating Userify directory (/opt/userify/)"
[ -d /opt/userify ] && (
    echo "Please remove /opt/userify before continuing." >&2; exit -1)
mkdir /opt/userify/ || (
    echo "Unable to create directory /opt/userify." >&2; exit 1)


echo "Creating uninstall script (/opt/userify/uninstall.sh)"
cat << EOF > /opt/userify/uninstall.sh
#! /bin/sh +e
# Debian, Ubuntu, RHEL:
sed -i "s/\/opt\/userify\/shim.sh \&//" \
    /etc/rc.local 2>/dev/null
# SUSE:
sed -i "s/\/opt\/userify\/shim.sh \&//" \
    /etc/init.d/after.local 2>/dev/null
# # Fedora:
# systemctl disable userify-shim.service 2>/dev/null
# rm -f /etc/systemd/system/userify-shim.service 2>/dev/null
# rm -Rf /opt/userify/
# killall shim.py shim.sh
EOF


if [ "x$api_id" != "x" ]; then
    echo "Creating API login config (/opt/userify/creds.py)"
    echo -n > /opt/userify/creds.py
    chmod 0600 /opt/userify/creds.py
    # create creds configuration file
    cat <<EOF >> /opt/userify/creds.py
api_id="$api_id"
api_key="$api_key"
EOF
else
    echo "api_id variable not found, skipping creds.py creation."
fi


echo "Creating shim (/opt/userify/shim.{sh,py})"
cat << "EOF" > /opt/userify/shim.sh
#! /bin/bash +e

[ -z "$PYTHON" ] && PYTHON="$(which python)"
output=$(curl -k https://shim.userify.com/shim.py | $PYTHON 2>&1)
echo "$output" |tee /var/log/shim.log

# fix for thundering herd
sleep $(( ( RANDOM % 5 )  + 1 ))

/opt/userify/shim.sh &

EOF


echo "Removing exit 0 from rc.local"
set +e
sed -i "s/^ *exit 0.*/# &/" /etc/rc.local 2>/dev/null
set -e


echo "Checking Shim Startup"

# most Linux versions can manage with a line added to rc.local:
if [ -f /etc/rc.local ]; then
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
Unable to set start at bootup -- no /etc/rc.local file?
You'll have to set shim to startup on it's own: create an
init script that launches /opt/userify/shim.sh on startup.
In most distributions, this would have been a single line
in /etc/rc.local, but you may need to do something more
exotic. Please contact us with Linux version information
and we may have more information for you.
EOF
    exit 1
fi

# actually set up the startup
if [ "$distro" != "Fedora" ]; then
    echo "Adding $distro Startup Script to $fname"
    echo >> "$fname"
    echo "/opt/userify/shim.sh &" >> "$fname"
    # remove any existing lines:
    set +e
        sed -i "s/\/opt\/userify\/shim.sh \&//" "$fname" 2>/dev/null
    set -e
fi

echo "Setting Permissions"
chmod 700 /opt/userify/ /opt/userify/uninstall.sh /opt/userify/shim.sh


echo "Launching shim.sh"
set +e;
killall shim.py shim.sh 2>/dev/null
set -e
/opt/userify/shim.sh &

echo
echo "Finished. Userify shim has been completely installed."
echo "To remove at any point in the future, run /opt/userify/uninstall.sh"
