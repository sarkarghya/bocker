## **System Prerequisites Installation**

**Install Required Packages:**
```bash
# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install btrfs-progs curl iproute2 iptables cgroup-tools util-linux coreutils

# On CentOS/RHEL
sudo yum install btrfs-progs curl iproute iptables libcgroup-tools util-linux coreutils

# On Arch Linux
sudo pacman -S btrfs-progs curl iproute2 iptables libcgroup util-linux coreutils
```

**Check util-linux Version:**
```bash
# Must be >= 2.25.2
unshare --version
```

If your version is too old, compile from source:
```bash
wget https://www.kernel.org/pub/linux/utils/util-linux/v2.25/util-linux-2.25.2.tar.gz
tar -xzf util-linux-2.25.2.tar.gz
cd util-linux-2.25.2
./configure --prefix=/usr/local
make && sudo make install
```

## **Filesystem Setup**

**Create Btrfs Filesystem:**
```bash
# Create a disk image file (if you don't have a dedicated partition)
sudo dd if=/dev/zero of=/var/bocker.img bs=1G count=10

# Format as btrfs
sudo mkfs.btrfs /var/bocker.img

# Create mount point
sudo mkdir -p /var/bocker

# Mount the filesystem
sudo mount -o loop /var/bocker.img /var/bocker

# Make mount permanent (add to /etc/fstab)
echo "/var/bocker.img /var/bocker btrfs loop 0 0" | sudo tee -a /etc/fstab
```

**Verify Btrfs Mount:**
```bash
df -T /var/bocker
# Should show btrfs filesystem type
```

## **Network Configuration**

**Create Bridge Interface:**
```bash
# Create bridge0
sudo ip link add name bridge0 type bridge

# Assign IP address
sudo ip addr add 10.0.0.1/24 dev bridge0

# Bring bridge up
sudo ip link set bridge0 up

# Verify bridge creation
ip addr show bridge0
```

**Enable IP Forwarding:**
```bash
# Enable temporarily
echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward

# Make permanent
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**Configure Firewall Rules:**
```bash
# Allow forwarding from bridge0 to your main interface (replace eth0 with your interface)
sudo iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -i bridge0 -o eth0 -j ACCEPT
sudo iptables -A FORWARD -i eth0 -o bridge0 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Save iptables rules (method varies by distribution)
# Ubuntu/Debian:
sudo iptables-save | sudo tee /etc/iptables/rules.v4

# CentOS/RHEL:
sudo service iptables save
```

## **Bocker Installation**

**Download and Setup Bocker:**
```bash
# Clone or download bocker
wget https://raw.githubusercontent.com/p8952/bocker/master/bocker
chmod +x bocker

# Move to system path (optional)
sudo mv bocker /usr/local/bin/

# Verify bocker is executable
./bocker help
```