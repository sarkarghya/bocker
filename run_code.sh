#!/bin/bash

# main_setup.sh
(
# Update package lists
apt-get update

# Install required packages including autopoint and python3-venv
apt-get install -y btrfs-progs curl iproute2 iptables cgroup-tools docker.io git autoconf automake gettext autopoint libtool python3-pip python3-venv



# Create btrfs filesystem
fallocate -l 10G ~/btrfs.img
mkdir -p /var/bocker
mkfs.btrfs ~/btrfs.img
mount -o loop ~/btrfs.img /var/bocker

# Start Docker
systemctl start docker
systemctl enable docker

# Create base image manually (avoiding undocker issues)
docker pull almalinux:9
docker create --name temp almalinux:9
mkdir -p ~/base-image
docker export temp | tar -xC ~/base-image
docker rm temp

# Create bocker symlink (adjust path as needed)
ln -s /path/to/bocker /usr/bin/bocker

# Configure networking
echo 1 > /proc/sys/net/ipv4/ip_forward
iptables --flush
iptables -t nat -A POSTROUTING -o bridge0 -j MASQUERADE
iptables -t nat -A POSTROUTING -o enp0s3 -j MASQUERADE

# Remove existing bridge if it exists
ip link del bridge0 2>/dev/null || true

# Create and configure bridge
ip link add bridge0 type bridge
ip addr add 10.0.0.1/24 dev bridge0
ip link set bridge0 up

# Clear all iptables rules
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

# Set default policies
iptables -P FORWARD ACCEPT
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT

# Add comprehensive iptables rules
iptables -t nat -A POSTROUTING -s 10.0.0.0/24 ! -o bridge0 -j MASQUERADE
iptables -A FORWARD -i bridge0 -o enp0s3 -j ACCEPT
iptables -A FORWARD -i enp0s3 -o bridge0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i bridge0 -o bridge0 -j ACCEPT

# Create Python virtual environment
python3 -m venv /opt/bocker-env

# Activate virtual environment and install dotenv
source /opt/bocker-env/bin/activate
pip install python-dotenv requests

cat > .env << 'EOF'
CLOUDFLARE_ACCOUNT_ID="2baaa4b8bd58d40ef343fd896f5afea8"
R2_BUCKET="images"
R2_ACCESS_KEY_ID="f94b0ba325ac641279ac11149dfb7653"
R2_SECRET_ACCESS_KEY="60b3a132d0865e4ae25279ae71e29235329393421a6d452d68078f43e2c2ddbd"
R2_DOMAIN="imagesbucket.utestny150.com"
R2_ENDPOINT="https://2baaa4b8bd58d40ef343fd896f5afea8.r2.cloudflarestorage.com"
RCLONE_REMOTE="r2aisb"
EOF

) 2>&1
