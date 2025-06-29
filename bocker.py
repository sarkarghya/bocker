"""
Python implementation of Bocker with comprehensive test coverage.
"""

# %%
import subprocess
import os
import json
import uuid
import random
import re
import shutil
import tempfile
import sys
import time
from pathlib import Path

def bash_command(command):
    """
    Execute a bash command and return its output.

    Args:
        command (str): The bash command to execute

    Returns:
        str: The stdout output from the command

    Raises:
        subprocess.CalledProcessError: If the command returns non-zero exit code
    """
    try:
        result = subprocess.run(
            ['bash', '-c', command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        # You can handle errors differently if needed
        # For example, return stderr or raise the exception
        return "Error: {}".format(e.stderr)

# %%

class Bocker:
    def __init__(self, btrfs_path='/var/bocker', cgroups='cpu,cpuacct,memory'):
        self.btrfs_path = btrfs_path
        self.cgroups = cgroups
        
    def bocker_check(self, name):
        """Check if a subvolume exists"""
        try:
            bash_command("btrfs subvolume list '{}' | grep -qw '{}'".format(self.btrfs_path, name))
            return 0
        except:
            return 1

    def bocker_init(self, directory):
        """Create an image from a directory"""
        uuid_val = "img_{}".format(random.randint(42002, 42254))
        
        if not os.path.isdir(directory):
            print("No directory named '{}' exists".format(directory))
            return None
            
        if self.bocker_check(uuid_val) == 0:
            return self.bocker_run(directory)
            
        # Create btrfs subvolume
        bash_command("btrfs subvolume create '{}/{}' > /dev/null".format(self.btrfs_path, uuid_val))
        
        # Copy files with reflink
        bash_command("cp -rf --reflink=auto '{}'/* '{}/{}' > /dev/null".format(directory, self.btrfs_path, uuid_val))
        
        # Create img.source file if it doesn't exist
        img_source_path = "{}/{}/img.source".format(self.btrfs_path, uuid_val)
        if not os.path.exists(img_source_path):
            with open(img_source_path, 'w') as f:
                f.write(directory)
                
        print("Created: {}".format(uuid_val))
        return uuid_val

    def bocker_pull(self, name, tag):
        """Pull an image from Docker Hub"""
        tmp_uuid = str(uuid.uuid4())
        tmp_dir = "/tmp/{}".format(tmp_uuid)
        os.makedirs(tmp_dir)
        
        try:
            # Download image (this will show progress)
            subprocess.run(['./download-frozen-image-v2.sh', tmp_dir, '{}:{}'.format(name, tag)], 
                         stdout=None, stderr=subprocess.DEVNULL)
            
            # Remove repositories
            repositories_path = "{}/repositories".format(tmp_dir)
            if os.path.exists(repositories_path):
                shutil.rmtree(repositories_path)
            
            # Extract layers
            manifest_path = "{}/manifest.json".format(tmp_dir)
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                
            for item in manifest:
                for layer in item.get('Layers', []):
                    bash_command("tar xf '{}/{}' -C '{}'".format(tmp_dir, layer, tmp_dir))
                    os.remove("{}/{}".format(tmp_dir, layer))
                    
                # Remove config files
                config = item.get('Config')
                if config:
                    config_path = "{}/{}".format(tmp_dir, config)
                    if os.path.exists(config_path):
                        os.remove(config_path)
            
            # Create img.source
            with open("{}/img.source".format(tmp_dir), 'w') as f:
                f.write("{}:{}".format(name, tag))
                
            return self.bocker_init(tmp_dir)
            
        finally:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)

    def bocker_rm(self, container_id):
        """Delete an image or container"""
        if self.bocker_check(container_id) == 1:
            print("No container named '{}' exists".format(container_id))
            sys.exit(1)
            
        # Delete btrfs subvolume
        bash_command("btrfs subvolume delete '{}/{}' > /dev/null".format(self.btrfs_path, container_id))
        
        # Delete cgroup
        try:
            bash_command("cgdelete -g '{}:/{}' &> /dev/null".format(self.cgroups, container_id))
        except:
            pass
            
        print("Removed: {}".format(container_id))

    def bocker_images(self):
        """List images"""
        print("IMAGE_ID\t\tSOURCE")
        
        btrfs_path = Path(self.btrfs_path)
        for img_path in btrfs_path.glob("img_*"):
            img_name = img_path.name
            source_file = img_path / "img.source"
            if source_file.exists():
                with open(source_file, 'r') as f:
                    source = f.read().strip()
                print(f"{img_name}\t\t{source}")

    def bocker_ps(self):
        """List containers"""
        print("CONTAINER_ID\t\tCOMMAND")
        
        btrfs_path = Path(self.btrfs_path)
        for ps_path in btrfs_path.glob("ps_*"):
            ps_name = ps_path.name
            cmd_file = ps_path / f"{ps_name}.cmd"
            if cmd_file.exists():
                with open(cmd_file, 'r') as f:
                    command = f.read().strip()
                print(f"{ps_name}\t\t{command}")

    def bocker_run(self, image_id, *command):
        """Create a container"""
        uuid_val = "ps_{}".format(random.randint(42002, 42254))
        
        if self.bocker_check(image_id) == 1:
            print("No image named '{}' exists".format(image_id))
            sys.exit(1)
            
        if self.bocker_check(uuid_val) == 0:
            print("UUID conflict, retrying...")
            return self.bocker_run(image_id, *command)
            
        cmd = ' '.join(command)
        ip_suffix = uuid_val[-3:].lstrip('0') or '1'
        mac_suffix = "{}:{}".format(uuid_val[-3:-2], uuid_val[-2:])
        
        try:
            # Network setup
            bash_command("ip link add dev veth0_{} type veth peer name veth1_{}".format(uuid_val, uuid_val))
            bash_command("ip link set dev veth0_{} up".format(uuid_val))
            bash_command("ip link set veth0_{} master bridge0".format(uuid_val))
            bash_command("ip netns add netns_{}".format(uuid_val))
            bash_command("ip link set veth1_{} netns netns_{}".format(uuid_val, uuid_val))
            bash_command("ip netns exec netns_{} ip link set dev lo up".format(uuid_val))
            bash_command("ip netns exec netns_{} ip link set veth1_{} address 02:42:ac:11:00:{}".format(uuid_val, uuid_val, mac_suffix))
            bash_command("ip netns exec netns_{} ip addr add 10.0.0.{}/24 dev veth1_{}".format(uuid_val, ip_suffix, uuid_val))
            bash_command("ip netns exec netns_{} ip link set dev veth1_{} up".format(uuid_val, uuid_val))
            bash_command("ip netns exec netns_{} ip route add default via 10.0.0.1".format(uuid_val))
            
            # Filesystem setup
            bash_command("btrfs subvolume snapshot '{}/{}' '{}/{}' > /dev/null".format(self.btrfs_path, image_id, self.btrfs_path, uuid_val))
            
            # Setup resolv.conf
            resolv_conf_path = "{}/{}/etc/resolv.conf".format(self.btrfs_path, uuid_val)
            os.makedirs(os.path.dirname(resolv_conf_path), exist_ok=True)
            with open(resolv_conf_path, 'w') as f:
                f.write('nameserver 8.8.8.8\n')
                
            # Save command
            with open("{}/{}/{}.cmd".format(self.btrfs_path, uuid_val, uuid_val), 'w') as f:
                f.write(cmd)
            
            # Cgroup setup
            bash_command("cgcreate -g '{}:/{}'".format(self.cgroups, uuid_val))
            
            # Get CPU and memory limits from environment variables
            cpu_share = os.environ.get('BOCKER_CPU_SHARE', '512')
            bash_command("cgset -r cpu.shares={} {}".format(cpu_share, uuid_val))
            
            mem_limit = os.environ.get('BOCKER_MEM_LIMIT', '512')
            mem_bytes = int(mem_limit) * 1000000
            bash_command("cgset -r memory.limit_in_bytes={} {}".format(mem_bytes, uuid_val))
            
            # Execute container
            exec_cmd = """cgexec -g '{}:{}' \
ip netns exec netns_{} \
unshare -fmuip --mount-proc \
chroot '{}/{}' \
/bin/sh -c "/bin/mount -t proc proc /proc && {}" """.format(self.cgroups, uuid_val, uuid_val, self.btrfs_path, uuid_val, cmd)
            
            # Run the command and capture output to log file
            result = subprocess.run(['bash', '-c', exec_cmd], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            # Write output to log file
            with open("{}/{}/{}.log".format(self.btrfs_path, uuid_val, uuid_val), 'w') as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write(result.stderr)
            
            # Print output to console
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())
                
            return uuid_val
            
        finally:
            # Cleanup network
            try:
                bash_command("ip link del dev veth0_{}".format(uuid_val))
                bash_command("ip netns del netns_{}".format(uuid_val))
            except:
                pass

    def bocker_exec(self, container_id, *command):
        """Execute a command in a running container"""
        if self.bocker_check(container_id) == 1:
            print("No container named '{}' exists".format(container_id))
            sys.exit(1)
            
        # Find container PID
        try:
            pid_cmd = "ps o ppid,pid | grep \"^$(ps o pid,cmd | grep -E \"^\ *[0-9]+ unshare.*{}\" | awk '{{print $1}}')\" | awk '{{print $2}}'".format(container_id)
            cid = bash_command(pid_cmd).strip()
            
            if not re.match(r'^\s*[0-9]+$', cid):
                print("Container '{}' exists but is not running".format(container_id))
                sys.exit(1)
                
            cmd = ' '.join(command)
            result = bash_command("nsenter -t {} -m -u -i -n -p chroot '{}/{}' {}".format(cid, self.btrfs_path, container_id, cmd))
            print(result.strip())
            
        except Exception as e:
            print("Error executing command: {}".format(e))

    def bocker_logs(self, container_id):
        """View logs from a container"""
        if self.bocker_check(container_id) == 1:
            print("No container named '{}' exists".format(container_id))
            sys.exit(1)
            
        log_file = "{}/{}/{}.log".format(self.btrfs_path, container_id, container_id)
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                return f.read().strip()
        return ""

    def bocker_commit(self, container_id, image_id):
        """Commit a container to an image"""
        if self.bocker_check(container_id) == 1:
            print("No container named '{}' exists".format(container_id))
            sys.exit(1)
            
        if self.bocker_check(image_id) == 0:
            self.bocker_rm(image_id)
            
        bash_command("btrfs subvolume snapshot '{}/{}' '{}/{}' > /dev/null".format(self.btrfs_path, container_id, self.btrfs_path, image_id))
        print("Created: {}".format(image_id))

    def bocker_help(self, script_name):
        """Display help message"""
        help_text = f"""
{script_name} - A simple container runtime

Commands:
    init               Create an image from a directory
    pull              Pull an image from Docker Hub
    rm    Delete an image or container
    images                       List images
    ps                          List containers
    run      Create a container
    exec     Execute a command in a running container
    logs          View logs from a container
    commit   Commit a container to an image
    help                        Display this message
        """
        print(help_text)

def main():
    """Main function to handle command line arguments"""
    bocker = Bocker()
    args = sys.argv[1:]
    
    if not args:
        bocker.bocker_help(sys.argv)
        return
        
    command = args
    command_args = args[1:]
    
    commands = {
        'pull': lambda: bocker.bocker_pull(*command_args),
        'init': lambda: bocker.bocker_init(*command_args),
        'rm': lambda: bocker.bocker_rm(*command_args),
        'images': lambda: bocker.bocker_images(),
        'ps': lambda: bocker.bocker_ps(),
        'run': lambda: bocker.bocker_run(*command_args),
        'exec': lambda: bocker.bocker_exec(*command_args),
        'logs': lambda: bocker.bocker_logs(*command_args),
        'commit': lambda: bocker.bocker_commit(*command_args),
        'help': lambda: bocker.bocker_help(sys.argv)
    }
    
    if command in commands:
        commands[command]()
    else:
        bocker.bocker_help(sys.argv)

if __name__ == "__main__":
    main()

# %%

class BockerTestSuite:
    """Comprehensive test suite for Bocker functionality"""
    
    def __init__(self, base_image_path="~/base-image"):
        self.bocker = Bocker()
        self.base_image_path = os.path.expanduser(base_image_path)
        self.test_results = []
        
    def log_test(self, test_name, passed, message=""):
        """Log test results"""
        status = "PASS" if passed else "FAIL"
        self.test_results.append(f"{test_name}: {status} {message}")
        print(f"[{status}] {test_name}: {message}")
        
    def teardown(self):
        """Clean up all images and containers"""
        print("Running teardown...")
        
        # Get all images
        try:
            result = subprocess.run(['python3', 'bocker.py', 'images'], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip() and 'img_' in line:
                    img_id = line.split()[0]  # Take first element
                    subprocess.run(['python3', 'bocker.py', 'rm', img_id], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            pass
            
        # Get all containers
        try:
            result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip() and 'ps_' in line:
                    ps_id = line.split()[0]  # Take first element
                    subprocess.run(['python3', 'bocker.py', 'rm', ps_id], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            pass
            
    def test_images_header(self):
        """Test that images command shows correct header"""
        result = subprocess.run(['python3', 'bocker.py', 'images'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        header = result.stdout.split('\n')
        expected = "IMAGE_ID\t\tSOURCE"
        passed = header and expected in header
        self.log_test("test_images_header", passed, f"Expected: {expected}")
        return passed
        
    def test_ps_header(self):
        """Test that ps command shows correct header"""
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        header = result.stdout.split('\n')
        expected = "CONTAINER_ID\t\tCOMMAND"
        passed = header and expected in header
        self.log_test("test_ps_header", passed, f"Expected: {expected}")
        return passed
        
    def test_init(self):
        """Test image initialization"""
        if not os.path.exists(self.base_image_path):
            self.log_test("test_init", False, f"Base image path {self.base_image_path} does not exist")
            return False
            
        result = subprocess.run(['python3', 'bocker.py', 'init', self.base_image_path], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        passed = result.stdout.startswith('Created: img_')
        self.log_test("test_init", passed, result.stdout.strip())
        return passed
        
    def bocker_run_test(self, img_id, command, expected_output):
        """Helper function to test bocker container runs"""
        subprocess.run(['python3', 'bocker.py', 'run', img_id, command], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(3)
        
        # Get container ID
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ps_id = None
        for line in result.stdout.split('\n')[1:]:
            if command in line:
                ps_id = line.split()[0]
                break
                
        if not ps_id:
            return False
            
        # Get logs
        result = subprocess.run(['python3', 'bocker.py', 'logs', ps_id], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logs = result.stdout
        
        return expected_output in logs
        
    def test_run_comprehensive(self):
        """Comprehensive test of run functionality"""
        # Initialize image
        result = subprocess.run(['python3', 'bocker.py', 'init', self.base_image_path], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not result.stdout.startswith('Created: img_'):
            self.log_test("test_run_comprehensive", False, "Failed to create image")
            return False
            
        img_id = result.stdout.split()[-1]
        time.sleep(4)
        
        # Verify image exists
        result = subprocess.run(['python3', 'bocker.py', 'images'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if img_id not in result.stdout:
            self.log_test("test_run_comprehensive", False, "Image not found in images list")
            return False
            
        # Test 1: echo foo
        test1 = self.bocker_run_test(img_id, 'echo foo', 'foo')
        self.log_test("test_run_echo", test1, "echo foo test")
        
        # Test 2: uname
        test2 = self.bocker_run_test(img_id, 'uname', 'Linux')
        self.log_test("test_run_uname", test2, "uname test")
        
        # Test 3: Process isolation
        test3 = self.bocker_run_test(img_id, 'cat /proc/self/stat', '1 (cat)')
        self.log_test("test_run_process_isolation", test3, "process isolation test")
        
        return test1 and test2 and test3
        
    def test_commit_workflow(self):
        """Test the complete commit workflow"""
        # Initialize image
        result = subprocess.run(['python3', 'bocker.py', 'init', self.base_image_path], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not result.stdout.startswith('Created: img_'):
            self.log_test("test_commit_workflow", False, "Failed to create image")
            return False
            
        img_id = result.stdout.split()[-1]
        time.sleep(1)
        
        # Test wget command (should fail)
        subprocess.run(['python3', 'bocker.py', 'run', img_id, 'wget'], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Get container ID for wget test
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        wget_ps = None
        for line in result.stdout.split('\n')[1:]:
            if 'wget' in line:
                wget_ps = line.split()[0]
                break
                
        if wget_ps:
            # Check logs
            result = subprocess.run(['python3', 'bocker.py', 'logs', wget_ps], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            wget_failed = "command not found" in result.stdout or "not found" in result.stdout
            self.log_test("test_wget_initially_fails", wget_failed, "wget should fail initially")
            
            # Clean up
            subprocess.run(['python3', 'bocker.py', 'rm', wget_ps], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Install wget
        subprocess.run(['python3', 'bocker.py', 'run', img_id, 'yum', 'install', '-y', 'wget'], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Get container ID for yum install
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        yum_ps = None
        for line in result.stdout.split('\n')[1:]:
            if 'yum install -y wget' in line:
                yum_ps = line.split()[0]
                break
                
        if not yum_ps:
            self.log_test("test_commit_workflow", False, "Could not find yum install container")
            return False
            
        # Commit changes
        subprocess.run(['python3', 'bocker.py', 'commit', yum_ps, img_id], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Test wget again (should work now)
        subprocess.run(['python3', 'bocker.py', 'run', img_id, 'wget', '-qO-', 'http://httpbin.org/get'], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Get container ID for wget test
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        wget_success_ps = None
        for line in result.stdout.split('\n')[1:]:
            if 'wget -qO- http://httpbin.org/get' in line:
                wget_success_ps = line.split()[0]
                break
                
        if wget_success_ps:
            result = subprocess.run(['python3', 'bocker.py', 'logs', wget_success_ps], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            wget_success = 'http://httpbin.org/get' in result.stdout
            self.log_test("test_wget_after_install", wget_success, "wget should work after install")
            return wget_success
            
        return False
        
    def test_pull_workflow(self):
        """Test pulling images from Docker Hub"""
        # Pull CentOS 7
        result = subprocess.run(['python3', 'bocker.py', 'pull', 'centos', '7'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if 'Created: img_' not in result.stdout:
            self.log_test("test_pull_centos", False, "Failed to pull CentOS image")
            return False
            
        centos_img = result.stdout.split()[-1]
        
        # Test CentOS release
        subprocess.run(['python3', 'bocker.py', 'run', centos_img, 'cat', '/etc/redhat-release'], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Get container and check logs
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ps_id = None
        for line in result.stdout.split('\n')[1:]:
            if 'cat /etc/redhat-release' in line:
                ps_id = line.split()[0]
                break
                
        if ps_id:
            result = subprocess.run(['python3', 'bocker.py', 'logs', ps_id], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            centos_test = 'CentOS Linux release 7' in result.stdout
            self.log_test("test_pull_centos", centos_test, "CentOS version check")
            
            # Clean up
            subprocess.run(['python3', 'bocker.py', 'rm', ps_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return centos_test
            
        return False
        
    def test_rm_functionality(self):
        """Test removal of images and containers"""
        # Create image
        result = subprocess.run(['python3', 'bocker.py', 'init', self.base_image_path], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not result.stdout.startswith('Created: img_'):
            self.log_test("test_rm_functionality", False, "Failed to create image")
            return False
            
        img_id = result.stdout.split()[-1]
        
        # Create container
        cmd = f"echo {random.randint(1000, 9999)}"
        subprocess.run(['python3', 'bocker.py', 'run', img_id] + cmd.split(), 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Get container ID
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ps_id = None
        for line in result.stdout.split('\n')[1:]:
            if cmd in line:
                ps_id = line.split()[0]
                break
                
        if not ps_id:
            self.log_test("test_rm_functionality", False, "Could not find container")
            return False
            
        # Verify they exist
        result = subprocess.run(['python3', 'bocker.py', 'images'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        img_exists_before = img_id in result.stdout
        
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ps_exists_before = cmd in result.stdout
        
        # Remove them
        subprocess.run(['python3', 'bocker.py', 'rm', img_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['python3', 'bocker.py', 'rm', ps_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Verify they're gone
        result = subprocess.run(['python3', 'bocker.py', 'images'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        img_exists_after = img_id in result.stdout
        
        result = subprocess.run(['python3', 'bocker.py', 'ps'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ps_exists_after = cmd in result.stdout
        
        success = (img_exists_before and ps_exists_before and 
                  not img_exists_after and not ps_exists_after)
        
        self.log_test("test_rm_functionality", success, 
                     f"Before: img={img_exists_before}, ps={ps_exists_before}; "
                     f"After: img={img_exists_after}, ps={ps_exists_after}")
        
        return success
        
    def run_all_tests(self):
        """Run all tests in the suite"""
        print("Starting Bocker Test Suite...")
        print("=" * 50)
        
        # Run teardown first to clean slate
        self.teardown()
        
        tests = [
            self.test_images_header,
            self.test_ps_header,
            self.test_init,
            self.test_run_comprehensive,
            self.test_commit_workflow,
            self.test_rm_functionality,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
            except Exception as e:
                self.log_test(test.__name__, False, f"Exception: {e}")
                
        # Final teardown
        self.teardown()
        
        print("=" * 50)
        print(f"Test Results: {passed}/{total} tests passed")
        print("=" * 50)
        
        for result in self.test_results:
            print(result)
            
        return passed == total

# %%

def test_bocker_comprehensive():
    """
    Run comprehensive tests for Bocker functionality.
    """
    test_suite = BockerTestSuite()
    success = test_suite.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! Bocker implementation is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        
    return success

# Run the comprehensive test suite
test_bocker_comprehensive()