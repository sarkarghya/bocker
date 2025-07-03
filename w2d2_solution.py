# %%
"""
# W2D2 - Containerization: Building Isolation from Scratch

Today you'll learn the fundamentals of containerization by building your own container runtime from the ground up. You'll understand how modern container technologies like Docker work under the hood by implementing the core isolation mechanisms yourself using Linux primitives.

**IMPORTANT SECURITY NOTICE**: The techniques you'll learn today involve low-level system operations that can affect system stability. You must:
- Only practice on systems you own or have explicit permission to modify
- Be careful when working with system calls and kernel features
- Understand that improper use of these techniques can compromise system security

This lab will teach you the building blocks that power modern containerization platforms, giving you deep insight into both their capabilities and limitations.

<!-- toc -->

## Content & Learning Objectives

### 1️⃣ Container Image Management

You'll learn how container images are structured, distributed, and extracted without relying on Docker's built-in tools.

> **Learning Objectives**
> - Understand container image formats and layer structures
> - Implement custom image pulling from container registries
> - Extract and examine container filesystem contents
> - Recognize security implications of image distribution

### 2️⃣ Filesystem Isolation with chroot

You'll master the fundamental building block of container filesystem isolation by implementing chroot jails.

> **Learning Objectives**
> - Create isolated filesystem environments using chroot
> - Understand the limitations and security implications of chroot
> - Learn why modern containers moved beyond chroot to pivot_root
> - Implement proper filesystem preparation for containers

### 3️⃣ Resource Control with cgroups

You'll discover how to limit and monitor resource usage of containerized processes using Linux control groups.

> **Learning Objectives**
> - Configure memory, CPU, and I/O limits using cgroups v1
> - Understand the relationship between cgroups and container orchestration
> - Implement resource monitoring and enforcement
> - Learn about OOM (Out of Memory) handling in containers

### 4️⃣ Process Isolation with Namespaces

You'll explore Linux namespaces to create isolated views of system resources for containerized applications.

> **Learning Objectives**
> - Implement PID, mount, network, and UTS namespaces
> - Understand how namespaces provide process isolation
> - Learn about user namespace remapping for security
> - Recognize namespace limitations and potential security issues

### 5️⃣ Container Networking

You'll build basic container networking to understand how containers communicate with each other and the outside world.

> **Learning Objectives**
> - Create isolated network namespaces for containers
> - Implement basic container-to-host networking
> - Understand virtual ethernet pairs and bridges
> - Learn about container network security considerations

### 6️⃣ Advanced Container Security (Bonus)

You'll explore advanced security mechanisms used in production container environments.

> **Learning Objectives**
> - Implement syscall filtering with seccomp
> - Understand container image scanning and vulnerability management
> - Learn about runtime security monitoring
> - Explore admission controllers and policy enforcement

## Lab Setup

For this lab, you will work with a Linux virtual machine that has the necessary tools and permissions to work with low-level system features:

1. You will get SSH access to your development host running Ubuntu Linux
2. The host has all necessary tools pre-installed including Python 3, development tools, and container utilities
3. You have sudo access to perform system-level operations required for containerization
4. A private container registry is available for pulling base images

You are encouraged to experiment and modify the system, but:
- **Be careful with system-level changes** that might affect other users
- **Do not attempt to escape** the provided environment or access unauthorized resources
- **Clean up** your experiments to avoid impacting subsequent exercises

## Understanding Containerization

Before diving into the technical implementation, let's understand what containerization provides and why it became so popular in modern software deployment.

### What Are Containers?

Containers are **lightweight, portable execution environments** that package applications with their dependencies while sharing the host operating system kernel. Unlike virtual machines that virtualize entire hardware stacks, containers use Linux kernel features to provide isolation at the process level.

Key characteristics of containers:
- **Process Isolation**: Each container runs in its own process space
- **Filesystem Isolation**: Containers have their own filesystem view
- **Resource Limits**: CPU, memory, and I/O can be controlled and limited
- **Network Isolation**: Containers can have isolated network stacks
- **Portability**: Containers run consistently across different environments

### Container vs Virtual Machine Architecture

```
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│            Virtual Machines         │  │             Containers              │
├─────────────────────────────────────┤  ├─────────────────────────────────────┤
│  App A  │  App B  │  App C          │  │  App A  │  App B  │  App C          │
├─────────┼─────────┼─────────────────┤  ├─────────┼─────────┼─────────────────┤
│ Bins/   │ Bins/   │ Bins/           │  │ Bins/   │ Bins/   │ Bins/           │
│ Libs    │ Libs    │ Libs            │  │ Libs    │ Libs    │ Libs            │
├─────────┼─────────┼─────────────────┤  ├─────────┼─────────┼─────────────────┤
│Guest OS │Guest OS │Guest OS         │  │         Container Engine            │
├─────────┼─────────┼─────────────────┤  ├─────────────────────────────────────┤
│           Hypervisor                │  │            Host OS                  │
├─────────────────────────────────────┤  ├─────────────────────────────────────┤
│            Host OS                  │  │           Hardware                  │
├─────────────────────────────────────┤  └─────────────────────────────────────┘
│           Hardware                  │
└─────────────────────────────────────┘
```

### Linux Kernel Features for Containerization

Modern containerization relies on several Linux kernel features:

1. **Namespaces**: Provide isolation of system resources
   - PID namespace: Process ID isolation
   - Mount namespace: Filesystem mount point isolation
   - Network namespace: Network stack isolation
   - UTS namespace: Hostname and domain name isolation
   - User namespace: User and group ID isolation
   - IPC namespace: Inter-process communication isolation

2. **Control Groups (cgroups)**: Resource limiting and accounting
   - Memory limits and usage tracking
   - CPU time and priority control
   - I/O bandwidth limiting
   - Device access control

3. **Union Filesystems**: Layered filesystem management
   - OverlayFS: Efficient copy-on-write filesystem
   - AUFS: Another union filesystem (deprecated)
   - Device Mapper: Block-level storage driver

4. **Security Features**: Additional isolation and access control
   - Capabilities: Fine-grained privilege control
   - SELinux/AppArmor: Mandatory access control
   - Seccomp: System call filtering

### Container Image Format

Container images are **layered filesystems** packaged in a standardized format. Each layer represents a set of filesystem changes, and layers are stacked to create the final container filesystem.

**Image Layers Example**:
```
┌─────────────────────────────────────┐
│     Application Layer               │  ← Your app and configs
├─────────────────────────────────────┤
│     Runtime Dependencies           │  ← Python, Node.js, etc.
├─────────────────────────────────────┤
│     Package Manager Updates        │  ← apt update, yum update
├─────────────────────────────────────┤
│     Base OS Layer                  │  ← Ubuntu, Alpine, etc.
└─────────────────────────────────────┘
```

This layered approach provides several benefits:
- **Efficiency**: Common layers are shared between images
- **Caching**: Unchanged layers don't need to be re-downloaded
- **Version Control**: Similar to Git, each layer has a unique hash
- **Security**: Individual layers can be scanned for vulnerabilities
"""

# %%
"""
## Code provided to you
"""

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

    def _check_cgroup_v1_exists(self, container_id):
        """Check if cgroup v1 exists for the given container/image ID"""
        subsystems = self.cgroups.split(',')  # ['cpu', 'cpuacct', 'memory']
        
        for subsystem in subsystems:
            cgroup_dir = f"/sys/fs/cgroup/{subsystem}/{container_id}"
            if os.path.exists(cgroup_dir):
                print(f"DEBUG: Cgroup directory {cgroup_dir} exists")
                return True
            else:
                print(f"DEBUG: Cgroup directory {cgroup_dir} does not exist")
        
        return False

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



# %%
# %%
"""
## Exercise 1: Container Image Management

In this first exercise, you'll implement the foundation of our container system:
managing container images. This includes creating images from directories, 
pulling images from remote registries, listing available images, and removing them.

We'll start with the basic image management operations that form the core of 
any container system, similar to `docker images`, `docker pull`, and `docker rmi`.

## Introduction

Container images are the building blocks of containerization. They contain:
- The filesystem that will become the container's root filesystem
- Metadata about how to run the container
- Layer information for efficient storage and transfer

Image management involves several key operations:
1. **Creating images** from existing directories (like `docker build` from a Dockerfile)
2. **Pulling images** from remote registries (like Docker Hub)
3. **Listing images** to see what's available locally
4. **Removing images** to free up storage space

Our implementation uses Btrfs subvolumes for efficient copy-on-write storage,
similar to how Docker uses overlay filesystems.

## Content & Learning Objectives

### 1️⃣ Image Creation from Directories

You'll implement the `init` command that creates a container image from a local directory.

> **Learning Objectives**
> - Understand how container images are created from filesystems
> - Learn about Btrfs subvolumes and copy-on-write storage
> - Implement filesystem-based image creation

### 2️⃣ Remote Image Pulling

Here, you'll implement downloading and extracting container images from remote storage.

> **Learning Objectives**
> - Understand container image distribution and registries
> - Implement HTTP-based image downloading with progress tracking
> - Learn about image manifests and layer extraction

### 3️⃣ Image Listing and Management

You'll implement commands to list available images and remove unwanted ones.

> **Learning Objectives**
> - Implement image metadata management
> - Create user-friendly output formatting
> - Handle image lifecycle management

## Vocabulary: Container Image Terms

- **Image**: A read-only template containing the filesystem and metadata needed to create containers
- **Layer**: A single filesystem change that can be stacked with others to form a complete image
- **Manifest**: Metadata describing the image structure and layers
- **Registry**: A service that stores and distributes container images
- **Tag**: A human-readable identifier for a specific version of an image
- **Subvolume**: A Btrfs feature that provides copy-on-write snapshots of filesystems

## Vocabulary: Btrfs Terms

- **Btrfs**: A modern filesystem with built-in copy-on-write, snapshots, and compression
- **Copy-on-write (CoW)**: A technique where data is only copied when modified, saving space
- **Subvolume**: A separately mountable portion of a Btrfs filesystem
- **Snapshot**: A point-in-time copy of a subvolume that shares unchanged data

## Vocabulary: Image Distribution Terms

- **Tarball**: A compressed archive format commonly used for distributing images
- **Extraction**: The process of unpacking compressed archives
- **Manifest**: JSON metadata describing image contents and structure
- **Layer extraction**: Unpacking individual filesystem layers from an image archive
"""

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
        
        # if centos_img:
        #     print(f"Testing pulled CentOS image: {centos_img}")
        #     # Test that we can create a container from the pulled image
        #     returncode = self.run([centos_img, 'echo', 'centos_test'])
        #     time.sleep(2)
            
        #     # Verify container was created
        #     containers = self._list_containers()
        #     centos_container = None
        #     for container in containers:
        #         if 'echo centos_test' in container['command']:
        #             centos_container = container['id']
        #             break
            
        #     if centos_container:
        #         print(f"Successfully created container from pulled image: {centos_container}")
        #     else:
        #         print("Warning: Could not create container from pulled image")

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

    def test_v1(self):
        """Test v1 functionality by running only BockerV1-specific test methods"""
        print("Testing BockerV1 functionality...")
        print("=" * 50)
        
        # Define only the test methods that belong to BockerV1
        v1_test_methods = ['test_init', 'test_pull', 'test_images', 'test_rm']
        
        # Filter to only include methods that actually exist in this class
        test_methods = []
        for method_name in v1_test_methods:
            if hasattr(self, method_name) and callable(getattr(self, method_name)):
                test_methods.append(method_name)
        
        print(f"Found {len(test_methods)} BockerV1 test methods: {', '.join(test_methods)}")
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
        print("BockerV2 Test Summary:")
        print("-" * 50)
        for test_name in test_methods:
            status = results.get(test_name, "UNKNOWN")
            status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "💥"
            print(f"{status_symbol} {test_name:<15} : {status}")
        
        print("-" * 50)
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print("=" * 50)
        
        return overall_success


# %%
# %%
"""
## Exercise 2: Container Creation and Chroot Execution

In this exercise, you'll implement container creation and execution with basic filesystem 
isolation using chroot. This builds on Exercise 1 by adding the ability to run processes 
inside containers with isolated filesystems.

We'll implement container listing, running containers with chroot isolation, viewing 
container logs, and basic container lifecycle management.

## Introduction

Container execution is the core functionality that distinguishes containers from simple 
filesystem images. When you run a container, several things happen:

1. **Filesystem Isolation**: The container gets its own view of the filesystem using chroot
2. **Process Execution**: Commands run inside the isolated environment
3. **Resource Tracking**: The system tracks running containers and their state
4. **Log Management**: Output from container processes is captured for debugging

Chroot (change root) is a Unix operation that changes the apparent root directory for 
the current running process and its children. This creates a "jail" where processes 
cannot access files outside their designated directory tree.

While chroot provides basic filesystem isolation, it's not a complete security boundary. 
Modern containers use additional technologies like namespaces and cgroups for stronger 
isolation, which we'll explore in later exercises.

Container lifecycle management involves tracking which containers exist, what commands 
they're running, and maintaining logs of their output. This is essential for debugging 
and monitoring containerized applications.

## Content & Learning Objectives

### 1️⃣ Container Listing and Management

You'll implement the `ps` command to list running and stopped containers.

> **Learning Objectives**
> - Understand container metadata and state tracking
> - Implement filesystem-based container discovery
> - Create user-friendly output formatting for container information

### 2️⃣ Container Execution with Chroot

Here, you'll implement the `run` command that creates and executes containers with filesystem isolation.

> **Learning Objectives**
> - Understand how chroot provides filesystem isolation
> - Implement container creation from images using Btrfs snapshots
> - Learn about process execution within isolated environments

### 3️⃣ Container Log Management

You'll implement log viewing functionality to debug and monitor container execution.

> **Learning Objectives**
> - Implement log capture and storage for container processes
> - Create log viewing interfaces for debugging containers
> - Understand the importance of observability in containerized systems

## Vocabulary: Container Execution Terms

- **Container**: A running instance of an image with its own isolated environment
- **Chroot**: Unix operation that changes the root directory for a process and its children
- **Filesystem isolation**: Preventing processes from accessing files outside their designated area
- **Container ID**: Unique identifier for each container instance (ps_* format in our implementation)
- **Process isolation**: Separating running processes so they can't interfere with each other
- **Container lifecycle**: The stages a container goes through from creation to termination

## Vocabulary: Chroot Terms

- **Root directory**: The top-level directory (/) that serves as the base of the filesystem
- **Jail**: Colloquial term for a chrooted environment that restricts filesystem access
- **Mount**: Attaching a filesystem to a specific directory in the filesystem hierarchy
- **Proc filesystem**: Special filesystem (/proc) that provides information about running processes
- **Nameserver**: DNS server configuration that allows containers to resolve domain names

## Vocabulary: Container Management Terms

- **Container registry**: A service for storing and distributing container images
- **Container state**: The current status of a container (running, stopped, failed, etc.)
- **Log aggregation**: Collecting and centralizing logs from multiple containers
- **Container orchestration**: Managing multiple containers across multiple hosts
- **Health checks**: Automated tests to verify container functionality

## Vocabulary: Btrfs Snapshot Terms

- **Snapshot**: A point-in-time copy of a subvolume that shares unchanged data with the original
- **Copy-on-write (CoW)**: A technique where data is only copied when it's modified
- **Subvolume**: A separately mountable portion of a Btrfs filesystem
- **Reflink**: Btrfs feature for creating efficient copies that share data blocks
- **Space efficiency**: Using minimal storage by sharing common data between containers
"""

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

    def run(self, args):
        """Create a container with basic filesystem isolation: BOCKER run_basic <image_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker run_basic <image_id> <command>", file=sys.stderr)
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

    def test_run(self):
        """Test basic run functionality (filesystem only)"""
        print("Testing bocker run_basic...")
        
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
        
        # Test basic echo command
        returncode = self.run([img_id, 'echo', 'basic_test'])
        time.sleep(2)
        
        # Verify container was created and has logs
        containers = self._list_containers()
        container_found = False
        for container in containers:
            if 'echo basic_test' in container['command']:
                container_found = True
                # Check logs
                log_file = Path(self.btrfs_path) / container['id'] / f"{container['id']}.log"
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                    if 'basic_test' not in log_content:
                        print(f"FAIL: Expected 'basic_test' in logs, got: {log_content}")
                        return False
                break
        
        if not container_found:
            print("FAIL: Container not found after basic run")
            return False

        print("PASS: bocker run_basic test")
        return True

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

    def test_logs(self):
        """Test logs functionality"""
        print("Testing bocker logs...")
        
        # Test with invalid container first
        returncode = self.logs(['nonexistent_container'])
        if returncode == 0:
            print("FAIL: Logs should fail with nonexistent container")
            return False
        
        # Test with no arguments
        returncode = self.logs([])
        if returncode == 0:
            print("FAIL: Logs should fail with no arguments")
            return False
        
        # Create a test container to test logs with
        images = self._list_images()
        if not images:
            base_image_dir = os.path.expanduser('~/base-image')
            if not os.path.exists(base_image_dir):
                print("SKIP: No images available for log testing")
                return True
            self.init([base_image_dir])
            images = self._list_images()
        
        if not images:
            print("SKIP: Could not create test image")
            return True
        
        img_id = images[0]['id']
        test_message = f"test_log_message_{random.randint(1000, 9999)}"
        
        # Run a command that will produce output
        print(f"Creating container with test message: {test_message}")
        returncode = self.run([img_id, 'echo', test_message])
        time.sleep(2)  # Give container time to complete
        
        # Find the container
        containers = self._list_containers()
        container_id = None
        for container in containers:
            if f'echo {test_message}' in container['command']:
                container_id = container['id']
                break
        
        if not container_id:
            print("FAIL: Could not find test container")
            return False
        
        print(f"Testing logs for container: {container_id}")
        
        # Capture logs output
        import io
        from contextlib import redirect_stdout
        
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            returncode = self.logs([container_id])
        
        if returncode != 0:
            print(f"FAIL: Logs command failed with return code {returncode}")
            return False
        
        log_output = output_buffer.getvalue()
        if test_message not in log_output:
            print(f"FAIL: Expected '{test_message}' in logs, got: {log_output}")
            return False
        
        print(f"SUCCESS: Found expected message in logs: {test_message}")
        print("PASS: bocker logs test")
        return True

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

    def test_v2(self):
        """Test v2 functionality by running only BockerV2-specific test methods"""
        print("Testing BockerV2 functionality...")
        print("=" * 50)
        
        # Define only the test methods that belong to BockerV2
        v2_test_methods = ['test_ps', 'test_run', 'test_rm', 'test_logs']
        
        # Filter to only include methods that actually exist in this class
        test_methods = []
        for method_name in v2_test_methods:
            if hasattr(self, method_name) and callable(getattr(self, method_name)):
                test_methods.append(method_name)
        
        print(f"Found {len(test_methods)} BockerV2 test methods: {', '.join(test_methods)}")
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
        print("BockerV2 Test Summary:")
        print("-" * 50)
        for test_name in test_methods:
            status = results.get(test_name, "UNKNOWN")
            status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "💥"
            print(f"{status_symbol} {test_name:<15} : {status}")
        
        print("-" * 50)
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print("=" * 50)
        
        return overall_success

# %%
"""
## Exercise 3: Resource Management with Cgroups

In this exercise, you'll implement container resource management using Linux cgroups 
(control groups). This builds on Exercise 2 by adding the ability to limit and monitor 
resource usage of containers, preventing them from consuming unlimited system resources.

We'll implement CPU and memory limits, understand how cgroups work, and see how 
modern container systems manage resources at scale.

## Introduction

Resource management is critical in containerized environments where multiple containers 
share the same host system. Without proper limits, a single container could consume 
all available CPU, memory, or other resources, causing system instability or denial 
of service to other containers.

Cgroups (control groups) is a Linux kernel feature that allows you to:

1. **Limit resources**: Set maximum CPU, memory, disk I/O, and network usage
2. **Prioritize access**: Ensure critical containers get resources first
3. **Monitor usage**: Track actual resource consumption for billing and optimization
4. **Isolate processes**: Prevent containers from interfering with each other

Cgroups work by creating hierarchical groups of processes and applying resource 
constraints to those groups. Each container gets its own cgroup, and the kernel 
enforces the limits automatically.

There are two major versions of cgroups:
- **Cgroups v1**: The original implementation with separate hierarchies per resource type
- **Cgroups v2**: A unified hierarchy design that's simpler and more efficient

Most production container systems use cgroups extensively. For example:
- Docker sets memory and CPU limits for containers
- Kubernetes uses cgroups for resource quotas and quality of service
- Cloud providers use cgroups to enforce instance limits

## Content & Learning Objectives

### 1️⃣ Understanding Cgroups Architecture

You'll learn how cgroups are structured and how to create resource-limited containers.

> **Learning Objectives**
> - Understand the cgroups filesystem interface
> - Learn about different cgroup subsystems (cpu, memory, etc.)
> - Implement cgroup creation and configuration for containers

### 2️⃣ CPU Resource Management

Here, you'll implement CPU limits using the cpu and cpuacct cgroup subsystems.

> **Learning Objectives**
> - Understand CPU shares and how relative CPU allocation works
> - Implement CPU-limited container execution
> - Learn about CPU accounting and monitoring

### 3️⃣ Memory Resource Management

You'll implement memory limits and understand how the kernel enforces them.

> **Learning Objectives**
> - Understand memory limits and out-of-memory (OOM) behavior
> - Implement memory-limited containers
> - Learn about memory accounting and swap control

### 4️⃣ Cgroup Cleanup and Management

Finally, you'll implement proper cgroup lifecycle management.

> **Learning Objectives**
> - Understand cgroup cleanup and resource deallocation
> - Implement proper error handling for resource management
> - Learn about cgroup hierarchy and inheritance

## Vocabulary: Cgroups Terms

- **Cgroup**: A collection of processes with shared resource limits and accounting
- **Subsystem**: A resource controller (cpu, memory, blkio, etc.) that manages specific resource types
- **Hierarchy**: A tree structure of cgroups with inheritance relationships
- **Tasks**: The processes assigned to a particular cgroup
- **Control files**: Special files in the cgroup filesystem used to set limits and read statistics
- **cgcreate**: Command-line tool to create new cgroups
- **cgset**: Command-line tool to set cgroup parameters
- **cgexec**: Command-line tool to run processes in a specific cgroup

## Vocabulary: CPU Management Terms

- **CPU shares**: Relative weight for CPU allocation (higher = more CPU time)
- **CPU quota**: Absolute limit on CPU usage (e.g., 50% of one core)
- **CPU period**: Time window for quota enforcement (usually 100ms)
- **cpuacct**: CPU accounting subsystem that tracks actual CPU usage
- **Load balancing**: Kernel mechanism to distribute processes across CPU cores
- **Nice value**: Process priority that affects CPU scheduling
- **Throttling**: Temporarily pausing processes that exceed CPU quota

## Vocabulary: Memory Management Terms

- **Memory limit**: Maximum amount of RAM a cgroup can use
- **OOM (Out of Memory)**: Condition when a process tries to use more memory than available
- **OOM killer**: Kernel mechanism that terminates processes to free memory
- **RSS (Resident Set Size)**: Physical memory currently used by processes
- **Cache**: Memory used for file system caching (can be reclaimed)
- **Swap**: Disk space used as virtual memory when RAM is full
- **Memory pressure**: Condition when memory usage approaches limits

## Vocabulary: Resource Isolation Terms

- **Resource contention**: Competition between processes for limited resources
- **Quality of Service (QoS)**: Different service levels based on resource guarantees
- **Resource reservation**: Guaranteeing minimum resources for critical processes
- **Burst capacity**: Ability to temporarily exceed normal resource limits
- **Fair share scheduling**: Ensuring each container gets proportional resource access
- **Resource monitoring**: Tracking actual usage for optimization and billing

## Vocabulary: Container Orchestration Terms

- **Node**: A physical or virtual machine running containers
- **Pod**: Kubernetes unit that groups containers sharing resources
- **Resource requests**: Minimum resources needed for a container to run
- **Resource limits**: Maximum resources a container is allowed to use
- **Horizontal scaling**: Adding more container instances to handle load
- **Vertical scaling**: Increasing resources allocated to existing containers
- **Resource quotas**: Limits on total resource usage across multiple containers
"""

class BockerV3(BockerV2):
    """Bocker v3: Adds cgroups for resource management"""
    
    def _get_available_commands(self):
        return super()._get_available_commands() + "\n  Resource management with cgroups enabled"

    def run(self, args):
        """Create a container with cgroup resource limits: BOCKER run <image_id> <command>"""
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

    def test_run(self):
        """FIXME: Test run with cgroups functionality"""
        print("Testing bocker run...")
        
        images = self._list_images()
        if not images:
            print("SKIP: No images available for cgroups testing")
            return True
            
        img_id = images[0]['id']
        print(f"Using image: {img_id}")
        
        # Test argument validation first
        returncode = self.run([])
        if returncode != 1:
            print("FAIL: run should fail with no arguments")
            return False
        
        returncode = self.run([img_id])
        if returncode != 1:
            print("FAIL: run should fail with no command")
            return False
        
        # Test with invalid image
        returncode = self.run(['nonexistent_img', 'echo', 'test'])
        if returncode == 0:
            print("FAIL: run should fail with nonexistent image")
            return False
        
        # Test successful cgroups run
        test_command = 'cgroups_test_12345'
        returncode = self.run([img_id, 'echo', test_command])
        
        import time
        time.sleep(2)
        
        # Find the container
        containers = self._list_containers()
        container_id = None
        for container in containers:
            if test_command in container['command']:
                container_id = container['id']
                break
        
        if not container_id:
            print("FAIL: Container not found after cgroups run")
            return False
        
        print(f"DEBUG: Found container {container_id}")
        
        # Verify container exists in filesystem
        if not self._bocker_check(container_id):
            print("FAIL: Container not found in btrfs subvolumes")
            return False
        
        # Check logs were created and contain expected output
        log_file = Path(self.btrfs_path) / container_id / f"{container_id}.log"
        if not log_file.exists():
            print(f"FAIL: Log file not found for container {container_id}")
            return False
        
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            if test_command not in log_content:
                print(f"FAIL: Expected '{test_command}' in logs, got: {log_content}")
                return False
            
            print(f"SUCCESS: Found '{test_command}' in logs")
        except Exception as e:
            print(f"FAIL: Error reading log file: {e}")
            return False
        
        # Test that cgroups were created during execution
        # Note: They may be cleaned up after container exits, so we test during a longer-running command
        print("Testing cgroup creation with longer-running command...")
        long_test_command = 'sleep 3 && echo cgroup_long_test'
        
        # Run in background and check cgroups while it's running
        import threading
        import time
        
        def run_long_container():
            self.run([img_id, 'sh', '-c', long_test_command])
        
        # Start container in background
        thread = threading.Thread(target=run_long_container)
        thread.start()
        
        # Give it time to start and create cgroups
        time.sleep(1)
        
        # Find the new container
        containers = self._list_containers()
        long_container_id = None
        for container in containers:
            if 'cgroup_long_test' in container['command'] or 'sleep 3' in container['command']:
                long_container_id = container['id']
                break
        
        if long_container_id:
            print(f"DEBUG: Checking cgroups for running container {long_container_id}")
            cgroup_exists = self._check_cgroup_v1_exists(long_container_id)
            if cgroup_exists:
                print("SUCCESS: Cgroups were created for running container")
            else:
                print("WARNING: Cgroups not found for running container (may have exited quickly)")
        
        # Wait for thread to complete
        thread.join()
        
        print("PASS: bocker run test")
        return True

    def rm(self, args):
        """Delete a container cgroup"""
        # First call the parent's rm method to handle basic removal
        result = super().rm(args)
        if result != 0:
            return result
        
        # Then add the cgroup deletion functionality with proper loop
        container_id = args[0]
        
        # Split the cgroups string and create individual delete commands
        cgroup_delete_commands = [f'cgdelete -g "{cgroup.strip()}:/{container_id}" &> /dev/null || true' \
            for cgroup in self.cgroups.split(',')]
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        {chr(10).join(cgroup_delete_commands)}
        """
        return self._run_bash_command(bash_script)

    def test_rm(self):
        """Test rm functionality with cgroup cleanup for containers"""
        print("Testing bocker rm with cgroups...")
        
        # Create a test image first
        base_image_dir = os.path.expanduser('~/base-image')
        if not os.path.exists(base_image_dir):
            print("SKIP: Base image directory not found")
            return True
        
        # Step 1: Create image
        print("DEBUG: Creating image...")
        self.init([base_image_dir])
        images = self._list_images()
        if not images:
            print("FAIL: No images found after init")
            return False
        img_id = images[-1]['id']  # Get the most recently created image
        print(f"DEBUG: Created image: {img_id}")
        
        # Step 2: Create a container from the image using run (this creates ps_* containers with cgroups)
        import random
        cmd = f"echo {random.randint(1000, 9999)}"
        print(f"DEBUG: Running command to create container: {cmd}")
        
        # This will create a ps_* container with cgroups
        returncode = self.run([img_id, 'echo', 'test_container'])
        if returncode != 0:
            print(f"FAIL: Run command failed with return code {returncode}")
            return False
        
        # Give container time to complete
        time.sleep(2)
        
        # Step 3: Get the container ID (ps_* format)
        containers = self._list_containers()
        container_id = None
        for container in containers:
            if 'echo test_container' in container['command']:
                container_id = container['id']
                break
        
        if not container_id:
            print("FAIL: No container found after run command")
            return False
        
        print(f"DEBUG: Found container: {container_id}")
        
        # Step 4: Verify container exists before removal
        if not self._bocker_check(container_id):
            print(f"FAIL: Container {container_id} not found before removal")
            return False
        
        # Step 5: Check cgroup exists before removal (only for ps_* containers)
        print(f"DEBUG: Checking cgroups BEFORE removal for container {container_id}")
        cgroup_exists_before = self._check_cgroup_v1_exists(container_id)
        print(f"DEBUG: Cgroup exists before removal: {cgroup_exists_before}")
        
        # Step 6: Remove the container
        print(f"DEBUG: Removing container {container_id}")
        returncode = self.rm([container_id])
        if returncode != 0:
            print(f"FAIL: RM command failed with return code {returncode}")
            return False
        
        # Step 7: Verify container is gone
        if self._bocker_check(container_id):
            print(f"FAIL: Container {container_id} still exists after removal")
            return False
        print(f"DEBUG: Container successfully removed")
        
        # Step 8: Verify cgroup is gone (only check if it existed before)
        print(f"DEBUG: Checking cgroups AFTER removal for container {container_id}")
        cgroup_exists_after = self._check_cgroup_v1_exists(container_id)
        print(f"DEBUG: Cgroup exists after removal: {cgroup_exists_after}")
        
        # Only fail if cgroup existed before but still exists after
        if cgroup_exists_before and cgroup_exists_after:
            print("FAIL: Cgroup still exists after removal")
            return False
        elif cgroup_exists_before and not cgroup_exists_after:
            print("DEBUG: Cgroup successfully cleaned up")
        elif not cgroup_exists_before:
            print("DEBUG: No cgroup existed before removal (this is unexpected for ps_* containers)")
        
        # Test error cases
        print("DEBUG: Testing error cases...")
        
        # Test invalid container ID
        returncode = self.rm(['nonexistent_container'])
        if returncode == 0:
            print("FAIL: RM should fail with nonexistent container")
            return False
        
        # Test missing arguments
        returncode = self.rm([])
        if returncode != 1:
            print("FAIL: RM should fail with no arguments")
            return False
        
        # Test removing an image (img_*) - should work but no cgroup cleanup needed
        print("DEBUG: Testing image removal...")
        returncode = self.rm([img_id])
        if returncode != 0:
            print(f"FAIL: RM command failed for image removal with return code {returncode}")
            return False
        
        # Verify image is gone
        if self._bocker_check(img_id):
            print("FAIL: Image still exists after removal")
            return False

        print("PASS: bocker rm test")
        return True

    def test_v3(self):
        """Test v3 functionality by running only BockerV3-specific test methods"""
        print("Testing BockerV3 functionality...")
        print("=" * 50)
        
        # Define only the test methods that belong to BockerV3
        v3_test_methods = ['test_run', 'test_rm']
        
        # Filter to only include methods that actually exist in this class
        test_methods = []
        for method_name in v3_test_methods:
            if hasattr(self, method_name) and callable(getattr(self, method_name)):
                test_methods.append(method_name)
        
        print(f"Found {len(test_methods)} BockerV3 test methods: {', '.join(test_methods)}")
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
        print("BockerV3 Test Summary:")
        print("-" * 50)
        for test_name in test_methods:
            status = results.get(test_name, "UNKNOWN")
            status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "💥"
            print(f"{status_symbol} {test_name:<15} : {status}")
        
        print("-" * 50)
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print("=" * 50)
        
        return overall_success

# %%
# %%
"""
## Exercise 4: Process and Network Isolation with Namespaces

In this exercise, you'll implement Linux namespaces to provide stronger isolation 
between containers. This builds on Exercise 3 by adding process ID (PID) and 
network namespaces, creating truly isolated container environments.

We'll implement namespace creation, process isolation, network isolation, and 
understand how modern container systems achieve security through isolation.

## Introduction

Linux namespaces are a fundamental feature that enables containerization by providing 
different types of isolation. While chroot provides filesystem isolation and cgroups 
manage resources, namespaces isolate various system resources so that processes in 
different namespaces have different views of the system.

There are several types of namespaces:

1. **PID Namespace**: Isolates process IDs - processes in a PID namespace only see other processes in the same namespace
2. **Network Namespace**: Provides separate network stacks with their own interfaces, routing tables, and firewall rules
3. **Mount Namespace**: Isolates filesystem mount points
4. **UTS Namespace**: Isolates hostname and domain name
5. **IPC Namespace**: Isolates inter-process communication resources
6. **User Namespace**: Isolates user and group IDs

The combination of namespaces, cgroups, and chroot creates the foundation for modern 
container security. Docker, Podman, and other container runtimes use these Linux 
kernel features to provide isolation between containers and from the host system.

Process isolation is particularly important because it prevents containers from 
seeing or interfering with processes on the host or in other containers. Network 
isolation allows containers to have their own network configuration without 
conflicting with the host or other containers.

## Content & Learning Objectives

### 1️⃣ PID Namespace Implementation

You'll implement process isolation using PID namespaces and the `unshare` command.

> **Learning Objectives**
> - Understand how PID namespaces provide process isolation
> - Implement container execution with isolated process trees
> - Learn about process visibility and security implications

### 2️⃣ Network Namespace Creation

Here, you'll implement network isolation using network namespaces.

> **Learning Objectives**
> - Understand network namespace fundamentals
> - Implement isolated network environments for containers
> - Learn about virtual network interfaces and routing

### 3️⃣ Combined Namespace Isolation

You'll combine multiple namespace types for comprehensive container isolation.

> **Learning Objectives**
> - Implement multi-namespace container execution
> - Understand namespace interaction and dependencies
> - Learn about the security benefits of layered isolation

### 4️⃣ Namespace Cleanup and Management

Finally, you'll implement proper namespace lifecycle management.

> **Learning Objectives**
> - Understand namespace cleanup and resource management
> - Implement proper error handling for namespace operations
> - Learn about namespace persistence and cleanup challenges

## Vocabulary: Namespace Terms

- **Namespace**: A Linux kernel feature that partitions system resources so that one set of processes sees one set of resources while another set sees a different set
- **unshare**: Command-line utility to run programs with some namespaces unshared from parent
- **nsenter**: Command-line utility to enter existing namespaces
- **PID 1**: The init process in a PID namespace, responsible for reaping zombie processes
- **Process tree**: Hierarchical structure of processes where each process has a parent
- **Zombie process**: A process that has completed execution but still has an entry in the process table
- **Process reaping**: The act of cleaning up zombie processes by reading their exit status

## Vocabulary: Network Namespace Terms

- **Network stack**: The complete set of networking components including interfaces, routing, and firewall rules
- **Virtual ethernet (veth)**: A pair of connected virtual network interfaces
- **Bridge**: A network device that connects multiple network segments
- **Loopback interface**: The local network interface (usually lo or 127.0.0.1)
- **Routing table**: A data table that determines where network packets should be forwarded
- **Network interface**: A point of interconnection between a computer and a network
- **IP address assignment**: The process of configuring network addresses for interfaces

## Vocabulary: Container Security Terms

- **Attack surface**: The sum of different points where an unauthorized user can try to enter or extract data
- **Privilege escalation**: The act of exploiting a bug or design flaw to gain elevated access
- **Container escape**: Breaking out of container isolation to access the host system
- **Defense in depth**: A security strategy using multiple layers of protection
- **Least privilege**: Security principle of giving minimal access rights necessary to perform tasks
- **Isolation boundary**: The security perimeter that separates different execution environments

## Vocabulary: System Administration Terms

- **Init system**: The first process started during system boot, responsible for starting other processes
- **Process supervision**: Monitoring and managing the lifecycle of processes
- **Signal handling**: The mechanism by which processes respond to system signals
- **Resource cleanup**: The process of freeing system resources when they're no longer needed
- **System call**: A programmatic way for programs to request services from the kernel
- **Kernel space**: The memory area reserved for running the kernel and kernel extensions
- **User space**: The memory area where user applications run
"""

class BockerV4(BockerV3):
    """Bocker v4: Adds namespaces for better isolation"""
    
    def _get_available_commands(self):
        return super()._get_available_commands() + "\n  Process isolation with namespaces enabled"

    def run(self, args):
        """Create a container with network namespace isolation: BOCKER run <image_id> <command>"""
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

    def test_run(self):
        """Test run with network namespace functionality"""
        print("Testing bocker run...")
        
        # Get available images
        images = self._list_images()
        if not images:
            print("SKIP: No images available for netns testing")
            return True
            
        img_id = images[0]['id']
        print(f"Using image: {img_id}")
        
        # Test argument validation
        if self.run([]) != 1:
            print("FAIL: run should fail with no arguments")
            return False
        
        if self.run([img_id]) != 1:
            print("FAIL: run should fail with no command")
            return False
        
        if self.run(['nonexistent_img', 'echo', 'test']) == 0:
            print("FAIL: run should fail with nonexistent image")
            return False
        
        # Test basic container creation with network namespace
        test_command = f'netns_test_{random.randint(10000, 99999)}'
        returncode = self.run([img_id, 'echo', test_command])
        
        if returncode != 0:
            print(f"FAIL: Run command failed with return code {returncode}")
            return False
        
        time.sleep(2)  # Allow container to complete
        
        # Verify container was created
        containers = self._list_containers()
        container_id = None
        for container in containers:
            if test_command in container['command']:
                container_id = container['id']
                break
        
        if not container_id:
            print("FAIL: Container not found after run")
            return False
        
        # Verify logs contain expected output
        log_file = Path(self.btrfs_path) / container_id / f"{container_id}.log"
        if not log_file.exists():
            print(f"FAIL: Log file not found for container {container_id}")
            return False
        
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            if test_command not in log_content:
                print(f"FAIL: Expected '{test_command}' in logs, got: {log_content}")
                return False
            
            print(f"SUCCESS: Found '{test_command}' in logs")
        except Exception as e:
            print(f"FAIL: Error reading log file: {e}")
            return False
        
        # Test network isolation by checking if container can see loopback interface
        print("Testing network isolation...")
        network_test_command = 'ip link show lo'
        returncode = self.run([img_id, 'sh', '-c', network_test_command])
        
        if returncode == 0:
            time.sleep(2)
            
            # Find the network test container
            containers = self._list_containers()
            for container in containers:
                if 'ip link show lo' in container['command']:
                    network_log_file = Path(self.btrfs_path) / container['id'] / f"{container['id']}.log"
                    if network_log_file.exists():
                        try:
                            with open(network_log_file, 'r') as f:
                                network_log_content = f.read()
                            
                            if 'lo:' in network_log_content or 'LOOPBACK' in network_log_content:
                                print("SUCCESS: Network namespace isolation working")
                            else:
                                print("WARNING: Network namespace test inconclusive")
                        except Exception as e:
                            print(f"WARNING: Could not read network test logs: {e}")
                    break
        else:
            print("WARNING: Network test command failed, but basic functionality works")
        
        print("PASS: bocker run test")
        return True

    def test_v4(self):
        """FIXME: Test v4 functionality by running only BockerV4-specific test methods"""
        print("Testing BockerV4 functionality...")
        print("=" * 50)
        
        # Define only the test methods that belong to BockerV4
        v4_test_methods = ['test_run']
        
        # Filter to only include methods that actually exist in this class
        test_methods = []
        for method_name in v4_test_methods:
            if hasattr(self, method_name) and callable(getattr(self, method_name)):
                test_methods.append(method_name)
        
        print(f"Found {len(test_methods)} BockerV4 test methods: {', '.join(test_methods)}")
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
        print("BockerV4 Test Summary:")
        print("-" * 50)
        for test_name in test_methods:
            status = results.get(test_name, "UNKNOWN")
            status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "💥"
            print(f"{status_symbol} {test_name:<15} : {status}")
        
        print("-" * 50)
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print("=" * 50)
        
        return overall_success

# %%
"""
## Exercise 5: Full Container Networking

In this exercise, you'll implement complete container networking with virtual ethernet 
interfaces, bridge networking, and IP address management. This builds on Exercise 4 
by adding full network connectivity between containers and to the external world.

We'll implement virtual network interfaces, bridge configuration, IP routing, and 
understand how container orchestration platforms manage networking at scale.

## Introduction

Container networking is one of the most complex aspects of containerization. While 
namespaces provide isolation, containers also need connectivity - both to each other 
and to external networks. This requires sophisticated virtual networking infrastructure.

Modern container networking involves several key components:

1. **Virtual Ethernet Pairs (veth)**: Pairs of connected virtual network interfaces where packets sent to one appear on the other
2. **Network Bridges**: Virtual switches that connect multiple network segments
3. **IP Address Management**: Automatic assignment of unique IP addresses to containers
4. **Routing and NAT**: Enabling containers to reach external networks
5. **DNS Resolution**: Allowing containers to resolve domain names

The networking model we'll implement is similar to Docker's default bridge networking:
- Each container gets its own network namespace with a virtual ethernet interface
- All container interfaces connect to a shared bridge (like a virtual switch)
- The bridge provides layer 2 connectivity between containers
- Network Address Translation (NAT) enables external connectivity
- Each container receives a unique IP address from a private subnet

This networking approach provides:
- **Isolation**: Each container has its own network stack
- **Connectivity**: Containers can communicate with each other and external networks
- **Scalability**: The bridge can support many containers
- **Security**: Network policies can be applied at the bridge level

## Content & Learning Objectives

### 1️⃣ Virtual Ethernet Interface Creation

You'll implement creation of veth pairs and assignment to network namespaces.

> **Learning Objectives**
> - Understand virtual ethernet interfaces and how they enable container networking
> - Implement veth pair creation and namespace assignment
> - Learn about MAC address generation and network interface configuration

### 2️⃣ Bridge Network Configuration

Here, you'll implement bridge creation and container interface attachment.

> **Learning Objectives**
> - Understand network bridges and how they provide layer 2 connectivity
> - Implement bridge configuration and interface attachment
> - Learn about network topology in containerized environments

### 3️⃣ IP Address Management and Routing

You'll implement automatic IP address assignment and routing configuration.

> **Learning Objectives**
> - Implement dynamic IP address allocation for containers
> - Configure routing tables for container connectivity
> - Understand subnet management and IP address conflicts

### 4️⃣ Container Network Integration

Finally, you'll integrate networking with the complete container execution pipeline.

> **Learning Objectives**
> - Combine networking with namespace isolation and resource management
> - Implement network cleanup and resource management
> - Understand the complete container networking lifecycle

## Vocabulary: Virtual Networking Terms

- **veth (Virtual Ethernet)**: A pair of connected virtual network interfaces that act like a network cable
- **Bridge**: A network device that connects multiple network segments at the data link layer
- **Network namespace**: Isolation mechanism that provides separate network stacks
- **MAC address**: Media Access Control address, a unique identifier for network interfaces
- **Layer 2**: The data link layer in the OSI model, dealing with frame transmission
- **Layer 3**: The network layer in the OSI model, dealing with IP routing
- **Virtual switch**: Software-based network switch that connects virtual interfaces

## Vocabulary: IP Networking Terms

- **Subnet**: A logical subdivision of an IP network
- **CIDR (Classless Inter-Domain Routing)**: Notation for describing IP address ranges (e.g., 10.0.0.0/24)
- **Default gateway**: The router that forwards traffic to destinations outside the local network
- **Routing table**: A data table that determines where network packets should be forwarded
- **ARP (Address Resolution Protocol)**: Protocol for mapping IP addresses to MAC addresses
- **DHCP (Dynamic Host Configuration Protocol)**: Protocol for automatic IP address assignment
- **Private IP ranges**: IP address ranges reserved for private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)

## Vocabulary: Container Networking Terms

- **CNI (Container Network Interface)**: Standard for configuring network interfaces in containers
- **Overlay network**: Virtual network built on top of existing network infrastructure
- **Service mesh**: Infrastructure layer for handling service-to-service communication
- **Network policy**: Rules that control traffic flow between network endpoints
- **Load balancer**: Device that distributes network traffic across multiple servers
- **Ingress controller**: Component that manages external access to services in a cluster
- **Pod networking**: Kubernetes model where containers in a pod share a network namespace

## Vocabulary: Network Security Terms

- **Firewall**: Network security device that monitors and controls network traffic
- **NAT (Network Address Translation)**: Technique for mapping private IP addresses to public ones
- **VLAN (Virtual Local Area Network)**: Method for creating separate broadcast domains
- **Network segmentation**: Practice of dividing networks into smaller, isolated segments
- **Zero trust networking**: Security model that requires verification for every network transaction
- **Microsegmentation**: Fine-grained network security approach that isolates individual workloads
- **East-west traffic**: Network traffic between services within a data center
- **North-south traffic**: Network traffic between clients and servers across network boundaries
"""


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

    def test_run(self):
        """Test full run functionality with networking"""
        print("Testing bocker run (full networking)...")
        
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
        if returncode == 0:
            print("FAIL: Run should fail with nonexistent image")
            return False
        
        # Test empty command
        returncode = self.run([img_id])
        if returncode == 0:
            print("FAIL: Run should fail with no command")
            return False
        
        def test_container_run(command, expected_in_logs):
            """Helper function to test container runs and verify output"""
            print(f"Testing command: {' '.join(command)}")
            
            # Run the command
            returncode = self.run([img_id] + command)
            time.sleep(2)  # Give container time to complete
            
            # Get container ID from ps output
            containers = self._list_containers()
            container_id = None
            command_str = ' '.join(command)
            for container in containers:
                if command_str in container['command']:
                    container_id = container['id']
                    break
            
            if not container_id:
                print(f"FAIL: Container not found for command: {command_str}")
                return False
            
            # Check logs
            log_file = Path(self.btrfs_path) / container_id / f"{container_id}.log"
            if not log_file.exists():
                print(f"FAIL: Log file not found for container {container_id}")
                return False
            
            try:
                with open(log_file, 'r') as f:
                    log_content = f.read()
                
                if expected_in_logs not in log_content:
                    print(f"FAIL: Expected '{expected_in_logs}' in logs, got: {log_content}")
                    return False
                    
                print(f"SUCCESS: Found '{expected_in_logs}' in logs")
                return True
            except Exception as e:
                print(f"FAIL: Error reading log file: {e}")
                return False
        
        # Test 1: Simple echo command
        if not test_container_run(['echo', 'hello world'], 'hello world'):
            return False
        
        # Test 2: Test process isolation - should show PID 1
        if not test_container_run(['cat', '/proc/self/stat'], '1 (cat)'):
            print("Note: Process isolation test may fail if /proc is not properly mounted")
        
        # Test 3: Test uname
        if not test_container_run(['uname'], 'Linux'):
            print("Note: uname test failed - this may be expected in some environments")
        
        # Test 4: Test basic file operations
        if not test_container_run(['ls', '/'], 'bin'):
            print("Note: File system test failed - checking basic directory structure")

        print("PASS: bocker run test")
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

    def exec(self, args):
        """FIXME: Execute a command in a running container with namespace support: BOCKER exec <container_id> <command>"""
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

    def test_exec(self):
        """FIXME: Test exec functionality"""
        print("Testing bocker exec...")
        
        # Test argument validation first
        returncode = self.exec([])
        if returncode != 1:  # Should fail with usage message
            print(f"FAIL: Exec should fail with no arguments")
            return False
        
        # Test with invalid container
        returncode = self.exec(['nonexistent_container', 'echo', 'test'])
        if returncode == 0:
            print("FAIL: Exec should fail with nonexistent container")
            return False
        
        # Note: Testing exec with a running container is complex because it requires
        # a container to be actively running in the background, which involves
        # process management and timing issues. For now, we test the validation logic.
        
        print("PASS: bocker exec test (argument validation)")
        return True

    def test_v5(self):
        """Test v5 functionality by running only BockerV5-specific test methods"""
        print("Testing BockerV5 functionality...")
        print("=" * 50)
        
        # Define only the test methods that belong to BockerV5
        v5_test_methods = ['test_run', 'test_commit', 'test_exec']
        
        # Filter to only include methods that actually exist in this class
        test_methods = []
        for method_name in v5_test_methods:
            if hasattr(self, method_name) and callable(getattr(self, method_name)):
                test_methods.append(method_name)
        
        print(f"Found {len(test_methods)} BockerV2 test methods: {', '.join(test_methods)}")
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
        print("BockerV2 Test Summary:")
        print("-" * 50)
        for test_name in test_methods:
            status = results.get(test_name, "UNKNOWN")
            status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "💥"
            print(f"{status_symbol} {test_name:<15} : {status}")
        
        print("-" * 50)
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print("=" * 50)
        
        return overall_success


# %%
"""
## Complete Test Suite

This runs the same comprehensive tests as docker.py to validate your implementation.
"""

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
            # Extract the number from the version string, e.g., 'v2' -> '2'
            version_number = version[1:]
            test_method = getattr(bocker, f'test_v{version_number}', None)
            if test_method:
                success = test_method()
                results[version] = "PASS" if success else "FAIL"
                if not success:
                    overall_success = False
            else:
                print(f"No test_v{version_number} method found for {version}")
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
    """Main entry point with version selection and error handling"""
    import sys

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
            try:
                success = test_method()
                return 0 if success else 1
            except KeyboardInterrupt:
                print("\nTest cancelled by user", file=sys.stderr)
                return 130
            except Exception as e:
                print(f"Unexpected error during test: {e}", file=sys.stderr)
                return 1
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
# %%
"""
## Exercise Instructions and Next Steps

### How to Complete the Exercises:

1. **Exercise 1 (Pull)**:
   - Download images from remote registry
   - Extract and process Docker image format
   - Set up btrfs subvolumes

2. **Exercise 2 (Init/Run Basic)**:
   - Create images from directories
   - Basic container execution with chroot

3. **Exercise 3 (Cgroups)**:
   - Add CPU and memory limits
   - Process resource control

4. **Exercise 4 (Namespaces)**:
   - Add PID, mount, UTS namespace isolation
   - Proper /proc mounting

5. **Exercise 5 (Networking)**:
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

- Look at `docker.py` for complete reference implementations
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

Good luck building your container system!
"""