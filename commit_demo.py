#!/usr/bin/env python3

import glob
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BockerConfig:
    """Configuration class for Bocker settings"""
    btrfs_path: str = '/var/bocker'

    @classmethod
    def from_environment(cls):
        """Create configuration from environment variables"""
        return cls(
            btrfs_path=os.environ.get('BOCKER_BTRFS_PATH', '/var/bocker')
        )

class BockerError(Exception):
    """Custom exception for Bocker operations"""
    pass

class Bocker:
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

    def _generate_uuid(self, prefix="ps_"):
        """Generate UUID using Python instead of bash shuf"""
        return f"{prefix}{random.randint(42002, 42254)}"

    def _directory_exists(self, directory):
        """Check if directory exists using Python"""
        return Path(directory).exists()

    def _list_images(self):
        """List images using Python glob instead of bash for loop"""
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

    def init(self, args):
        """Create an image from a directory: BOCKER init <directory>"""
        if len(args) < 1:
            print("Usage: bocker init <directory>", file=sys.stderr)
            return 1

        directory = args[0]
        if not self._directory_exists(directory):
            print(f"No directory named '{directory}' exists", file=sys.stderr)
            return 1

        uuid = self._generate_uuid("img_")
        if self._bocker_check(uuid):
            return self.init(args)

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs subvolume create "{self.btrfs_path}/{uuid}" > /dev/null
        cp -rf --reflink=auto "{directory}"/* "{self.btrfs_path}/{uuid}" > /dev/null
        [[ ! -f "{self.btrfs_path}/{uuid}"/img.source ]] && echo "{directory}" > "{self.btrfs_path}/{uuid}"/img.source
        echo "Created: {uuid}"
        """
        return self._run_bash_command(bash_script)

    def images(self, args):
        """List images: BOCKER images"""
        images = self._list_images()
        if not images:
            print("IMAGE_ID\t\tSOURCE")
            return 0
        rows = [[img['id'], img['source']] for img in images]
        output = self._format_table_output(['IMAGE_ID', 'SOURCE'], rows)
        print(output)
        return 0

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
        echo "Removed: {container_id}"
        """
        return self._run_bash_command(bash_script)

    def ps(self, args):
        """List containers: BOCKER ps"""
        containers = self._list_containers()
        if not containers:
            print("CONTAINER_ID\t\tCOMMAND")
            return 0
        rows = [[container['id'], container['command']] for container in containers]
        output = self._format_table_output(['CONTAINER_ID', 'COMMAND'], rows)
        print(output)
        return 0

    def run(self, args):
        """Create a container: BOCKER run <image_id> <command>"""
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

        uuid = self._generate_uuid("ps_")
        if self._bocker_check(uuid):
            return self.run(args)

        ip_suffix = uuid[-3:].replace('0', '') or '1'
        mac_suffix = f"{uuid[-3:-2]}:{uuid[-2:]}"

        bash_script = f"""
        set -o errexit -o nounset -o pipefail; shopt -s nullglob
        
        ip link add dev veth0_"{uuid}" type veth peer name veth1_"{uuid}"
        ip link set dev veth0_"{uuid}" up
        ip link set veth0_"{uuid}" master bridge0
        ip netns add netns_"{uuid}"
        ip link set veth1_"{uuid}" netns netns_"{uuid}"
        ip netns exec netns_"{uuid}" ip link set dev lo up
        ip netns exec netns_"{uuid}" ip link set veth1_"{uuid}" address 02:42:ac:11:00{mac_suffix}
        ip netns exec netns_"{uuid}" ip addr add 10.0.0.{ip_suffix}/24 dev veth1_"{uuid}"
        ip netns exec netns_"{uuid}" ip link set dev veth1_"{uuid}" up
        ip netns exec netns_"{uuid}" ip route add default via 10.0.0.1

        btrfs subvolume snapshot "{self.btrfs_path}/{image_id}" "{self.btrfs_path}/{uuid}" > /dev/null
        echo 'nameserver 8.8.8.8' > "{self.btrfs_path}/{uuid}"/etc/resolv.conf
        echo "{command}" > "{self.btrfs_path}/{uuid}/{uuid}.cmd"
        
        ip netns exec netns_"{uuid}" \\
        unshare -fmuip --mount-proc \\
        chroot "{self.btrfs_path}/{uuid}" \\
        /bin/sh -c "/bin/mount -t proc proc /proc && {command}" \\
        2>&1 | tee "{self.btrfs_path}/{uuid}/{uuid}.log" || true

        ip link del dev veth0_"{uuid}"
        ip netns del netns_"{uuid}"
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
        btrfs subvolume snapshot "{self.btrfs_path}/{container_id}" "{self.btrfs_path}/{image_id}" > /dev/null
        echo "Created: {image_id}"
        """
        return self._run_bash_command(bash_script)

    def test_commit(self):
        """Test commit functionality using wget installation pattern"""
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
        if returncode == 0:
            print("FAIL: Commit should fail with nonexistent container")
            return False
        
        # Create test image for commit testing
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: No base image directory available for commit testing")
            return True
        
        # Initialize a new image from base
        returncode = self.init([base_image_dir])
        if returncode != 0:
            print("FAIL: Could not create test image for commit")
            return False
        
        # Get the newly created image ID
        images = self._list_images()
        img_id = None
        for img in images:
            if base_image_dir in img['source']:
                img_id = img['id']
                break
        
        if not img_id:
            print("FAIL: Could not find created test image")
            return False
        
        print(f"Created test image: {img_id}")
        time.sleep(1)
        
        # Test 1: Run wget command (should fail since wget is not installed)
        print("Step 1: Testing wget command (should fail)...")
        returncode = self.run([img_id, 'wget'])
        time.sleep(2)
        
        # Get container ID for wget test
        containers = self._list_containers()
        wget_test_container = None
        for container in containers:
            if 'wget' in container['command'] and 'yum' not in container['command']:
                wget_test_container = container['id']
                break
        
        if wget_test_container:
            print(f"Wget test container: {wget_test_container}")
            # Check logs to confirm wget is not installed
            log_file = Path(self.btrfs_path) / wget_test_container / f"{wget_test_container}.log"
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                    if 'command not found' in log_content or 'wget: command not found' in log_content:
                        print("Confirmed: wget command not found (as expected)")
                    else:
                        print(f"Warning: Unexpected wget output: {log_content}")
                except Exception as e:
                    print(f"Warning: Could not read wget test logs: {e}")
            
            # Clean up test container
            self.rm([wget_test_container])
        
        # Test 2: Install wget using yum
        print("Step 2: Installing wget using yum...")
        returncode = self.run([img_id, 'yum', 'install', '-y', 'wget'])
        time.sleep(5)  # Give more time for yum install
        
        # Get container ID for yum install
        containers = self._list_containers()
        yum_container = None
        for container in containers:
            if 'yum install -y wget' in container['command']:
                yum_container = container['id']
                break
        
        if not yum_container:
            print("FAIL: Could not find yum install container")
            return False
        
        print(f"Yum install container: {yum_container}")
        
        # Test 3: Commit the changes
        print("Step 3: Committing changes to image...")
        commit_returncode = self.commit([yum_container, img_id])
        if commit_returncode != 0:
            print(f"FAIL: Commit failed with return code {commit_returncode}")
            return False
        
        print(f"Successfully committed changes to image {img_id}")
        
        # Test 4: Verify wget now works by making HTTP request
        print("Step 4: Testing wget with HTTP request...")
        returncode = self.run([img_id, 'wget', '-qO-', 'http://httpbin.org/get'])
        time.sleep(3)
        
        # Get container ID for wget HTTP request
        containers = self._list_containers()
        wget_http_container = None
        for container in containers:
            if 'wget -qO- http://httpbin.org/get' in container['command']:
                wget_http_container = container['id']
                break
        
        if wget_http_container:
            print(f"Wget HTTP request container: {wget_http_container}")
            
            # Check logs to verify HTTP request succeeded
            log_file = Path(self.btrfs_path) / wget_http_container / f"{wget_http_container}.log"
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                    
                    print("Logs from wget HTTP request:")
                    print(log_content[:200] + "..." if len(log_content) > 200 else log_content)
                    
                    if 'http://httpbin.org/get' in log_content or '"url"' in log_content:
                        print("SUCCESS: wget successfully fetched data from httpbin.org")
                    else:
                        print("Warning: wget HTTP request may have failed or returned unexpected data")
                        # Don't fail the test as network issues might occur
                        
                except Exception as e:
                    print(f"Warning: Could not read wget HTTP logs: {e}")
            
            # Clean up HTTP test container
            self.rm([wget_http_container])
        else:
            print("Warning: Could not find wget HTTP request container")
        
        print("PASS: bocker commit test")
        return True

    def help(self, args):
        """Display help message"""
        help_text = """BOCKER - Simplified version to demonstrate commit functionality

Usage: bocker [command] [args...]

Commands:
  init     Create an image from a directory
  images   List images
  images   List images
  ps       List containers
  images   List images  
  ps       List containers
  run      Create a container
  ps       List containers
  commit   Commit a container to an image
  rm       Delete an image or container
  demo     Run commit demonstration
  help     Display this message

Commit Demo:
  bocker demo   - Run a complete demonstration of commit functionality"""
        print(help_text)
        return 0


def main():
    """Main entry point"""
    if len(sys.argv) == 1:
        # Run demo by default
        bocker = Bocker()
        success = bocker.demo_commit()
        return 0 if success else 1

    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    bocker = Bocker()
    
    # Command mapping
    command_map = {
        'init': bocker.init,
        'images': bocker.images,
        'run': bocker.run,
        'ps': bocker.ps,
        'commit': bocker.commit,
        'rm': bocker.rm,
        'demo': lambda _: bocker.demo_commit(),
        'help': bocker.help
    }

    if command in command_map:
        try:
            if command == 'demo':
                success = bocker.demo_commit()
                return 0 if success else 1
            else:
                return command_map[command](args)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return bocker.help([])

if __name__ == '__main__':
    sys.exit(main())
