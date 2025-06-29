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
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, List, Dict

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

class Bocker:
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
        cgcreate -g "{self.cgroups}:/{uuid}"
        cgset -r cpu.shares="{self.config.cpu_share}" "{uuid}"
        cgset -r memory.limit_in_bytes="{self.config.mem_limit * 1000000}" "{uuid}"
        
        cgexec -g "{self.cgroups}:{uuid}" \\
        ip netns exec netns_"{uuid}" \\
        unshare -fmuip --mount-proc \\
        chroot "{self.btrfs_path}/{uuid}" \\
        /bin/sh -c "/bin/mount -t proc proc /proc && {command}" \\
        2>&1 | tee "{self.btrfs_path}/{uuid}/{uuid}.log" || true

        ip link del dev veth0_"{uuid}"
        ip netns del netns_"{uuid}"
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
        cid="$(ps o ppid,pid | grep "^$(ps o pid,cmd | grep -E "^\\ *[0-9]+ unshare.*{container_id}" | awk '{{print $1}}')" | awk '{{print $2}}')"
        [[ ! "$cid" =~ ^\\ *[0-9]+$ ]] && echo "Container '{container_id}' exists but is not running" && exit 1
        nsenter -t "$cid" -m -u -i -n -p chroot "{self.btrfs_path}/{container_id}" {command}
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

    def help(self, args):
        """Display help message"""
        help_text = """BOCKER - Docker implemented in around 100 lines of bash

Usage: bocker [args...]

Commands:
  pull     Pull an image from Docker Hub
  init     Create an image from a directory
  rm       Delete an image or container
  images   List images
  ps       List containers
  run      Create a container
  exec     Execute a command in a running container
  logs     View logs from a container
  commit   Commit a container to an image
  test     Run comprehensive test suite
  help     Display this message"""
        print(help_text)
        return 0


class BockerTester:
    def __init__(self):
        self.base_image_dir = os.path.expanduser('~/base-image')
        self.bocker = Bocker()

    def run_bocker_command(self, args):
        """Run bocker command and return result"""
        try:
            command = args[0] if args else 'help'
            command_args = args[1:] if len(args) > 1 else []
            
            command_map = {
                'pull': self.bocker.pull,
                'init': self.bocker.init,
                'rm': self.bocker.rm,
                'images': self.bocker.images,
                'ps': self.bocker.ps,
                'run': self.bocker.run,
                'exec': self.bocker.exec,
                'logs': self.bocker.logs,
                'commit': self.bocker.commit,
                'help': self.bocker.help
            }
            
            if command in command_map:
                import io
                from contextlib import redirect_stdout, redirect_stderr
                
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    returncode = command_map[command](command_args)
                
                return returncode, stdout_capture.getvalue(), stderr_capture.getvalue()
            else:
                return 1, "", f"Unknown command: {command}"
                
        except Exception as e:
            return 1, "", str(e)

    def bocker_run_test(self, image_id, command, expected_output):
        """Test bocker container runs and check their output"""
        returncode, stdout, stderr = self.run_bocker_command(['run', image_id, command])
        time.sleep(3)

        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        if ps_returncode != 0:
            return False

        container_id = None
        for line in ps_stdout.split('\n'):
            if command in line:
                container_id = line.split()[0]
                break

        if not container_id:
            return False

        logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
        if logs_returncode != 0:
            return False

        return expected_output in logs_stdout

    def test_init(self):
        """Test bocker init functionality"""
        print("Testing bocker init...")
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        
        if returncode != 0:
            print(f"FAIL: Init command failed with return code {returncode}")
            print(f"stderr: {stderr}")
            return False

        if not stdout.startswith('Created: img_'):
            print(f"FAIL: Expected 'Created: img_*' but got: {stdout}")
            return False

        print("PASS: bocker init test")
        return True

    def test_images(self):
        """Test bocker images functionality"""
        print("Testing bocker images...")
        returncode, stdout, stderr = self.run_bocker_command(['images'])
        
        if returncode != 0:
            print(f"FAIL: Images command failed with return code {returncode}")
            return False

        lines = stdout.strip().split('\n')
        if not lines or lines[0] != 'IMAGE_ID\t\tSOURCE':
            print(f"FAIL: Expected header 'IMAGE_ID\\t\\tSOURCE' but got: {lines[0] if lines else 'empty'}")
            return False

        print("PASS: bocker images test")
        return True

    def test_ps(self):
        """Test bocker ps functionality"""
        print("Testing bocker ps...")
        returncode, stdout, stderr = self.run_bocker_command(['ps'])
        
        if returncode != 0:
            print(f"FAIL: PS command failed with return code {returncode}")
            return False

        lines = stdout.strip().split('\n')
        if not lines or lines[0] != 'CONTAINER_ID\t\tCOMMAND':
            print(f"FAIL: Expected header 'CONTAINER_ID\\t\\tCOMMAND' but got: {lines[0] if lines else 'empty'}")
            return False

        print("PASS: bocker ps test")
        return True

    def test_run(self):
        """Test bocker run functionality with comprehensive tests"""
        print("Testing bocker run...")
        
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        if returncode != 0:
            print(f"FAIL: Could not create test image: {stderr}")
            return False

        img_id = stdout.strip().split()[-1]
        print(f"Created image with ID: {img_id}")
        time.sleep(4)

        returncode, stdout, stderr = self.run_bocker_command(['images'])
        if returncode != 0 or img_id not in stdout:
            print("FAIL: Image not found in bocker images list")
            return False

        test_cases = [
            ('echo foo', 'foo', "Test 1: echo foo"),
            ('uname', 'Linux', "Test 2: uname"),
            ('cat /proc/self/stat', '1 (cat)', "Test 3: process isolation check")
        ]

        for command, expected, description in test_cases:
            print(f"Running {description}")
            if not self.bocker_run_test(img_id, command, expected):
                print(f"FAIL: {description} failed")
                return False
            print(f"{description} completed successfully")

        print("PASS: bocker run test")
        return True

    def test_rm(self):
        """Test bocker rm functionality"""
        print("Testing bocker rm...")
        
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        if returncode != 0:
            print(f"FAIL: Could not create test image: {stderr}")
            return False

        img_id = stdout.strip().split()[-1]
        
        cmd = f"echo {random.randint(1000, 9999)}"
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, cmd])

        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if cmd.split()[-1] in line:
                container_id = line.split()[0]
                break

        if not container_id:
            print("FAIL: Could not find container ID")
            return False

        rm_img_returncode, rm_img_stdout, rm_img_stderr = self.run_bocker_command(['rm', img_id])
        rm_ps_returncode, rm_ps_stdout, rm_ps_stderr = self.run_bocker_command(['rm', container_id])

        images_returncode, images_stdout, images_stderr = self.run_bocker_command(['images'])
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])

        if img_id in images_stdout or container_id in ps_stdout:
            print("FAIL: Image or container still found after removal")
            return False

        print("PASS: bocker rm test")
        return True

    def test_pull(self):
        """Test bocker pull functionality"""
        print("Testing bocker pull...")
        
        print("Pulling CentOS 7...")
        returncode, stdout, stderr = self.run_bocker_command(['pull', 'centos', '7'])
        if returncode != 0:
            print(f"FAIL: CentOS pull failed: {stderr}")
            return False

        centos_img = stdout.strip().split()[-1]
        returncode, stdout, stderr = self.run_bocker_command(['run', centos_img, 'cat', '/etc/redhat-release'])

        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if 'cat /etc/redhat-release' in line:
                container_id = line.split()[0]
                break

        if container_id:
            logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
            self.run_bocker_command(['rm', container_id])
            if 'CentOS Linux release 7' not in logs_stdout:
                print(f"FAIL: Expected CentOS release info, got: {logs_stdout}")
                return False

        print("PASS: bocker pull test")
        return True

    def test_commit(self):
        """Test bocker commit functionality"""
        print("Testing bocker commit...")
        
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        if returncode != 0:
            print(f"FAIL: Could not create test image: {stderr}")
            return False

        img_id = stdout.strip().split()[-1]
        print(f"Created image: {img_id}")
        time.sleep(1)

        images_returncode, images_stdout, images_stderr = self.run_bocker_command(['images'])
        if img_id not in images_stdout:
            print(f"Error: Image {img_id} not found in image list")
            return False

        print("Testing wget command (should fail)...")
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, 'wget'])

        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if 'wget' in line:
                container_id = line.split()[0]
                break

        if container_id:
            logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
            self.run_bocker_command(['rm', container_id])

        print("Installing wget using yum...")
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, 'yum', 'install', '-y', 'wget'])
        if returncode == 0:
            ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
            container_id = None
            for line in ps_stdout.split('\n'):
                if 'yum install -y wget' in line:
                    container_id = line.split()[0]
                    break

            if container_id:
                commit_returncode, commit_stdout, commit_stderr = self.run_bocker_command(['commit', container_id, img_id])
                if commit_returncode != 0:
                    print(f"FAIL: Commit failed: {commit_stderr}")
                    return False

        print("PASS: bocker commit test")
        return True

    def cleanup(self):
        """Clean up test artifacts"""
        print("Cleaning up test artifacts...")
        
        for prefix in ['img_', 'ps_']:
            items_returncode, items_stdout, items_stderr = self.run_bocker_command(['images' if prefix == 'img_' else 'ps'])
            if items_returncode == 0:
                for line in items_stdout.split('\n'):
                    if line.startswith(prefix):
                        item_id = line.split()[0]
                        self.run_bocker_command(['rm', item_id])

    def run_all_tests(self):
        """Run all test cases"""
        print("=" * 60)
        print("BOCKER COMPREHENSIVE TEST SUITE")
        print("=" * 60)

        tests = [
            ('Init Test', self.test_init),
            ('Images Test', self.test_images),
            ('PS Test', self.test_ps),
            ('Run Test', self.test_run),
            ('RM Test', self.test_rm),
            ('Pull Test', self.test_pull),
            ('Commit Test', self.test_commit),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            print(f"\n{'-' * 40}")
            print(f"Running {test_name}")
            print(f"{'-' * 40}")
            try:
                if test_func():
                    passed += 1
                    print(f"✓ {test_name} PASSED")
                else:
                    failed += 1
                    print(f"✗ {test_name} FAILED")
            except Exception as e:
                failed += 1
                print(f"✗ {test_name} FAILED with exception: {e}")
            
            time.sleep(2)

        print(f"\n{'=' * 60}")
        print(f"TEST RESULTS: {passed} passed, {failed} failed")
        print(f"{'=' * 60}")

        self.cleanup()
        return failed == 0


def main():
    """Main entry point - runs tests by default, or specific commands if provided"""
    # If no arguments provided, run tests automatically
    if len(sys.argv) == 1:
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print(f"Error: Base image directory {base_image_dir} not found")
            print("Please create a base image directory with a minimal Linux filesystem")
            return 1
        
        tester = BockerTester()
        success = tester.run_all_tests()
        return 0 if success else 1

    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    # Explicit test command
    if command == 'test':
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print(f"Error: Base image directory {base_image_dir} not found")
            print("Please create a base image directory with a minimal Linux filesystem")
            return 1
        
        tester = BockerTester()
        success = tester.run_all_tests()
        return 0 if success else 1
    
    # Regular bocker commands
    bocker = Bocker()
    command_map = {
        'pull': bocker.pull,
        'init': bocker.init,
        'rm': bocker.rm,
        'images': bocker.images,
        'ps': bocker.ps,
        'run': bocker.run,
        'exec': bocker.exec,
        'logs': bocker.logs,
        'commit': bocker.commit,
        'help': bocker.help
    }

    if command in command_map:
        try:
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

