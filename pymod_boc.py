#!/usr/bin/env python3
import subprocess
import sys
import os
import tempfile
import uuid
import json
import shutil
import time
import random
import logging
import ipaddress
import glob
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict
from contextlib import contextmanager

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

    def _process_docker_manifest(self, manifest_path):
        """Process Docker manifest using Python JSON instead of jq"""
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            layers = []
            configs = []
            
            for item in manifest:
                if 'Layers' in item:
                    layers.extend(item['Layers'])
                if 'Config' in item:
                    configs.append(item['Config'])
            
            return layers, configs
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            return [], []

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
        import os
        import sys
        import requests
        import tarfile
        import json
        import tempfile
        import shutil
        import uuid
        from dotenv import load_dotenv
        
        if len(args) < 2:
            print("Usage: bocker pull <name> <tag>", file=sys.stderr)
            return 1
        
        name, tag = args[0], args[1]
        
        # Load environment variables
        load_dotenv()
        r2_domain = os.getenv('R2_DOMAIN')
        
        if not r2_domain:
            print("Error: R2_DOMAIN not found in environment", file=sys.stderr)
            return 1
        
        # Create temporary directories
        temp_base = tempfile.mkdtemp(prefix=f"bocker_{name}_{tag}_")
        download_path = os.path.join(temp_base, "download")
        extract_path = os.path.join(temp_base, "extract")
        process_path = os.path.join(temp_base, "process")
        
        os.makedirs(download_path, exist_ok=True)
        os.makedirs(extract_path, exist_ok=True)
        os.makedirs(process_path, exist_ok=True)
        
        try:
            # Step 1: Download the image
            tarball_url = f"https://{r2_domain}/{name}_{tag}.tar.gz"
            compressed_filename = os.path.join(download_path, f"{name}_{tag}.tar.gz")
            
            print(f"Downloading {name}:{tag} from {r2_domain}")
            print(f"URL: {tarball_url}")
            
            resp = requests.get(tarball_url, stream=True)
            resp.raise_for_status()
            
            # Download with progress
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
            
            # Step 2: Extract the tar.gz
            print("Extracting Docker image archive...")
            with tarfile.open(compressed_filename, "r:gz") as tar:
                tar.extractall(path=extract_path)
            
            print("✓ Archive extraction complete!")
            
            # Step 3: Process Docker image format
            print("Processing Docker image layers...")
            
            # Look for manifest.json in extracted content
            manifest_path = None
            for root, dirs, files in os.walk(extract_path):
                if 'manifest.json' in files:
                    manifest_path = os.path.join(root, 'manifest.json')
                    break
            
            if not manifest_path:
                print("Error: manifest.json not found in extracted image", file=sys.stderr)
                return 1
            
            # Read manifest
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Copy all files to process directory first
            extract_root = os.path.dirname(manifest_path)
            for item in os.listdir(extract_root):
                src = os.path.join(extract_root, item)
                dst = os.path.join(process_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            
            # Process layers
            for entry in manifest:
                if 'Layers' in entry:
                    for layer in entry['Layers']:
                        layer_path = os.path.join(process_path, layer)
                        if os.path.exists(layer_path):
                            print(f"Extracting layer: {layer}")
                            with tarfile.open(layer_path, 'r') as layer_tar:
                                layer_tar.extractall(path=process_path)
                            # Remove the layer tar after extraction
                            os.remove(layer_path)
                
                # Remove config files
                if 'Config' in entry:
                    config_path = os.path.join(process_path, entry['Config'])
                    if os.path.exists(config_path):
                        os.remove(config_path)
            
            # Remove repositories file if it exists
            repositories_path = os.path.join(process_path, 'repositories')
            if os.path.exists(repositories_path):
                os.remove(repositories_path)
            
            # Remove manifest.json as it's no longer needed
            process_manifest_path = os.path.join(process_path, 'manifest.json')
            if os.path.exists(process_manifest_path):
                os.remove(process_manifest_path)
            
            # Add image source information
            with open(os.path.join(process_path, 'img.source'), 'w') as f:
                f.write(f"{name}:{tag}\n")
            
            print("✓ Layer processing complete!")
            
            # Step 4: Create bocker image using btrfs
            print("Creating bocker image...")
            
            # Generate unique image ID
            img_uuid = f"img_{uuid.uuid4().hex[:8]}"
            
            bash_script = f"""
            set -o errexit -o nounset -o pipefail
            btrfs_path='{self.btrfs_path}'
            process_path='{process_path}'
            img_uuid='{img_uuid}'
            
            function bocker_check() {{
                btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
            }}
            
            # Check if image already exists
            if [[ "$(bocker_check "$img_uuid")" == 0 ]]; then
                echo "Image UUID conflict, regenerating..."
                img_uuid="img_$(shuf -i 42002-42254 -n 1)"
            fi
            
            # Create btrfs subvolume
            echo "Creating btrfs subvolume: $img_uuid"
            btrfs subvolume create "$btrfs_path/$img_uuid" > /dev/null
            
            # Copy processed image content
            echo "Copying image content..."
            cp -rf --reflink=auto "$process_path"/* "$btrfs_path/$img_uuid/" > /dev/null
            
            echo "Created: $img_uuid"
            echo "Image {name}:{tag} successfully pulled and stored as $img_uuid"
            """
            
            result = self._run_bash_command(bash_script, show_realtime=True)
            
            print("✓ Bocker image creation complete!")
            return result
            
        except requests.RequestException as e:
            print(f"Failed to download: {e}", file=sys.stderr)
            return 1
        except tarfile.TarError as e:
            print(f"Failed to extract: {e}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as e:
            print(f"Failed to parse manifest.json: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1
        finally:
            # Clean up all temporary directories
            if os.path.exists(temp_base):
                print(f"Cleaning up temporary files...")
                shutil.rmtree(temp_base)
                print("✓ Cleanup complete!")
    
    def init(self, args):
        """Create an image from a directory: BOCKER init <directory>"""
        if len(args) < 1:
            print("Usage: bocker init <directory>", file=sys.stderr)
            return 1
        
        directory = args[0]
        
        # Validate directory exists using Python
        if not self._directory_exists(directory):
            print(f"No directory named '{directory}' exists", file=sys.stderr)
            return 1
        
        # Generate UUID using Python
        uuid = self._generate_uuid("img_")
        
        # Check if UUID conflicts using Python
        if self._bocker_check(uuid):
            print("UUID conflict, retrying...", file=sys.stderr)
            return self.init(args)
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        uuid='{uuid}'
        directory='{directory}'
        
        btrfs subvolume create "$btrfs_path/$uuid" > /dev/null
        cp -rf --reflink=auto "$directory"/* "$btrfs_path/$uuid" > /dev/null
        [[ ! -f "$btrfs_path/$uuid"/img.source ]] && echo "$directory" > "$btrfs_path/$uuid"/img.source
        echo "Created: $uuid"
        """
        return self._run_bash_command(bash_script)
    
    def rm(self, args):
        """Delete an image or container: BOCKER rm <image_id or container_id>"""
        if len(args) < 1:
            print("Usage: bocker rm <image_id or container_id>", file=sys.stderr)
            return 1
        
        container_id = args[0]
        
        # Validate container exists using Python
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        cgroups='{self.cgroups}'
        container_id='{container_id}'
        
        btrfs subvolume delete "$btrfs_path/$container_id" > /dev/null
        cgdelete -g "$cgroups:/$container_id" &> /dev/null || true
        echo "Removed: $container_id"
        """
        return self._run_bash_command(bash_script)
    
    def images(self, args):
        """List images: BOCKER images"""
        # Use Python to list images instead of bash for loop
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
        # Use Python to list containers instead of bash for loop
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
        
        # Validate image exists using Python
        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1
        
        # Validate command is not empty using Python
        if not command.strip():
            print("Error: Command cannot be empty", file=sys.stderr)
            return 1
        
        # Generate UUID using Python
        uuid = self._generate_uuid("ps_")
        
        # Check UUID conflict using Python
        if self._bocker_check(uuid):
            print("UUID conflict, retrying...", file=sys.stderr)
            return self.run(args)
        
        # Calculate IP and MAC using Python
        ip_suffix = uuid[-3:].replace('0', '') or '1'
        mac_suffix = f"{uuid[-3:-2]}:{uuid[-2:]}"
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail; shopt -s nullglob
        btrfs_path='{self.btrfs_path}'
        cgroups='{self.cgroups}'
        uuid='{uuid}'
        image_id='{image_id}'
        cmd='{command}'
        ip='{ip_suffix}'
        mac='{mac_suffix}'
        
        # Network setup
        ip link add dev veth0_"$uuid" type veth peer name veth1_"$uuid"
        ip link set dev veth0_"$uuid" up
        ip link set veth0_"$uuid" master bridge0
        ip netns add netns_"$uuid"
        ip link set veth1_"$uuid" netns netns_"$uuid"
        ip netns exec netns_"$uuid" ip link set dev lo up
        ip netns exec netns_"$uuid" ip link set veth1_"$uuid" address 02:42:ac:11:00"$mac"
        ip netns exec netns_"$uuid" ip addr add 10.0.0."$ip"/24 dev veth1_"$uuid"
        ip netns exec netns_"$uuid" ip link set dev veth1_"$uuid" up
        ip netns exec netns_"$uuid" ip route add default via 10.0.0.1
        
        # Filesystem setup
        btrfs subvolume snapshot "$btrfs_path/$image_id" "$btrfs_path/$uuid" > /dev/null
        echo 'nameserver 8.8.8.8' > "$btrfs_path/$uuid"/etc/resolv.conf
        echo "$cmd" > "$btrfs_path/$uuid/$uuid.cmd"
        
        cgcreate -g "$cgroups:/$uuid"
        cgset -r cpu.shares="{self.config.cpu_share}" "$uuid"
        cgset -r memory.limit_in_bytes="{self.config.mem_limit * 1000000}" "$uuid"
        cgexec -g "$cgroups:$uuid" \\
            ip netns exec netns_"$uuid" \\
            unshare -fmuip --mount-proc \\
            chroot "$btrfs_path/$uuid" \\
            /bin/sh -c "/bin/mount -t proc proc /proc && $cmd" \\
            2>&1 | tee "$btrfs_path/$uuid/$uuid.log" || true
        # Cleanup network
        ip link del dev veth0_"$uuid"
        ip netns del netns_"$uuid"
        """
        return self._run_bash_command(bash_script, show_realtime=True)
    
    def exec(self, args):
        """Execute a command in a running container: BOCKER exec <container_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker exec <container_id> <command>", file=sys.stderr)
            return 1
        
        container_id = args[0]
        command = ' '.join(args[1:])
        
        # Validate container exists using Python
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        container_id='{container_id}'
        
        cid="$(ps o ppid,pid | grep "^$(ps o pid,cmd | grep -E "^\\ *[0-9]+ unshare.*$container_id" | awk '{{print $1}}')" | awk '{{print $2}}')"
        [[ ! "$cid" =~ ^\\ *[0-9]+$ ]] && echo "Container '$container_id' exists but is not running" && exit 1
        nsenter -t "$cid" -m -u -i -n -p chroot "$btrfs_path/$container_id" {command}
        """
        return self._run_bash_command(bash_script, show_realtime=True)
    
    def logs(self, args):
        """View logs from a container: BOCKER logs <container_id>"""
        if len(args) < 1:
            print("Usage: bocker logs <container_id>", file=sys.stderr)
            return 1
        
        container_id = args[0]
        
        # Validate container exists using Python
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1
        
        # Check if log file exists using Python
        log_file = Path(self.btrfs_path) / container_id / f"{container_id}.log"
        if not log_file.exists():
            print(f"No log file found for container '{container_id}'", file=sys.stderr)
            return 1
        
        # Read and display log file using Python
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
        
        # Validate both container and image exist using Python
        if not self._bocker_check(container_id):
            print(f"No container named '{container_id}' exists", file=sys.stderr)
            return 1
            
        if not self._bocker_check(image_id):
            print(f"No image named '{image_id}' exists", file=sys.stderr)
            return 1
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        cgroups='{self.cgroups}'
        container_id='{container_id}'
        image_id='{image_id}'
        
        # Remove existing image
        btrfs subvolume delete "$btrfs_path/$image_id" > /dev/null
        cgdelete -g "$cgroups:/$image_id" &> /dev/null || true
        
        # Create new snapshot
        btrfs subvolume snapshot "$btrfs_path/$container_id" "$btrfs_path/$image_id" > /dev/null
        echo "Created: $image_id"
        """
        return self._run_bash_command(bash_script)
    
    def help(self, args):
        """Display help message"""
        # Use Python string formatting instead of bash echo statements
        help_text = """BOCKER - Docker implemented in around 100 lines of bash

Usage: bocker <command> [args...]

Commands:
  pull <name> <tag>           Pull an image from Docker Hub
  init <directory>            Create an image from a directory
  rm <image_id|container_id>  Delete an image or container
  images                      List images
  ps                          List containers
  run <image_id> <command>    Create a container
  exec <container_id> <cmd>   Execute a command in a running container
  logs <container_id>         View logs from a container
  commit <container_id> <img> Commit a container to an image
  help                        Display this message"""
        
        print(help_text)
        return 0

def main():
    """Main entry point with Python argument handling"""
    bocker = Bocker()
    
    if len(sys.argv) < 2:
        return bocker.help([])
    
    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Map commands to their methods using Python dict
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

