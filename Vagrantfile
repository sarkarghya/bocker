$script = <<SCRIPT
(
# Update package lists
apt-get update

# Install required packages including autopoint
apt-get install -y btrfs-progs curl iproute2 iptables cgroup-tools docker.io git autoconf automake gettext autopoint libtool python3-pip

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

# Create bocker symlink
ln -s /vagrant/bocker /usr/bin/bocker

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
) 2>&1
SCRIPT

$cgroup_switch_script = <<SCRIPT
# Function to switch to cgroup v1
switch_to_cgroupv1() {
    echo "Checking current cgroup version..."
    
    # Check if we're already on cgroup v1
    if [ -d "/sys/fs/cgroup/memory" ] && [ -d "/sys/fs/cgroup/cpu" ]; then
        echo "System is already using cgroup v1"
        return 0
    fi
    
    echo "System is using cgroup v2. Switching to cgroup v1..."
    
    # Backup current GRUB configuration
    cp /etc/default/grub /etc/default/grub.backup
    
    # Check if the kernel parameter is already present
    if grep -q "systemd.unified_cgroup_hierarchy=false" /etc/default/grub; then
        echo "cgroup v1 parameter already present in GRUB config"
    else
        # Add kernel parameter to disable cgroup v2 (enable cgroup v1)
        sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="systemd.unified_cgroup_hierarchy=false /' /etc/default/grub
        
        # Also add to GRUB_CMDLINE_LINUX if it exists
        if grep -q "^GRUB_CMDLINE_LINUX=" /etc/default/grub; then
            sed -i 's/GRUB_CMDLINE_LINUX="/GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=false /' /etc/default/grub
        fi
        
        echo "Added cgroup v1 kernel parameter to GRUB configuration"
    fi
    
    # Update GRUB
    update-grub
    
    # Create a flag file to indicate reboot is needed
    touch /tmp/cgroup_reboot_needed
    
    echo "GRUB configuration updated. System needs to be rebooted to switch to cgroup v1."
    echo "Run 'vagrant reload' to reboot the VM and apply cgroup v1 configuration."
}

# Function to verify cgroup version after reboot
verify_cgroup_version() {
    echo "Verifying cgroup version..."
    
    if [ -d "/sys/fs/cgroup/memory" ] && [ -d "/sys/fs/cgroup/cpu" ]; then
        echo "SUCCESS: System is now using cgroup v1"
        echo "Available cgroup v1 controllers:"
        ls -la /sys/fs/cgroup/ | grep -E "(memory|cpu|blkio|devices|freezer|net_cls|net_prio|pids)"
        
        # Remove the reboot flag
        rm -f /tmp/cgroup_reboot_needed
        
        return 0
    else
        echo "WARNING: System appears to still be using cgroup v2"
        echo "You may need to check your GRUB configuration and reboot again"
        return 1
    fi
}

# Check if this is a post-reboot verification
if [ -f "/tmp/cgroup_reboot_needed" ]; then
    echo "Detected post-reboot state. Verifying cgroup configuration..."
    verify_cgroup_version
else
    # Initial setup - switch to cgroup v1
    switch_to_cgroupv1
fi
SCRIPT

Vagrant.configure(2) do |config|
  # Use Ubuntu 20.04 LTS as the base box
  config.vm.box = "ubuntu/focal64"
  
  # Configure VM resources
  config.vm.provider "virtualbox" do |vb|
    vb.memory = "2048"
    vb.cpus = 2
    vb.name = "bocker-vm"
  end
  
  # Configure network
  config.vm.network "private_network", ip: "192.168.56.10"
  
  # Sync the bocker directory
  config.vm.synced_folder ".", "/vagrant", type: "virtualbox"
  
  # Run the main provisioning script
  config.vm.provision "shell", inline: $script, privileged: true
  
  # Set up additional configuration
  config.vm.provision "shell", inline: <<-SHELL
    # Make bocker executable
    chmod +x /vagrant/bocker
    
    # Add vagrant user to docker group
    usermod -aG docker vagrant
    
    # Create a test directory for containers
    mkdir -p /home/vagrant/containers
    chown vagrant:vagrant /home/vagrant/containers
    
    # Final cgroup verification
    echo "Final cgroup verification:"
    if [ -d "/sys/fs/cgroup/memory" ] && [ -d "/sys/fs/cgroup/cpu" ]; then
        echo "✓ cgroup v1 is active and ready for bocker"
    else
        echo "⚠ cgroup v2 detected - you may need to run 'vagrant reload' to complete the switch"
    fi
    
    echo "Bocker environment setup complete!"
    echo "You can now use 'bocker' commands to manage containers"
  SHELL
end
