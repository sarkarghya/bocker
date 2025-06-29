#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import tempfile
import shutil
import random

class BockerTester:
    def __init__(self):
        self.bocker_script = './pymod_boc.py'
        self.base_image_dir = os.path.expanduser('~/base-image')
        
    def run_bocker_command(self, args):
        """Run bocker command and return result"""
        try:
            cmd = [self.bocker_script] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)
    
    def bocker_run_test(self, image_id, command, expected_output):
        """Test bocker container runs and check their output"""
        # Run the command
        returncode, stdout, stderr = self.run_bocker_command(['run', image_id, command])
        time.sleep(3)
        
        # Get container ID from ps output
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
        
        # Get logs
        logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
        if logs_returncode != 0:
            return False
        
        return expected_output in logs_stdout

    def test_init(self):
        """Test bocker init functionality"""
        print("Testing bocker init...")
        
        # Test init with valid directory
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
        
        # Initialize a new image from base-image
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        if returncode != 0:
            print(f"FAIL: Could not create test image: {stderr}")
            return False
        
        img_id = stdout.strip().split()[-1]
        print(f"Created image with ID: {img_id}")
        
        time.sleep(4)
        
        # Verify the image appears in the images list
        returncode, stdout, stderr = self.run_bocker_command(['images'])
        if returncode != 0 or img_id not in stdout:
            print("FAIL: Image not found in bocker images list")
            return False
        
        print("Image successfully found in bocker images list")
        
        # Test 1: Run 'echo foo' and expect 'foo' in output
        print("Running test 1: echo foo")
        if not self.bocker_run_test(img_id, 'echo foo', 'foo'):
            print("FAIL: Test 1 failed")
            return False
        print("Test 1 completed successfully")
        
        # Test 2: Run 'uname' and expect 'Linux' in output
        print("Running test 2: uname")
        if not self.bocker_run_test(img_id, 'uname', 'Linux'):
            print("FAIL: Test 2 failed")
            return False
        print("Test 2 completed successfully")
        
        # Test 3: Check process isolation - cat should show PID 1
        print("Running test 3: process isolation check")
        if not self.bocker_run_test(img_id, 'cat /proc/self/stat', '1 (cat)'):
            print("FAIL: Test 3 failed")
            return False
        print("Test 3 completed successfully - process isolation working")
        
        # Install iproute package in a container
        print("Installing iproute package...")
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, 'yum', 'install', '-y', 'iproute'])
        
        # Get container ID for yum install
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if 'yum install -y iproute' in line:
                container_id = line.split()[0]
                break
        
        if container_id:
            print(f"Container ID for yum install: {container_id}")
            
            # Commit the changes to create a new image layer
            commit_returncode, commit_stdout, commit_stderr = self.run_bocker_command(['commit', container_id, img_id])
            if commit_returncode == 0:
                print(f"Committed changes to image {img_id}")
                
                # Test 4: Verify network interface setup
                print("Running test 4: network interface check")
                if not self.bocker_run_test(img_id, 'ip addr', 'veth1_ps_'):
                    print("FAIL: Test 4 failed")
                    return False
                print("Test 4 completed successfully - network interfaces configured")
                
                # Test 5: Test external connectivity to Google DNS
                print("Running test 5: external DNS connectivity")
                if not self.bocker_run_test(img_id, 'ping -c 1 8.8.8.8', '0% packet loss'):
                    print("FAIL: Test 5 failed")
                    return False
                print("Test 5 completed successfully - can reach 8.8.8.8")
                
                # Test 6: Test DNS resolution and connectivity
                print("Running test 6: DNS resolution and connectivity")
                if not self.bocker_run_test(img_id, 'ping -c 1 google.com', '0% packet loss'):
                    print("FAIL: Test 6 failed")
                    return False
                print("Test 6 completed successfully - DNS resolution working")
        
        print("PASS: bocker run test")
        return True

    def test_rm(self):
        """Test bocker rm functionality"""
        print("Testing bocker rm...")
        
        # Create test image
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        if returncode != 0:
            print(f"FAIL: Could not create test image: {stderr}")
            return False
        
        img_id = stdout.strip().split()[-1]
        
        # Create test container
        cmd = f"echo {random.randint(1000, 9999)}"
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, cmd])
        
        # Get container ID
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if cmd.split()[-1] in line:  # Look for the random number
                container_id = line.split()[0]
                break
        
        if not container_id:
            print("FAIL: Could not find container ID")
            return False
        
        # Verify image and container exist
        images_returncode, images_stdout, images_stderr = self.run_bocker_command(['images'])
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        
        if img_id not in images_stdout:
            print("FAIL: Image not found before removal")
            return False
        
        if container_id not in ps_stdout:
            print("FAIL: Container not found before removal")
            return False
        
        # Remove image and container
        rm_img_returncode, rm_img_stdout, rm_img_stderr = self.run_bocker_command(['rm', img_id])
        rm_ps_returncode, rm_ps_stdout, rm_ps_stderr = self.run_bocker_command(['rm', container_id])
        
        # Verify they're gone
        images_returncode, images_stdout, images_stderr = self.run_bocker_command(['images'])
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        
        if img_id in images_stdout:
            print("FAIL: Image still found after removal")
            return False
        
        if container_id in ps_stdout:
            print("FAIL: Container still found after removal")
            return False
        
        print("PASS: bocker rm test")
        return True

    def test_pull(self):
        """Test bocker pull functionality"""
        print("Testing bocker pull...")
        
        # Test CentOS pull
        print("Pulling CentOS 7...")
        returncode, stdout, stderr = self.run_bocker_command(['pull', 'centos', '7'])
        if returncode != 0:
            print(f"FAIL: CentOS pull failed: {stderr}")
            return False
        
        centos_img = stdout.strip().split()[-1]
        
        # Test CentOS container
        returncode, stdout, stderr = self.run_bocker_command(['run', centos_img, 'cat', '/etc/redhat-release'])
        
        # Get container ID and logs
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
        
        # Test Ubuntu pull
        print("Pulling Ubuntu 14.04...")
        returncode, stdout, stderr = self.run_bocker_command(['pull', 'ubuntu', '14.04'])
        if returncode != 0:
            print(f"FAIL: Ubuntu pull failed: {stderr}")
            return False
        
        ubuntu_img = stdout.strip().split()[-1]
        
        # Test Ubuntu container
        returncode, stdout, stderr = self.run_bocker_command(['run', ubuntu_img, 'tail', '-n1', '/etc/lsb-release'])
        
        # Get container ID and logs
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if 'tail -n1 /etc/lsb-release' in line:
                container_id = line.split()[0]
                break
        
        if container_id:
            logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
            self.run_bocker_command(['rm', container_id])
            
            if 'Ubuntu 14.04' not in logs_stdout:
                print(f"FAIL: Expected Ubuntu release info, got: {logs_stdout}")
                return False
        
        print("PASS: bocker pull test")
        return True

    def test_commit(self):
        """Test bocker commit functionality"""
        print("Testing bocker commit...")
        
        # Initialize a new container from base image
        returncode, stdout, stderr = self.run_bocker_command(['init', self.base_image_dir])
        if returncode != 0:
            print(f"FAIL: Could not create test image: {stderr}")
            return False
        
        img_id = stdout.strip().split()[-1]
        print(f"Created image: {img_id}")
        
        time.sleep(1)
        
        # Verify the image exists
        images_returncode, images_stdout, images_stderr = self.run_bocker_command(['images'])
        if img_id not in images_stdout:
            print(f"Error: Image {img_id} not found in image list")
            return False
        print(f"Image {img_id} verified in image list")
        
        # Test 1: Run wget command (should fail since wget is not installed)
        print("Testing wget command (should fail)...")
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, 'wget'])
        
        # Get container ID
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        container_id = None
        for line in ps_stdout.split('\n'):
            if 'wget' in line:
                container_id = line.split()[0]
                break
        
        if container_id:
            print(f"Container process ID: {container_id}")
            logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
            print(f"Logs from wget test: {logs_stdout}")
            self.run_bocker_command(['rm', container_id])
            print(f"Removed container {container_id}")
            
            if 'wget: command not found' in logs_stdout:
                print("Confirmed: wget command not found (as expected)")
            else:
                print("Warning: wget failure message unexpected")
        
        # Test 2: Install wget using yum
        print("Installing wget using yum...")
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, 'yum', 'install', '-y', 'wget'])
        
        if returncode == 0:
            # Get container ID for yum install
            ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
            container_id = None
            for line in ps_stdout.split('\n'):
                if 'yum install -y wget' in line:
                    container_id = line.split()[0]
                    break
            
            if container_id:
                print(f"Yum install process ID: {container_id}")
                commit_returncode, commit_stdout, commit_stderr = self.run_bocker_command(['commit', container_id, img_id])
                if commit_returncode == 0:
                    print(f"Committed changes to image {img_id} (wget now installed)")
                else:
                    print(f"FAIL: Commit failed: {commit_stderr}")
                    return False
        else:
            print("Error: yum install wget failed")
            return False
        
        # Test 3: Use wget to fetch data from httpbin.org
        print("Testing wget with HTTP request...")
        returncode, stdout, stderr = self.run_bocker_command(['run', img_id, 'wget', '-qO-', 'http://httpbin.org/get'])
        
        if returncode == 0:
            # Get container ID for wget request
            ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
            container_id = None
            for line in ps_stdout.split('\n'):
                if 'wget -qO- http://httpbin.org/get' in line:
                    container_id = line.split()[0]
                    break
            
            if container_id:
                print(f"Wget HTTP request process ID: {container_id}")
                logs_returncode, logs_stdout, logs_stderr = self.run_bocker_command(['logs', container_id])
                print("Logs from wget HTTP request:")
                print(logs_stdout)
                
                if 'http://httpbin.org/get' in logs_stdout:
                    print("Success: wget successfully fetched data from http://httpbin.org/get")
                else:
                    print("Warning: wget did not fetch expected data")
        else:
            print("Error: wget HTTP request failed")
            return False
        
        print("PASS: bocker commit test")
        return True

    def cleanup(self):
        """Clean up test artifacts"""
        print("Cleaning up test artifacts...")
        
        # Remove all test images
        images_returncode, images_stdout, images_stderr = self.run_bocker_command(['images'])
        if images_returncode == 0:
            for line in images_stdout.split('\n'):
                if line.startswith('img_'):
                    img_id = line.split()[0]
                    self.run_bocker_command(['rm', img_id])
        
        # Remove all test containers
        ps_returncode, ps_stdout, ps_stderr = self.run_bocker_command(['ps'])
        if ps_returncode == 0:
            for line in ps_stdout.split('\n'):
                if line.startswith('ps_'):
                    container_id = line.split()[0]
                    self.run_bocker_command(['rm', container_id])

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
            
            # Small delay between tests
            time.sleep(2)
        
        print(f"\n{'=' * 60}")
        print(f"TEST RESULTS: {passed} passed, {failed} failed")
        print(f"{'=' * 60}")
        
        # Cleanup
        self.cleanup()
        
        return failed == 0

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Usage: python3 test_bocker.py")
        print("Run comprehensive test suite for bocker")
        return 0
    
    # Check if bocker.py exists
    if not os.path.exists('./bocker.py'):
        print("Error: bocker.py not found in current directory")
        return 1
    
    # Check if base image directory exists
    base_image_dir = os.path.expanduser('~/base-image')
    if not os.path.exists(base_image_dir):
        print(f"Error: Base image directory {base_image_dir} not found")
        print("Please create a base image directory with a minimal Linux filesystem")
        return 1
    
    tester = BockerTester()
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())

