#!/bin/bash

# cgroup_switch.sh
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
    echo "Run 'sudo reboot' to reboot the system and apply cgroup v1 configuration."
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
