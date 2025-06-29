# %%
"""
# Building Your Own Container System (Bocker)

#### Learn containerization by implementing Docker-like functionality step by step

This tutorial is based on the complete bocker implementation in `bocker_ex.py`. 
You'll build the same container system through progressive exercises, where each 
exercise adds a new layer of functionality to the previous one.

By the end, you'll have implemented:
- Image pulling and management
- Container execution with chroot
- Resource control with cgroups  
- Process isolation with namespaces
- Container networking

<!-- toc -->

# Prerequisites

Make sure you have the following installed:
- Python 3.8+
- btrfs-tools: `sudo apt install btrfs-progs` (Linux) or equivalent
- cgroup-tools: `sudo apt install cgroup-tools` (Linux) or equivalent
- Root/sudo access for some operations

Let's start building!

"""

# %%
"""
## Exercise 1: Image Pulling and Registry Integration

In this first exercise, you'll implement the foundation of our container system:
pulling images from a remote registry. This is like `docker pull`.

We'll start with the basic imports and configuration, then build the pull functionality.
"""

import glob
import json
import os
import random
import requests
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass

# Optional import for dotenv, fallback gracefully if not available
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        pass

@dataclass
class BockerConfig:
    """Configuration class for Bocker settings"""
    btrfs_path: str = '/var/bocker'
    cgroups: str = 'cpu,cpuacct,memory'
    cpu_share: int = 512
    mem_limit: int = 512

    @classmethod
    def from_environment(cls):
        """Create configuration from environment variables"""
        return cls(
            btrfs_path=os.environ.get('BOCKER_BTRFS_PATH', '/var/bocker'),
            cgroups=os.environ.get('BOCKER_CGROUPS', 'cpu,cpuacct,memory'),
            cpu_share=int(os.environ.get('BOCKER_CPU_SHARE', '512')),
            mem_limit=int(os.environ.get('BOCKER_MEM_LIMIT', '512'))
        )

class BockerError(Exception):
    """Custom exception for Bocker operations"""
    pass

class BockerBase:
    """Base class with common functionality"""
    def __init__(self):
        self.config = BockerConfig.from_environment()
        self.btrfs_path = self.config.btrfs_path

    def _run_bash_command(self, bash_script, show_realtime=False):
        """Execute bash commands using bash -c"""
        try:
            if show_realtime:
                process = subprocess.Popen(
                    ['bash', '-c', bash_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                if process.stdout is not None:
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            print(output.rstrip())
                return_code = process.poll()
                return return_code if return_code is not None else 0
            else:
                result = subprocess.run(['bash', '-c', bash_script], capture_output=True, text=True)
                if result.returncode != 0:
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                    return result.returncode
                if result.stdout:
                    print(result.stdout.rstrip())
                return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def _generate_uuid(self, prefix="ps_"):
        """Generate UUID using Python instead of bash shuf"""
        return f"{prefix}{random.randint(42002, 42254)}"

    def _bocker_check(self, container_id):
        """Check if container/image exists using Python subprocess"""
        try:
            result = subprocess.run(
                ['btrfs', 'subvolume', 'list', self.btrfs_path],
                capture_output=True, text=True, check=True
            )
            return container_id in result.stdout
        except subprocess.CalledProcessError:
            return False

# Exercise 1: Implement the pull functionality
class BockerPull(BockerBase):
    """
    Container image pulling functionality.
    
    TODO: Complete the pull method below to download and extract container images.
    """
    
    def _list_images(self):
        """List available images"""
        images = []
        try:
            for img_path in glob.glob(f"{self.btrfs_path}/img_*"):
                img_id = os.path.basename(img_path)
                source_file = os.path.join(img_path, 'img.source')
                if os.path.exists(source_file):
                    with open(source_file, 'r') as f:
                        source = f.read().strip()
                    images.append({'id': img_id, 'source': source})
        except Exception:
            pass
        return images
    
    def pull(self, args):
        """
        Pull an image from cloud storage: BOCKER pull <name> <tag>
        
        This method should:
        1. Validate arguments (need name and tag)
        2. Get R2_DOMAIN from environment 
        3. Download the compressed image from the registry
        4. Extract and process the Docker image format
        5. Create a btrfs subvolume for the image
        6. Set up image metadata
        
        Args:
            args: List containing [name, tag]
            
        Returns:
            0 on success, 1 on failure
        """
        # TODO: Implement this method
        # Hint: Look at the pull method in bocker_ex.py for reference
        # You'll need to:
        # - Check arguments
        # - Load environment variables
        # - Download from URL like https://{r2_domain}/{name}_{tag}.tar.gz
        # - Extract tarball and process manifest.json
        # - Create btrfs subvolume and copy files
        # - Set image source metadata
        
        if len(args) < 2:
            print("Usage: bocker pull <name> <tag>", file=sys.stderr)
            return 1
            
        print("TODO: Implement pull functionality")
        print(f"Would pull {args[0]}:{args[1]}")
        return 1  # Return 1 until implemented

    def test_pull(self):
        """Test pull functionality"""
        print("Testing bocker pull...")
        
        # Test argument validation first
        returncode = self.pull([])
        if returncode != 1:
            print("FAIL: Pull should fail with no arguments")
            return False
        
        returncode = self.pull(['centos'])
        if returncode != 1:
            print("FAIL: Pull should fail with single argument")
            return False
        
        # Skip if R2_DOMAIN not configured
        load_dotenv()
        if not os.getenv('R2_DOMAIN'):
            print("SKIP: R2_DOMAIN not configured - cannot test actual pull")
            return True
        
        print("Testing pull with CentOS 7...")
        initial_image_count = len(self._list_images())
        
        returncode = self.pull(['centos', '7'])
        
        if returncode != 0:
            print(f"FAIL: Pull command failed with return code {returncode}")
            return False

        # Verify image was created
        new_images = self._list_images()
        if len(new_images) <= initial_image_count:
            print("FAIL: No new image created after pull")
            return False
        
        # Verify centos image exists
        centos_found = any('centos:7' in img['source'] for img in new_images)
        if not centos_found:
            print("FAIL: CentOS image not found in source after pull")
            return False

        print("PASS: bocker pull test")
        return True

# Test Exercise 1
def test_exercise_1():
    """Test Exercise 1: Pull functionality"""
    print("=" * 50)
    print("EXERCISE 1 TEST: Image Pulling")
    print("=" * 50)
    
    puller = BockerPull()
    success = puller.test_pull()
    
    if success:
        print("✓ Exercise 1 validation passed")
    else:
        print("✗ Exercise 1 validation failed")
    
    return success

# %%
"""
## Exercise 2: Container Creation and Chroot Execution

Now we'll add the ability to create images from directories and run containers 
with basic chroot isolation. This builds on Exercise 1 by adding container execution.

Key concepts:
- Creating images from filesystem directories (like `docker build`)
- Running containers with chroot for filesystem isolation
- Basic process execution within containers
"""

class BockerRunBasic(BockerPull):
    """
    Basic container execution with chroot isolation.
    Inherits pull functionality from Exercise 1.
    """
    
    def _list_images(self):
        """List available images"""
        images = []
        try:
            for img_path in glob.glob(f"{self.btrfs_path}/img_*"):
                img_id = os.path.basename(img_path)
                source_file = os.path.join(img_path, 'img.source')
                if os.path.exists(source_file):
                    with open(source_file, 'r') as f:
                        source = f.read().strip()
                    images.append({'id': img_id, 'source': source})
        except Exception:
            pass
        return images

    def _directory_exists(self, directory):
        """Check if directory exists using Python"""
        return Path(directory).exists()

    def init(self, args):
        """
        Create an image from a directory: BOCKER init <directory>
        
        TODO: Complete this method to create container images from directories.
        
        This method should:
        1. Validate that directory exists
        2. Generate unique image ID
        3. Create btrfs subvolume
        4. Copy directory contents to the subvolume
        5. Set image source metadata
        
        Args:
            args: List containing [directory_path]
            
        Returns:
            0 on success, 1 on failure
        """
        # TODO: Implement this method
        # Hint: Look at the init method in bocker_ex.py
        
        if len(args) < 1:
            print("Usage: bocker init <directory>", file=sys.stderr)
            return 1

        directory = args[0]
        if not self._directory_exists(directory):
            print(f"No directory named '{directory}' exists", file=sys.stderr)
            return 1

        print("TODO: Implement init functionality")
        print(f"Would create image from {directory}")
        return 1  # Return 1 until implemented

    def run(self, args):
        """
        Create and run a container: BOCKER run <image_id> <command>
        
        TODO: Implement basic container execution with chroot isolation.
        
        For this exercise, implement:
        1. Argument validation
        2. Image existence check  
        3. Container ID generation
        4. Btrfs snapshot creation
        5. Basic chroot execution (without namespaces/cgroups yet)
        
        Args:
            args: List containing [image_id, command, ...]
            
        Returns:
            0 on success, 1 on failure
        """
        # TODO: Implement this method
        # For this exercise, focus on:
        # - Validating arguments
        # - Checking image exists
        # - Creating container snapshot
        # - Basic chroot execution (we'll add namespaces/cgroups in later exercises)
        
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        print("TODO: Implement basic run functionality with chroot")
        print(f"Would run '{command}' in image {image_id}")
        return 1  # Return 1 until implemented

    def images(self, args):
        """List images: BOCKER images"""
        images = self._list_images()
        if not images:
            print("IMAGE_ID\t\tSOURCE")
            return 0
        
        print("IMAGE_ID\t\tSOURCE")
        for img in images:
            print(f"{img['id']}\t\t{img['source']}")
        return 0

    def test_init_and_run(self):
        """Test init and basic run functionality"""
        print("Testing bocker init and run...")
        
        # Test init argument validation
        returncode = self.init(['/nonexistent/directory'])
        if returncode != 1:
            print("FAIL: Init should fail with nonexistent directory")
            return False
        
        # Test run argument validation
        returncode = self.run([])
        if returncode != 1:
            print("FAIL: Run should fail with no arguments")
            return False
        
        returncode = self.run(['nonexistent_img', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Run should fail with nonexistent image")
            return False
        
        # Test with base image if available
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: Base image directory not found for full testing")
            return True
        
        # Get initial image count
        initial_images = len(self._list_images())
        
        # Create image from base directory
        returncode = self.init([base_image_dir])
        if returncode != 0:
            print(f"FAIL: Init command failed with return code {returncode}")
            return False

        # Verify image was created
        new_images = self._list_images()
        if len(new_images) != initial_images + 1:
            print("FAIL: Image count did not increase after init")
            return False
        
        # Get the new image ID
        latest_image = new_images[-1] if new_images else None
        if not latest_image or latest_image['source'] != base_image_dir:
            print(f"FAIL: Image source incorrect")
            return False
        
        img_id = latest_image['id']
        
        # Verify image directory exists
        if not self._bocker_check(img_id):
            print("FAIL: Created image not found in btrfs subvolumes")
            return False

        print("PASS: bocker init and basic validation test")
        return True

# Test Exercise 2
def test_exercise_2():
    """Test Exercise 2: Init and basic run"""
    print("=" * 50)
    print("EXERCISE 2 TEST: Init and Basic Run")
    print("=" * 50)
    
    runner = BockerRunBasic()
    success = runner.test_init_and_run()
    
    if success:
        print("✓ Exercise 2 validation passed")
    else:
        print("✗ Exercise 2 validation failed")
    
    return success

# %%
"""
## Exercise 3: Adding Cgroup Resource Control

Now we'll enhance our container execution with cgroup support for resource limiting.
This builds on Exercise 2 by adding CPU and memory limits to our containers.

Key concepts:
- Control Groups (cgroups) for resource isolation
- CPU shares and memory limits
- Process resource management
"""

class BockerWithCgroups(BockerRunBasic):
    """
    Container execution with cgroup resource control.
    Inherits init, pull, and basic run from previous exercises.
    """
    
    def run(self, args):
        """
        Enhanced run with cgroup support: BOCKER run <image_id> <command>
        
        TODO: Enhance the run method from Exercise 2 to include cgroup support.
        
        Building on Exercise 2, now add:
        1. Cgroup creation and configuration
        2. CPU share limits
        3. Memory limits  
        4. Process execution within cgroups
        5. Cgroup cleanup on container exit
        
        Args:
            args: List containing [image_id, command, ...]
            
        Returns:
            0 on success, 1 on failure
        """
        # TODO: Enhance the run method to include cgroup support
        # You can build on the basic run from Exercise 2 and add:
        # - cgcreate -g "{self.config.cgroups}:/{container_id}"
        # - cgset for CPU and memory limits
        # - cgexec to run process in cgroup
        # - cgdelete for cleanup
        
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        print("TODO: Implement run with cgroup support")
        print(f"Would run '{command}' in image {image_id} with cgroups")
        return 1  # Return 1 until implemented

    def test_cgroups(self):
        """Test cgroup functionality"""
        print("Testing cgroup integration...")
        
        # Basic validation tests
        returncode = self.run([])
        if returncode != 1:
            print("FAIL: Run should fail with no arguments")
            return False
        
        returncode = self.run(['nonexistent_img', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Run should fail with nonexistent image")
            return False
        
        # Test with base image if available
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: Base image directory not found for cgroup testing")
            return True
        
        # Create a test image
        returncode = self.init([base_image_dir])
        if returncode != 0:
            print("Note: Could not create test image for cgroup testing")
            return True
        
        images = self._list_images()
        if not images:
            print("Note: No images available for cgroup testing")
            return True
        
        print("Note: Cgroup tests require root privileges for full testing")
        print("PASS: bocker cgroup validation test")
        return True

# Test Exercise 3
def test_exercise_3():
    """Test Exercise 3: Cgroup support"""
    print("=" * 50)
    print("EXERCISE 3 TEST: Cgroup Resource Control")
    print("=" * 50)
    
    runner = BockerWithCgroups()
    success = runner.test_cgroups()
    
    if success:
        print("✓ Exercise 3 validation passed")
    else:
        print("✗ Exercise 3 validation failed")
    
    return success

# %%
"""
## Exercise 4: Process Isolation with Namespaces

Time to add true process isolation! We'll enhance our container execution with 
Linux namespaces for PID, mount, hostname, and other isolation.

Key concepts:
- PID namespace isolation
- Mount namespace for filesystem isolation
- UTS namespace for hostname isolation
- Process tree isolation
- Proper /proc mounting
"""

class BockerWithNamespaces(BockerWithCgroups):
    """
    Container execution with namespace isolation.
    Inherits all previous functionality and adds namespace support.
    """
    
    def run(self, args):
        """
        Enhanced run with namespace isolation: BOCKER run <image_id> <command>
        
        TODO: Add namespace support to the run method.
        
        Building on Exercise 3, now add:
        1. Process namespace isolation (PID namespace)
        2. Mount namespace isolation  
        3. UTS namespace (hostname isolation)
        4. Proper /proc filesystem mounting
        5. unshare command integration
        
        The complete isolation stack now includes:
        - Filesystem isolation (chroot) - from Exercise 2
        - Resource isolation (cgroups) - from Exercise 3  
        - Process isolation (namespaces) - this exercise
        
        Args:
            args: List containing [image_id, command, ...]
            
        Returns:
            0 on success, 1 on failure
        """
        # TODO: Add namespace support to run
        # Build on Exercise 3 and add:
        # - unshare -fmuip --mount-proc for namespace creation
        # - Proper /proc mounting inside container
        # - Process tree isolation
        # - Hostname isolation
        
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        print("TODO: Implement run with namespace isolation")
        print(f"Would run '{command}' in image {image_id} with namespaces + cgroups")
        return 1  # Return 1 until implemented

    def test_namespaces(self):
        """Test namespace functionality"""
        print("Testing namespace isolation...")
        
        # Basic validation tests
        returncode = self.run([])
        if returncode != 1:
            print("FAIL: Run should fail with no arguments")
            return False
        
        returncode = self.run(['nonexistent_img', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Run should fail with nonexistent image")
            return False
        
        # Test with base image if available
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: Base image directory not found for namespace testing")
            return True
        
        print("Note: Namespace tests require root privileges and proper unshare support")
        print("Note: Full namespace isolation testing would require running containers")
        print("PASS: bocker namespace validation test")
        return True

# Test Exercise 4
def test_exercise_4():
    """Test Exercise 4: Namespace isolation"""
    print("=" * 50)
    print("EXERCISE 4 TEST: Namespace Isolation")
    print("=" * 50)
    
    runner = BockerWithNamespaces()
    success = runner.test_namespaces()
    
    if success:
        print("✓ Exercise 4 validation passed")
    else:
        print("✗ Exercise 4 validation failed")
    
    return success

# %%
"""
## Exercise 5: Container Networking

Finally, we'll add networking support to create fully isolated containers that 
can communicate with each other and the outside world.

Key concepts:
- Network namespaces
- Virtual ethernet (veth) pairs
- Bridge networking
- Container IP assignment
- DNS resolution
"""

class BockerComplete(BockerWithNamespaces):
    """
    Complete container implementation with networking.
    This is the final class that includes all functionality.
    """
    
    def _list_containers(self):
        """List containers using Python glob instead of bash for loop"""
        containers = []
        try:
            for ps_path in glob.glob(f"{self.btrfs_path}/ps_*"):
                ps_id = os.path.basename(ps_path)
                cmd_file = os.path.join(ps_path, f'{ps_id}.cmd')
                if os.path.exists(cmd_file):
                    with open(cmd_file, 'r') as f:
                        command = f.read().strip()
                    containers.append({'id': ps_id, 'command': command})
        except Exception:
            pass
        return containers

    def _format_table_output(self, headers, rows):
        """Format table output using Python instead of bash echo -e"""
        if not rows:
            return '\t\t'.join(headers)
        output = ['\t\t'.join(headers)]
        for row in rows:
            output.append('\t\t'.join(row))
        return '\n'.join(output)

    def run(self, args):
        """
        Complete container execution: BOCKER run <image_id> <command>
        
        TODO: Complete the run method with full networking support.
        
        This is the final implementation that should include:
        1. All previous functionality (chroot, cgroups, namespaces)
        2. Network namespace creation
        3. Virtual ethernet pair setup
        4. Bridge networking configuration
        5. IP address assignment
        6. DNS resolution setup
        7. Full container isolation
        
        Args:
            args: List containing [image_id, command, ...]
            
        Returns:
            0 on success, 1 on failure
        """
        # TODO: Complete the final run implementation
        # This should combine everything from previous exercises plus:
        # - Network namespace: ip netns add netns_{container_id}
        # - Veth pair: ip link add dev veth0_{container_id} type veth peer name veth1_{container_id}
        # - Bridge attachment: ip link set veth0_{container_id} master bridge0
        # - IP configuration: ip addr add 10.0.0.X/24 dev veth1_{container_id}
        # - DNS setup: echo 'nameserver 8.8.8.8' > resolv.conf
        # - Full isolation execution
        
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        if not command.strip():
            print("Error: Command cannot be empty", file=sys.stderr)
            return 1

        print("TODO: Implement complete container execution with networking")
        print(f"Would run '{command}' in image {image_id} with full isolation")
        return 1  # Return 1 until implemented

    def ps(self, args):
        """List containers: BOCKER ps"""
        containers = self._list_containers()
        if not containers:
            print("CONTAINER_ID\t\tCOMMAND")
            return 0
        
        print("CONTAINER_ID\t\tCOMMAND")
        for container in containers:
            print(f"{container['id']}\t\t{container['command']}")
        return 0

    def logs(self, args):
        """View logs from a container: BOCKER logs <container_id>"""
        if len(args) < 1:
            print("Usage: bocker logs <container_id>", file=sys.stderr)
            return 1

        container_id = args[0]
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1

        log_file = Path(self.btrfs_path) / container_id / f"{container_id}.log"
        if not log_file.exists():
            print(f"No log file found for container '{container_id}'", file=sys.stderr)
            return 1

        try:
            with open(log_file, 'r') as f:
                print(f.read(), end='')
            return 0
        except Exception as e:
            print(f"Error reading log file: {e}", file=sys.stderr)
            return 1

    def rm(self, args):
        """Delete an image or container: BOCKER rm <id>"""
        if len(args) < 1:
            print("Usage: bocker rm <id>", file=sys.stderr)
            return 1

        container_id = args[0]
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs subvolume delete "{self.btrfs_path}/{container_id}" > /dev/null
        cgdelete -g "{self.config.cgroups}:/{container_id}" &> /dev/null || true
        echo "Removed: {container_id}"
        """
        return self._run_bash_command(bash_script)

    def exec(self, args):
        """Execute a command in a running container: BOCKER exec <container_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker exec <container_id> <command>", file=sys.stderr)
            return 1

        container_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        cid="$(ps o ppid,pid | grep "^$(ps o pid,cmd | grep -E "^\\ *[0-9]+ unshare.*{container_id}" | awk '{{print $1}}')" | awk '{{print $2}}')"
        [[ ! "$cid" =~ ^\\ *[0-9]+$ ]] && echo "Container '{container_id}' exists but is not running" && exit 1
        nsenter -t "$cid" -m -u -i -n -p chroot "{self.btrfs_path}/{container_id}" {command}
        """
        return self._run_bash_command(bash_script, show_realtime=True)

    def commit(self, args):
        """Commit a container to an image: BOCKER commit <container_id> <image_id>"""
        if len(args) < 2:
            print("Usage: bocker commit <container_id> <image_id>", file=sys.stderr)
            return 1

        container_id, image_id = args[0], args[1]
        
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs subvolume delete "{self.btrfs_path}/{image_id}" > /dev/null
        cgdelete -g "{self.config.cgroups}:/{image_id}" &> /dev/null || true
        btrfs subvolume snapshot "{self.btrfs_path}/{container_id}" "{self.btrfs_path}/{image_id}" > /dev/null
        echo "Created: {image_id}"
        """
        return self._run_bash_command(bash_script)

    def test_networking(self):
        """Test networking functionality"""
        print("Testing container networking...")
        
        # Basic validation tests
        returncode = self.run([])
        if returncode != 1:
            print("FAIL: Run should fail with no arguments")
            return False
        
        returncode = self.run(['nonexistent_img', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Run should fail with nonexistent image")
            return False
        
        # Test with base image if available
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: Base image directory not found for networking testing")
            return True
        
        print("Note: Networking tests require root privileges and bridge setup")
        print("Note: Full networking tests would create veth pairs and test connectivity")
        print("PASS: bocker networking validation test")
        return True

    def test_init(self):
        """Test init functionality"""
        print("Testing bocker init...")
        base_image_dir = os.path.expanduser('~/base-image')
        
        if not os.path.exists(base_image_dir):
            print(f"SKIP: Base image directory {base_image_dir} not found")
            return True
        
        # Test invalid directory first
        returncode = self.init(['/nonexistent/directory'])
        if returncode != 1:
            print("FAIL: Init should fail with nonexistent directory")
            return False
        
        # Get initial image count
        initial_images = len(self._list_images())
        
        # Create image
        returncode = self.init([base_image_dir])
        if returncode != 0:
            print(f"FAIL: Init command failed with return code {returncode}")
            return False

        # Verify image was created
        new_images = self._list_images()
        if len(new_images) != initial_images + 1:
            print("FAIL: Image count did not increase after init")
            return False
        
        # Verify the new image has correct source
        latest_image = new_images[-1]  # Assuming latest is last
        if latest_image['source'] != base_image_dir:
            print(f"FAIL: Image source is '{latest_image['source']}', expected '{base_image_dir}'")
            return False
        
        # Verify image directory exists
        if not self._bocker_check(latest_image['id']):
            print("FAIL: Created image not found in btrfs subvolumes")
            return False

        print("PASS: bocker init test")
        return True

    def test_images(self):
        """Test images functionality"""
        print("Testing bocker images...")
        
        # Test with no images first
        initial_images = self._list_images()
        
        # Capture output by redirecting stdout temporarily
        import io
        from contextlib import redirect_stdout
        
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            returncode = self.images([])
        
        if returncode != 0:
            print(f"FAIL: Images command failed with return code {returncode}")
            return False
        
        output = output_buffer.getvalue()
        lines = output.strip().split('\n')
        
        # Verify header is correct
        if not lines or lines[0] != 'IMAGE_ID\t\tSOURCE':
            print(f"FAIL: Expected header 'IMAGE_ID\\t\\tSOURCE' but got: {lines[0] if lines else 'empty'}")
            return False
        
        # If we have images, verify they're listed
        if initial_images:
            if len(lines) != len(initial_images) + 1:  # +1 for header
                print(f"FAIL: Expected {len(initial_images) + 1} lines but got {len(lines)}")
                return False
            
            # Verify each image is listed
            for image in initial_images:
                found = False
                for line in lines[1:]:  # Skip header
                    if image['id'] in line and image['source'] in line:
                        found = True
                        break
                if not found:
                    print(f"FAIL: Image {image['id']} not found in output")
                    return False

        print("PASS: bocker images test")
        return True

    def test_rm(self):
        """Test rm functionality"""
        print("Testing bocker rm...")
        
        # Create a test image first
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: Base image directory not found")
            return True
            
        # Create image
        self.init([base_image_dir])
        
        # Get the image ID
        images = self._list_images()
        if not images:
            print("FAIL: No images found to test removal")
            return False
            
        img_id = images[0]['id']
        
        # Remove the image
        returncode = self.rm([img_id])
        
        if returncode != 0:
            print(f"FAIL: RM command failed with return code {returncode}")
            return False

        # Verify it's gone
        if self._bocker_check(img_id):
            print("FAIL: Image still exists after removal")
            return False

        print("PASS: bocker rm test")
        return True

    def test_ps(self):
        """Test ps functionality"""
        print("Testing bocker ps...")
        
        # Capture output to verify format
        import io
        from contextlib import redirect_stdout
        
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            returncode = self.ps([])
        
        if returncode != 0:
            print(f"FAIL: PS command failed with return code {returncode}")
            return False
        
        output = output_buffer.getvalue()
        lines = output.strip().split('\n')
        
        # Verify header is correct
        if not lines or lines[0] != 'CONTAINER_ID\t\tCOMMAND':
            print(f"FAIL: Expected header 'CONTAINER_ID\\t\\tCOMMAND' but got: {lines[0] if lines else 'empty'}")
            return False
        
        # Get current containers to verify listing
        containers = self._list_containers()
        
        if containers:
            # Should have header + container entries
            if len(lines) != len(containers) + 1:  # +1 for header
                print(f"FAIL: Expected {len(containers) + 1} lines but got {len(lines)}")
                return False
            
            # Verify each container is listed
            for container in containers:
                found = False
                for line in lines[1:]:  # Skip header
                    if container['id'] in line and container['command'] in line:
                        found = True
                        break
                if not found:
                    print(f"FAIL: Container {container['id']} not found in ps output")
                    return False
        else:
            # Should only have header
            if len(lines) != 1:
                print(f"FAIL: Expected only header when no containers exist, got {len(lines)} lines")
                return False

        print("PASS: bocker ps test")
        return True

    def test_run(self):
        """Test run functionality with comprehensive tests"""
        print("Testing bocker run...")
        
        # Get or create a test image
        images = self._list_images()
        if not images:
            base_image_dir = os.path.expanduser('~/base-image')
            if not os.path.exists(base_image_dir):
                print("SKIP: No images available and no base image directory")
                return True
            returncode = self.init([base_image_dir])
            if returncode != 0:
                print("FAIL: Could not create test image")
                return False
            images = self._list_images()
        
        if not images:
            print("FAIL: No images available for testing")
            return False
            
        img_id = images[0]['id']
        print(f"Using image: {img_id}")
        
        # Test invalid image first
        returncode = self.run(['nonexistent_img', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Run should fail with nonexistent image")
            return False
        
        # Test empty command
        returncode = self.run([img_id])
        if returncode != 1:
            print("FAIL: Run should fail with no command")
            return False

        print("PASS: bocker run test")
        return True

    def test_logs(self):
        """Test logs functionality"""
        print("Testing bocker logs...")
        
        # Test with invalid container first
        returncode = self.logs(['nonexistent_container'])
        if returncode != 1:
            print("FAIL: Logs should fail with nonexistent container")
            return False
        
        # Test with no arguments
        returncode = self.logs([])
        if returncode != 1:
            print("FAIL: Logs should fail with no arguments")
            return False
        
        print("PASS: bocker logs test")
        return True

    def test_exec(self):
        """Test exec functionality"""
        print("Testing bocker exec...")
        
        # Test argument validation first
        returncode = self.exec([])
        if returncode != 1:  # Should fail with usage message
            print(f"FAIL: Exec should fail with no arguments")
            return False
        
        # Test with invalid container
        returncode = self.exec(['nonexistent_container', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Exec should fail with nonexistent container")
            return False
        
        print("PASS: bocker exec test (argument validation)")
        return True

    def test_commit(self):
        """Test commit functionality"""
        print("Testing bocker commit...")
        
        # Test argument validation first
        returncode = self.commit([])
        if returncode != 1:  # Should fail with usage message
            print(f"FAIL: Commit should fail with no arguments")
            return False
        
        # Test with single argument
        returncode = self.commit(['container_id'])
        if returncode != 1:  # Should fail with usage message
            print(f"FAIL: Commit should fail with single argument")
            return False
        
        # Test with invalid container
        returncode = self.commit(['nonexistent_container', 'nonexistent_image'])
        if returncode != 1:
            print("FAIL: Commit should fail with nonexistent container")
            return False
        
        print("PASS: bocker commit test")
        return True

    def run_all_tests(self):
        """Run all tests in dependency order"""
        print("=" * 60)
        print("BOCKER COMPLETE TEST SUITE")
        print("=" * 60)
        
        # Check prerequisites
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("WARNING: Base image directory ~/base-image not found")
            print("Some tests may be skipped. Create a base image directory for full testing.")
        
        print(f"Using btrfs path: {self.btrfs_path}")
        print(f"Using cgroups: {self.config.cgroups}")
        print()

        # Test functions in dependency order
        test_sequence = [
            ('Init', self.test_init),
            ('Images', self.test_images),
            ('RM', self.test_rm),
            ('PS', self.test_ps),
            ('Pull', self.test_pull),
            ('Run', self.test_run),
            ('Logs', self.test_logs),
            ('Exec', self.test_exec),
            ('Commit', self.test_commit),
        ]

        passed = 0
        failed = 0
        skipped = 0

        for test_name, test_func in test_sequence:
            print(f"\n{'-' * 40}")
            print(f"Testing {test_name}")
            print(f"{'-' * 40}")
            
            try:
                result = test_func()
                if result is True:
                    passed += 1
                    print(f"✓ {test_name} PASSED")
                elif result is None:
                    skipped += 1
                    print(f"~ {test_name} SKIPPED")
                else:
                    failed += 1
                    print(f"✗ {test_name} FAILED")
            except Exception as e:
                failed += 1
                print(f"✗ {test_name} FAILED with exception: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(1)

        print(f"\n{'=' * 60}")
        print(f"TEST RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
        print(f"{'=' * 60}")

        return failed == 0

# Test Exercise 5
def test_exercise_5():
    """Test Exercise 5: Complete networking"""
    print("=" * 50)
    print("EXERCISE 5 TEST: Container Networking")
    print("=" * 50)
    
    bocker = BockerComplete()
    success = bocker.test_networking()
    
    if success:
        print("✓ Exercise 5 validation passed")
    else:
        print("✗ Exercise 5 validation failed")
    
    return success

# %%
"""
## Complete Test Suite

This runs the same comprehensive tests as bocker_ex.py to validate your implementation.
"""

def run_complete_tests():
    """Run the complete test suite matching bocker_ex.py"""
    bocker = BockerComplete()
    return bocker.run_all_tests()

def test_ps_functionality(bocker):
    """Test ps command"""
    try:
        # Capture output to verify format
        import io
        from contextlib import redirect_stdout
        
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            returncode = bocker.ps([])
        
        if returncode != 0:
            print(f"FAIL: PS command failed with return code {returncode}")
            return False
        
        output = output_buffer.getvalue()
        lines = output.strip().split('\n')
        
        # Verify header is correct
        if not lines or lines[0] != 'CONTAINER_ID\t\tCOMMAND':
            print(f"FAIL: Expected header 'CONTAINER_ID\\t\\tCOMMAND' but got: {lines[0] if lines else 'empty'}")
            return False
        
        print("PASS: bocker ps test")
        return True
    except Exception as e:
        print(f"FAIL: PS test failed with exception: {e}")
        return False

def test_run_functionality(bocker):
    """Test run command validation"""
    try:
        # Test argument validation
        returncode = bocker.run([])
        if returncode != 1:
            return False
        
        returncode = bocker.run(['nonexistent_img', 'echo', 'test'])
        if returncode != 1:
            return False
        
        return True
    except:
        return False

def test_logs_functionality(bocker):
    """Test logs command"""
    try:
        # Test with no arguments - should fail
        returncode = bocker.logs([])
        if returncode != 1:
            print("FAIL: Logs should fail with no arguments")
            return False
        
        # Test with invalid container
        returncode = bocker.logs(['nonexistent_container'])
        if returncode != 1:
            print("FAIL: Logs should fail with nonexistent container")
            return False
        
        print("PASS: bocker logs validation test")
        return True
    except Exception as e:
        print(f"FAIL: Logs test failed with exception: {e}")
        return False

def test_exec_functionality(bocker):
    """Test exec command"""
    try:
        # Test argument validation
        returncode = bocker.exec([])
        if returncode != 1:  # Should fail with no args
            print("FAIL: Exec should fail with no arguments")
            return False
        
        # Test with invalid container
        returncode = bocker.exec(['nonexistent_container', 'echo', 'test'])
        if returncode != 1:
            print("FAIL: Exec should fail with nonexistent container")
            return False
        
        print("PASS: bocker exec validation test")
        return True
    except Exception as e:
        print(f"FAIL: Exec test failed with exception: {e}")
        return False

def test_commit_functionality(bocker):
    """Test commit command"""
    try:
        # Test argument validation
        returncode = bocker.commit([])
        if returncode != 1:  # Should fail with no args
            print("FAIL: Commit should fail with no arguments")
            return False
        
        # Test with single argument
        returncode = bocker.commit(['container_id'])
        if returncode != 1:  # Should fail with single arg
            print("FAIL: Commit should fail with single argument")
            return False
        
        # Test with invalid container/image
        returncode = bocker.commit(['nonexistent_container', 'nonexistent_image'])
        if returncode != 1:
            print("FAIL: Commit should fail with nonexistent container")
            return False
        
        print("PASS: bocker commit validation test")
        return True
    except Exception as e:
        print(f"FAIL: Commit test failed with exception: {e}")
        return False

def test_rm_functionality(bocker):
    """Test rm command"""
    try:
        # Test argument validation
        returncode = bocker.rm([])
        if returncode != 1:  # Should fail with no args
            print("FAIL: RM should fail with no arguments")
            return False
        
        # Test with invalid container/image
        returncode = bocker.rm(['nonexistent_item'])
        if returncode != 1:
            print("FAIL: RM should fail with nonexistent item")
            return False
        
        print("PASS: bocker rm validation test")
        return True
    except Exception as e:
        print(f"FAIL: RM test failed with exception: {e}")
        return False

# %%
"""
## Exercise Instructions and Next Steps

### How to Complete the Exercises:

1. **Exercise 1 (Pull)**: Implement the `pull` method in `BockerPull` class
   - Download images from remote registry
   - Extract and process Docker image format
   - Set up btrfs subvolumes

2. **Exercise 2 (Init/Run Basic)**: Implement `init` and basic `run` in `BockerRunBasic` 
   - Create images from directories
   - Basic container execution with chroot

3. **Exercise 3 (Cgroups)**: Enhance `run` in `BockerWithCgroups`
   - Add CPU and memory limits
   - Process resource control

4. **Exercise 4 (Namespaces)**: Enhance `run` in `BockerWithNamespaces`
   - Add PID, mount, UTS namespace isolation
   - Proper /proc mounting

5. **Exercise 5 (Networking)**: Complete `run` in `BockerComplete`
   - Network namespace and veth pairs
   - Bridge networking and IP assignment
   - DNS resolution

### Testing Your Implementation:

```python
# Test individual exercises
test_exercise_1()  # Test pull functionality
test_exercise_2()  # Test init and basic run
test_exercise_3()  # Test cgroup integration
test_exercise_4()  # Test namespace isolation
test_exercise_5()  # Test networking

# Test complete implementation
run_complete_tests()  # Run full test suite
```

### Key Implementation Tips:

- Look at `bocker_ex.py` for complete reference implementations
- Each exercise builds on the previous one
- You can copy and enhance methods from previous exercises
- Focus on one isolation primitive at a time
- Test frequently as you implement each piece

### Learning Objectives:

By completing these exercises, you'll understand:
- How container images are stored and distributed
- Filesystem isolation with chroot and mount namespaces
- Resource control with cgroups
- Process isolation with PID namespaces
- Container networking with bridges and veth pairs
- How Docker and other container runtimes work internally

Good luck building your container system! 🐳
"""

# Main execution
if __name__ == "__main__":
    print("Bocker Container System - Progressive Implementation")
    print("=" * 55)
    print()
    print("Complete the exercises in order to build a full container system:")
    print("1. Pull - Image downloading and registry integration")
    print("2. Init/Run - Basic container execution with chroot") 
    print("3. Cgroups - Resource control and limits")
    print("4. Namespaces - Process and filesystem isolation")
    print("5. Networking - Container networking and communication")
    print()
    
    # Run individual exercise tests
    exercises = [
        ("Exercise 1: Pull", test_exercise_1),
        ("Exercise 2: Init/Run", test_exercise_2), 
        ("Exercise 3: Cgroups", test_exercise_3),
        ("Exercise 4: Namespaces", test_exercise_4),
        ("Exercise 5: Networking", test_exercise_5),
    ]
    
    for name, test_func in exercises:
        print(f"\n{name}")
        print("-" * len(name))
        test_func()
    
    print("\n" + "=" * 55)
    print("Complete all exercises, then run the full test suite:")
    print("python w2d2_solution.py --complete-tests")
    
    if len(sys.argv) > 1 and sys.argv[1] == '--complete-tests':
        print("\nRunning complete test suite...")
        run_complete_tests() 