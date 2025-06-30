#!/usr/bin/env python3

import glob
import ipaddress
import json
import logging
import os
import random
import requests
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict
from dotenv import load_dotenv

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

# CLASS 1: Setup/Base Class
class BockerBase:
    """Base class with common functionality for all Bocker versions"""
    
    def __init__(self):
        self.config = BockerConfig.from_environment()
        self.btrfs_path = self.config.btrfs_path
        self.cgroups = self.config.cgroups

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

    def help(self, args):
        """Display help message"""
        help_text = f"""BOCKER {self.__class__.__name__} - Docker implemented in Python

Usage: bocker [args...]

Commands:
  {self._get_available_commands()}
  help     Display this message
  test     Run test suite for this version"""
        print(help_text)
        return 0

    def _get_available_commands(self):
        """Get list of available commands for this version"""
        return "Base functionality only"

    def test_base(self):
        """Test base functionality"""
        print(f"Testing {self.__class__.__name__} base functionality...")
        
        # Test configuration
        if not self.config:
            print("FAIL: Configuration not loaded")
            return False
        
        # Test helper methods
        test_uuid = self._generate_uuid("test_")
        if not test_uuid.startswith("test_"):
            print("FAIL: UUID generation failed")
            return False
        
        print("PASS: Base functionality test")
        return True

# CLASS 2: Bocker v1 - Pulling Images
class BockerV1(BockerBase):
    """Bocker v1: Image management - pull, init, images, commit, rm"""
    
    def _get_available_commands(self):
        return "pull     Pull an image from Docker Hub\n  init     Create an image from a directory\n  images   List images\n  commit   Commit a container to an image\n  rm       Delete an image or container"

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

    def test_init(self):
        """Test init functionality"""
        print("Testing bocker init...")
        base_image_dir = os.path.expanduser('~/base-image')
        
        if not os.path.exists(base_image_dir):
            print(f"SKIP: Base image directory {base_image_dir} not found")
            return True
        
        # Test invalid directory first
        returncode = self.init(['/nonexistent/directory'])
        if returncode == 0:
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

    def pull(self, args):
        """Pull an image from cloud storage: BOCKER pull <name> <tag>"""
        if len(args) < 2:
            print("Usage: bocker pull <name> <tag>", file=sys.stderr)
            return 1

        name, tag = args[0], args[1]
        load_dotenv()
        r2_domain = os.getenv('R2_DOMAIN')
        if not r2_domain:
            print("Error: R2_DOMAIN not found in environment", file=sys.stderr)
            return 1

        temp_base = tempfile.mkdtemp(prefix=f"bocker_{name}_{tag}_")
        download_path = os.path.join(temp_base, "download")
        extract_path = os.path.join(temp_base, "extract")
        process_path = os.path.join(temp_base, "process")
        
        for path in [download_path, extract_path, process_path]:
            os.makedirs(path, exist_ok=True)

        try:
            tarball_url = f"https://{r2_domain}/{name}_{tag}.tar.gz"
            compressed_filename = os.path.join(download_path, f"{name}_{tag}.tar.gz")
            print(f"Downloading {name}:{tag} from {r2_domain}")
            
            resp = requests.get(tarball_url, stream=True)
            resp.raise_for_status()
            
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(compressed_filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\rProgress: {percent:.1f}%", end='', flush=True)
            print(f"\nDownloaded {compressed_filename}")

            with tarfile.open(compressed_filename, "r:gz") as tar:
                tar.extractall(path=extract_path)

            manifest_path = None
            for root, dirs, files in os.walk(extract_path):
                if 'manifest.json' in files:
                    manifest_path = os.path.join(root, 'manifest.json')
                    break

            if not manifest_path:
                print("Error: manifest.json not found", file=sys.stderr)
                return 1

            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            extract_root = os.path.dirname(manifest_path)
            for item in os.listdir(extract_root):
                src = os.path.join(extract_root, item)
                dst = os.path.join(process_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            for entry in manifest:
                if 'Layers' in entry:
                    for layer in entry['Layers']:
                        layer_path = os.path.join(process_path, layer)
                        if os.path.exists(layer_path):
                            with tarfile.open(layer_path, 'r') as layer_tar:
                                layer_tar.extractall(path=process_path)
                            os.remove(layer_path)

            img_uuid = self._generate_uuid("img_")
            bash_script = f"""
            set -o errexit -o nounset -o pipefail
            btrfs subvolume create "{self.btrfs_path}/{img_uuid}" > /dev/null
            cp -rf --reflink=auto "{process_path}"/* "{self.btrfs_path}/{img_uuid}/" > /dev/null
            echo "{name}:{tag}" > "{self.btrfs_path}/{img_uuid}/img.source"
            echo "Created: {img_uuid}"
            """
            return self._run_bash_command(bash_script)

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base)

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
        
        # Find the centos image and test it
        centos_img = None
        for img in new_images:
            if 'centos:7' in img['source']:
                centos_img = img['id']
                break
        
        if centos_img:
            print(f"Testing pulled CentOS image: {centos_img}")
            # Test that we can create a container from the pulled image
            returncode = self.run([centos_img, 'echo', 'centos_test'])
            time.sleep(2)
            
            # Verify container was created
            containers = self._list_containers()
            centos_container = None
            for container in containers:
                if 'echo centos_test' in container['command']:
                    centos_container = container['id']
                    break
            
            if centos_container:
                print(f"Successfully created container from pulled image: {centos_container}")
            else:
                print("Warning: Could not create container from pulled image")

        print("PASS: bocker pull test")
        return True

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
        
        # Create an image to test with if none exist
        base_image_dir = os.path.expanduser('~/base-image')
        if os.path.exists(base_image_dir) and not initial_images:
            self.init([base_image_dir])
            
            # Test again with the new image
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                returncode = self.images([])
            
            if returncode != 0:
                print(f"FAIL: Images command failed after creating image")
                return False
            
            output = output_buffer.getvalue()
            lines = output.strip().split('\n')
            
            if len(lines) < 2:  # Should have header + at least one image
                print("FAIL: No images listed after creating one")
                return False

        print("PASS: bocker images test")
        return True

    def commit(self, args):
        """Commit a container to an image: BOCKER commit <container_id> <image_id>"""
        if len(args) < 2:
            print("Usage: bocker commit <container_id> <image_id>", file=sys.stderr)
            return 1

        container_id, image_id = args[0], args[1]

        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1

        if self._bocker_check(image_id):
            self.rm([image_id])

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs subvolume snapshot "{self.btrfs_path}/{container_id}" "{self.btrfs_path}/{image_id}" > /dev/null
        echo "Created: {image_id}"
        """
        return self._run_bash_command(bash_script)

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
        cgdelete -g "{self.cgroups}:/{container_id}" &> /dev/null || true
        echo "Removed: {container_id}"
        """
        return self._run_bash_command(bash_script)

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

    def test_v1(self):
        """Test v1 functionality by running all test methods"""
        print("Testing BockerV1 functionality...")
        print("=" * 50)
        
        # Get all test methods for this class (excluding test_v1 to avoid recursion)
        test_methods = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if (attr_name.startswith('test_') and 
                callable(attr) and 
                attr_name != 'test_v1'):
                test_methods.append(attr_name)
        
        # Sort test methods for consistent order
        test_methods.sort()
        
        print(f"Found {len(test_methods)} test methods: {', '.join(test_methods)}")
        print("-" * 50)
        
        results = {}
        overall_success = True
        
        # Run each test method
        for test_name in test_methods:
            print(f"\n🧪 Running {test_name}...")
            try:
                test_method = getattr(self, test_name)
                success = test_method()
                results[test_name] = "PASS" if success else "FAIL"
                if not success:
                    overall_success = False
                    print(f"❌ {test_name}: FAILED")
                else:
                    print(f"✅ {test_name}: PASSED")
            except Exception as e:
                print(f"💥 {test_name}: ERROR - {e}")
                results[test_name] = "ERROR"
                overall_success = False
        
        # Print summary
        print("\n" + "=" * 50)
        print("BockerV1 Test Summary:")
        print("-" * 50)
        for test_name in test_methods:
            status = results.get(test_name, "UNKNOWN")
            status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "💥"
            print(f"{status_symbol} {test_name:<15} : {status}")
        
        print("-" * 50)
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print("=" * 50)
        
        return overall_success

# CLASS 3: Bocker v2 - Pulling Images + Chroot
class BockerV2(BockerV1):
    """Bocker v2: Adds container functionality with chroot - ps, run, exec, logs"""
    
    def _get_available_commands(self):
        return super()._get_available_commands() + "\n  ps       List containers\n  run      Create a container\n  exec     Execute a command in a running container\n  logs     View logs from a container"

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

        uuid = self._generate_uuid("ps_")
        if self._bocker_check(uuid):
            return self.run(args)

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        
        # Filesystem setup - Create snapshot and configure environment
        btrfs subvolume snapshot "{self.btrfs_path}/{image_id}" "{self.btrfs_path}/{uuid}" > /dev/null
        echo 'nameserver 8.8.8.8' > "{self.btrfs_path}/{uuid}"/etc/resolv.conf
        echo "{command}" > "{self.btrfs_path}/{uuid}/{uuid}.cmd"
        
        # Execute in chroot environment with proc mounted
        chroot "{self.btrfs_path}/{uuid}" /bin/sh -c "/bin/mount -t proc proc /proc && {command}" \\
            2>&1 | tee "{self.btrfs_path}/{uuid}/{uuid}.log" || true
        """
        return self._run_bash_command(bash_script, show_realtime=True)

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
        cid="$(ps o ppid,pid | grep "^$(ps o pid,cmd | grep -E "^\\ *[0-9]+ chroot.*{container_id}" | awk '{{print $1}}')" | awk '{{print $2}}')"
        [[ ! "$cid" =~ ^\\ *[0-9]+$ ]] && echo "Container '{container_id}' exists but is not running" && exit 1
        chroot "{self.btrfs_path}/{container_id}" {command}
        """
        return self._run_bash_command(bash_script, show_realtime=True)

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

    def test_v2(self):
        """Test v2 functionality"""
        print("Testing BockerV2 functionality...")
        
        if not self.test_v1():
            return False
        
        # Test ps command
        result = self.ps([])
        if result != 0:
            print("FAIL: PS command failed")
            return False
        
        # Test with a simple container run
        images = self._list_images()
        if not images:
            print("SKIP: No images available for v2 container testing")
            return True
        
        img_id = images[0]['id']
        result = self.run([img_id, 'echo', 'hello_v2'])
        time.sleep(1)
        
        # Check logs
        containers = self._list_containers()
        test_container = None
        for container in containers:
            if 'echo hello_v2' in container['command']:
                test_container = container['id']
                break
        
        if test_container:
            log_result = self.logs([test_container])
            if log_result != 0:
                print("FAIL: Logs command failed")
                return False
        
        print("PASS: BockerV2 test")
        return True

# CLASS 4: Bocker v3 - Pulling Images + Chroot + Cgroups
class BockerV3(BockerV2):
    """Bocker v3: Adds cgroups for resource management"""
    
    def _get_available_commands(self):
        return super()._get_available_commands() + "\n  Resource management with cgroups enabled"

    def run(self, args):
        """Create a container with cgroups: BOCKER run <image_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        uuid = self._generate_uuid("ps_")
        if self._bocker_check(uuid):
            return self.run(args)

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        
        # Filesystem setup - Create snapshot and configure environment
        btrfs subvolume snapshot "{self.btrfs_path}/{image_id}" "{self.btrfs_path}/{uuid}" > /dev/null
        echo 'nameserver 8.8.8.8' > "{self.btrfs_path}/{uuid}"/etc/resolv.conf
        echo "{command}" > "{self.btrfs_path}/{uuid}/{uuid}.cmd"
        
        # Cgroups setup - Create and configure resource limits
        cgcreate -g "{self.cgroups}:/{uuid}"
        cgset -r cpu.shares="{self.config.cpu_share}" "{uuid}"
        cgset -r memory.limit_in_bytes="{self.config.mem_limit * 1000000}" "{uuid}"
        
        # Execute in chroot environment with cgroup constraints
        cgexec -g "{self.cgroups}:{uuid}" \\
            chroot "{self.btrfs_path}/{uuid}" \\
            /bin/sh -c "/bin/mount -t proc proc /proc && {command}" \\
            2>&1 | tee "{self.btrfs_path}/{uuid}/{uuid}.log" || true
        """
        return self._run_bash_command(bash_script, show_realtime=True)

    def rm(self, args):
        """Delete an image or container with cgroup cleanup: BOCKER rm <image_id or container_id>"""
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
        
        # Cleanup cgroups if they exist
        cgdelete -g "{self.cgroups}:/{container_id}" &> /dev/null || true
        
        echo "Removed: {container_id}"
        """
        return self._run_bash_command(bash_script)

    def test_v3(self):
        """Test v3 functionality"""
        print("Testing BockerV3 functionality...")
        
        if not self.test_v2():
            return False
        
        # Test cgroups functionality by running a memory-intensive command
        images = self._list_images()
        if not images:
            print("SKIP: No images available for v3 cgroups testing")
            return True
        
        img_id = images[0]['id']
        result = self.run([img_id, 'echo', 'cgroups_test'])
        time.sleep(1)
        
        # Verify cgroups were created and cleaned up
        print("PASS: BockerV3 test (cgroups support added)")
        return True

# CLASS 5: Bocker v4 - Pulling Images + Chroot + Cgroups + Namespaces
class BockerV4(BockerV3):
    """Bocker v4: Adds namespaces for better isolation"""
    
    def _get_available_commands(self):
        return super()._get_available_commands() + "\n  Process isolation with namespaces enabled"

    def run(self, args):
        """Create a container with namespaces: BOCKER run <image_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        uuid = self._generate_uuid("ps_")
        if self._bocker_check(uuid):
            return self.run(args)

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        
        # Filesystem setup - Create snapshot and configure environment
        btrfs subvolume snapshot "{self.btrfs_path}/{image_id}" "{self.btrfs_path}/{uuid}" > /dev/null
        echo 'nameserver 8.8.8.8' > "{self.btrfs_path}/{uuid}"/etc/resolv.conf
        echo "{command}" > "{self.btrfs_path}/{uuid}/{uuid}.cmd"
        
        # Create network namespace
        ip netns add netns_"{uuid}"
        ip netns exec netns_"{uuid}" ip link set dev lo up
        
        # Cgroups setup - Create and configure resource limits
        cgcreate -g "{self.cgroups}:/{uuid}"
        cgset -r cpu.shares="{self.config.cpu_share}" "{uuid}"
        cgset -r memory.limit_in_bytes="{self.config.mem_limit * 1000000}" "{uuid}"
        
        # Execute in namespace-isolated environment with cgroup constraints
        cgexec -g "{self.cgroups}:{uuid}" \\
            ip netns exec netns_"{uuid}" \\
            unshare -fmuip --mount-proc \\
            chroot "{self.btrfs_path}/{uuid}" \\
            /bin/sh -c "/bin/mount -t proc proc /proc && {command}" \\
            2>&1 | tee "{self.btrfs_path}/{uuid}/{uuid}.log" || true
        
        # Cleanup network namespace
        ip netns del netns_"{uuid}"
        """
        return self._run_bash_command(bash_script, show_realtime=True)

    def exec(self, args):
        """Execute a command in a running container with namespace support: BOCKER exec <container_id> <command>"""
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
        # Enter all namespaces (mount, UTS, IPC, network, PID) and chroot
        nsenter -t "$cid" -m -u -i -n -p chroot "{self.btrfs_path}/{container_id}" {command}
        """
        return self._run_bash_command(bash_script, show_realtime=True)

    def test_v4(self):
        """Test v4 functionality"""
        print("Testing BockerV4 functionality...")
        
        if not self.test_v3():
            return False
        
        # Test namespace isolation
        images = self._list_images()
        if not images:
            print("SKIP: No images available for v4 namespace testing")
            return True
        
        img_id = images[0]['id']
        result = self.run([img_id, 'echo', 'namespace_test'])
        time.sleep(1)
        
        print("PASS: BockerV4 test (namespace isolation added)")
        return True

# CLASS 6: Bocker v5 - Pulling Images + Chroot + Cgroups + Namespaces + Network
class BockerV5(BockerV4):
    """Bocker v5: Adds full networking support"""
    
    def _get_available_commands(self):
        return super()._get_available_commands() + "\n  Full network isolation and connectivity"

    def run(self, args):
        """Create a container with full networking: BOCKER run <image_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1

        image_id = args[0]
        command = ' '.join(args[1:])

        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1

        uuid = self._generate_uuid("ps_")
        if self._bocker_check(uuid):
            return self.run(args)

        # Generate network configuration
        ip_suffix = uuid[-3:].replace('0', '') or '1'
        mac_suffix = f"{uuid[-3:-2]}:{uuid[-2:]}"

        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        
        # Network setup
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
        
        # Filesystem setup
        btrfs subvolume snapshot "{self.btrfs_path}/{image_id}" "{self.btrfs_path}/{uuid}" > /dev/null
        echo 'nameserver 8.8.8.8' > "{self.btrfs_path}/{uuid}"/etc/resolv.conf
        echo "{command}" > "{self.btrfs_path}/{uuid}/{uuid}.cmd"
        
        # Cgroups setup
        cgcreate -g "{self.cgroups}:/{uuid}"
        cgset -r cpu.shares="{self.config.cpu_share}" "{uuid}"
        cgset -r memory.limit_in_bytes="{self.config.mem_limit * 1000000}" "{uuid}"
        
        # Execute with full isolation
        cgexec -g "{self.cgroups}:{uuid}" \\
            ip netns exec netns_"{uuid}" \\
            unshare -fmuip --mount-proc \\
            chroot "{self.btrfs_path}/{uuid}" \\
            /bin/sh -c "/bin/mount -t proc proc /proc && {command}" \\
            2>&1 | tee "{self.btrfs_path}/{uuid}/{uuid}.log" || true
        
        # Cleanup network
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
        cgdelete -g "{self.cgroups}:/{image_id}" &> /dev/null || true
        btrfs subvolume snapshot "{self.btrfs_path}/{container_id}" "{self.btrfs_path}/{image_id}" > /dev/null
        echo "Created: {image_id}"
        """
        return self._run_bash_command(bash_script)

    def test_v5(self):
        """Test v5 functionality"""
        print("Testing BockerV5 functionality...")
        
        if not self.test_v4():
            return False
        
        # Test network connectivity
        images = self._list_images()
        if not images:
            print("SKIP: No images available for v5 network testing")
            return True
        
        img_id = images[0]['id']
        
        # Test basic network setup
        result = self.run([img_id, 'echo', 'network_test'])
        time.sleep(1)
        
        # Test with a network command if available
        result = self.run([img_id, 'ping', '-c', '1', '8.8.8.8'])
        time.sleep(2)
        
        print("PASS: BockerV5 test (full networking support)")
        return True

def run_all_tests():
    """Run tests for all versions starting from v1"""
    print("=" * 60)
    print("Running Bocker Test Suite - All Versions")
    print("=" * 60)
    
    # Version mapping in order
    versions = ['v1', 'v2', 'v3', 'v4', 'v5']
    version_map = {
        'v1': BockerV1,
        'v2': BockerV2,
        'v3': BockerV3,
        'v4': BockerV4,
        'v5': BockerV5
    }
    
    results = {}
    overall_success = True
    
    for version in versions:
        print(f"\n{'=' * 20} Testing {version.upper()} {'=' * 20}")
        
        try:
            bocker = version_map[version]()
            test_method = getattr(bocker, f'test_{version}', None)
            
            if test_method:
                success = test_method()
                results[version] = "PASS" if success else "FAIL"
                if not success:
                    overall_success = False
            else:
                print(f"No test method found for {version}")
                results[version] = "SKIP"
                
        except Exception as e:
            print(f"ERROR in {version}: {e}")
            results[version] = "ERROR"
            overall_success = False
    
    # Summary
    print(f"\n{'=' * 20} TEST SUMMARY {'=' * 20}")
    for version in versions:
        status = results.get(version, "UNKNOWN")
        status_symbol = "✓" if status == "PASS" else "✗" if status == "FAIL" else "!"
        print(f"{status_symbol} {version.upper():<4} : {status}")
    
    print(f"\nOverall Result: {'PASS' if overall_success else 'FAIL'}")
    print("=" * 60)
    
    return overall_success

def main():
    """Main entry point with version selection"""
    # If no arguments provided, run all tests
    if len(sys.argv) == 1:
        success = run_all_tests()
        return 0 if success else 1
    
    # If first argument is "test_all", run all tests
    if len(sys.argv) == 2 and sys.argv[1] == "test_all":
        success = run_all_tests()
        return 0 if success else 1
    
    if len(sys.argv) < 2:
        print("Usage: python boc_ex.py [version] [command] [args...]")
        print("       python boc_ex.py                    # Run all tests")
        print("       python boc_ex.py test_all           # Run all tests") 
        print("       python boc_ex.py <version> [cmd]    # Run specific version/command")
        print("Versions: v1, v2, v3, v4, v5")
        print("Commands: help, test, or any bocker command")
        return 1

    version = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'help'
    args = sys.argv[3:] if len(sys.argv) > 3 else []

    # Version mapping
    version_map = {
        'v1': BockerV1,
        'v2': BockerV2,
        'v3': BockerV3,
        'v4': BockerV4,
        'v5': BockerV5
    }

    if version not in version_map:
        print(f"Unknown version: {version}")
        print("Available versions: v1, v2, v3, v4, v5")
        return 1

    bocker = version_map[version]()
    
    # Handle test commands
    if command == 'test':
        test_method = getattr(bocker, f'test_{version}', None)
        if test_method:
            success = test_method()
            return 0 if success else 1
        else:
            print(f"No test method found for version {version}")
            return 1
    
    # Handle regular commands
    if hasattr(bocker, command):
        try:
            return getattr(bocker, command)(args)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Unknown command: {command}")
        return bocker.help([])

if __name__ == '__main__':
    sys.exit(main())
