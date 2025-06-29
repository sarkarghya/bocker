#!/usr/bin/env python3
import subprocess
import sys
import os
import tempfile
import uuid
import json
import shutil
import time

class BockerWrapper:
    def __init__(self):
        self.btrfs_path = '/var/bocker'
        self.cgroups = 'cpu,cpuacct,memory'
        
    def _run_bash_command(self, bash_script, show_realtime=False):
        """Execute embedded bash commands"""
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
        """Check if container/image exists"""
        bash_script = f"""
        btrfs_path='{self.btrfs_path}'
        btrfs subvolume list "$btrfs_path" | grep -qw "{container_id}" && echo 0 || echo 1
        """
        result = subprocess.run(['bash', '-c', bash_script], capture_output=True, text=True)
        return result.stdout.strip() == '0'

    def pull(self, args):
        """Pull an image from Docker Hub: BOCKER pull <name> <tag>"""
        if len(args) < 2:
            print("Usage: bocker pull <name> <tag>", file=sys.stderr)
            return 1
        
        name, tag = args[0], args[1]
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_init() {{
            uuid="img_$(shuf -i 42002-42254 -n 1)"
            if [[ -d "$1" ]]; then
                [[ "$(bocker_check "$uuid")" == 0 ]] && bocker_run "$@"
                btrfs subvolume create "$btrfs_path/$uuid" > /dev/null
                cp -rf --reflink=auto "$1"/* "$btrfs_path/$uuid" > /dev/null
                [[ ! -f "$btrfs_path/$uuid"/img.source ]] && echo "$1" > "$btrfs_path/$uuid"/img.source
                echo "Created: $uuid"
            else
                echo "No directory named '$1' exists"
            fi
        }}
        
        function bocker_pull() {{
            tmp_uuid="$(uuidgen)" && mkdir /tmp/"$tmp_uuid"
            ./download-frozen-image-v2.sh /tmp/"$tmp_uuid" "$1:$2" > /dev/null
            rm -rf /tmp/"$tmp_uuid"/repositories
            for tar in $(jq '.[].Layers[]' --raw-output < /tmp/$tmp_uuid/manifest.json); do
                tar xf /tmp/$tmp_uuid/$tar -C /tmp/$tmp_uuid && rm -rf /tmp/$tmp_uuid/$tar
            done
            for config in $(jq '.[].Config' --raw-output < /tmp/$tmp_uuid/manifest.json); do
                rm -f /tmp/$tmp_uuid/$config
            done
            echo "$1:$2" > /tmp/$tmp_uuid/img.source
            bocker_init /tmp/$tmp_uuid && rm -rf /tmp/$tmp_uuid
        }}
        
        bocker_pull "{name}" "{tag}"
        """
        return self._run_bash_command(bash_script, show_realtime=True)
    
    def init(self, args):
        """Create an image from a directory: BOCKER init <directory>"""
        if len(args) < 1:
            print("Usage: bocker init <directory>", file=sys.stderr)
            return 1
        
        directory = args[0]
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_init() {{
            uuid="img_$(shuf -i 42002-42254 -n 1)"
            if [[ -d "$1" ]]; then
                [[ "$(bocker_check "$uuid")" == 0 ]] && bocker_run "$@"
                btrfs subvolume create "$btrfs_path/$uuid" > /dev/null
                cp -rf --reflink=auto "$1"/* "$btrfs_path/$uuid" > /dev/null
                [[ ! -f "$btrfs_path/$uuid"/img.source ]] && echo "$1" > "$btrfs_path/$uuid"/img.source
                echo "Created: $uuid"
            else
                echo "No directory named '$1' exists"
            fi
        }}
        
        bocker_init "{directory}"
        """
        return self._run_bash_command(bash_script)
    
    def rm(self, args):
        """Delete an image or container: BOCKER rm <image_id or container_id>"""
        if len(args) < 1:
            print("Usage: bocker rm <image_id or container_id>", file=sys.stderr)
            return 1
        
        container_id = args[0]
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        cgroups='{self.cgroups}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_rm() {{
            [[ "$(bocker_check "$1")" == 1 ]] && echo "No container named '$1' exists" && exit 1
            btrfs subvolume delete "$btrfs_path/$1" > /dev/null
            cgdelete -g "$cgroups:/$1" &> /dev/null || true
            echo "Removed: $1"
        }}
        
        bocker_rm "{container_id}"
        """
        return self._run_bash_command(bash_script)
    
    def images(self, args):
        """List images: BOCKER images"""
        bash_script = f"""
        btrfs_path='{self.btrfs_path}'
        
        function bocker_images() {{
            echo -e "IMAGE_ID\\t\\tSOURCE"
            for img in "$btrfs_path"/img_*; do
                img=$(basename "$img")
                echo -e "$img\\t\\t$(cat "$btrfs_path/$img/img.source")"
            done
        }}
        
        bocker_images
        """
        return self._run_bash_command(bash_script)
    
    def ps(self, args):
        """List containers: BOCKER ps"""
        bash_script = f"""
        btrfs_path='{self.btrfs_path}'
        
        function bocker_ps() {{
            echo -e "CONTAINER_ID\\t\\tCOMMAND"
            for ps in "$btrfs_path"/ps_*; do
                ps=$(basename "$ps")
                echo -e "$ps\\t\\t$(cat "$btrfs_path/$ps/$ps.cmd")"
            done
        }}
        
        bocker_ps
        """
        return self._run_bash_command(bash_script)
    
    def run(self, args):
        """Create a container: BOCKER run <image_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker run <image_id> <command>", file=sys.stderr)
            return 1
        
        image_id = args[0]
        command = ' '.join(args[1:])
        cpu_share = os.environ.get('BOCKER_CPU_SHARE', '512')
        mem_limit = os.environ.get('BOCKER_MEM_LIMIT', '512')
        
        bash_script = f"""
        set -o errexit -o nounset -o pipefail; shopt -s nullglob
        btrfs_path='{self.btrfs_path}'
        cgroups='{self.cgroups}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_run() {{
            uuid="ps_$(shuf -i 42002-42254 -n 1)"
            [[ "$(bocker_check "$1")" == 1 ]] && echo "No image named '$1' exists" && exit 1
            [[ "$(bocker_check "$uuid")" == 0 ]] && echo "UUID conflict, retrying..." && bocker_run "$@" && return
            cmd="${{@:2}}" && ip="$(echo "${{uuid: -3}}" | sed 's/0//g')" && mac="${{uuid: -3:1}}:${{uuid: -2}}"
            
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
            btrfs subvolume snapshot "$btrfs_path/$1" "$btrfs_path/$uuid" > /dev/null
            echo 'nameserver 8.8.8.8' > "$btrfs_path/$uuid"/etc/resolv.conf
            echo "$cmd" > "$btrfs_path/$uuid/$uuid.cmd"
            
            cgcreate -g "$cgroups:/$uuid"
            : "${{BOCKER_CPU_SHARE:={cpu_share}}}" && cgset -r cpu.shares="$BOCKER_CPU_SHARE" "$uuid"
            : "${{BOCKER_MEM_LIMIT:={mem_limit}}}" && cgset -r memory.limit_in_bytes="$((BOCKER_MEM_LIMIT * 1000000))" "$uuid"
            cgexec -g "$cgroups:$uuid" \\
                ip netns exec netns_"$uuid" \\
                unshare -fmuip --mount-proc \\
                chroot "$btrfs_path/$uuid" \\
                /bin/sh -c "/bin/mount -t proc proc /proc && $cmd" \\
                2>&1 | tee "$btrfs_path/$uuid/$uuid.log" || true
            # Cleanup network
            ip link del dev veth0_"$uuid"
            ip netns del netns_"$uuid"
        }}
        
        bocker_run "{image_id}" {command}
        """
        return self._run_bash_command(bash_script, show_realtime=True)
    
    def exec(self, args):
        """Execute a command in a running container: BOCKER exec <container_id> <command>"""
        if len(args) < 2:
            print("Usage: bocker exec <container_id> <command>", file=sys.stderr)
            return 1
        
        container_id = args[0]
        command = ' '.join(args[1:])
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_exec() {{
            [[ "$(bocker_check "$1")" == 1 ]] && echo "No container named '$1' exists" && exit 1
            cid="$(ps o ppid,pid | grep "^$(ps o pid,cmd | grep -E "^\\ *[0-9]+ unshare.*$1" | awk '{{print $1}}')" | awk '{{print $2}}')"
            [[ ! "$cid" =~ ^\\ *[0-9]+$ ]] && echo "Container '$1' exists but is not running" && exit 1
            nsenter -t "$cid" -m -u -i -n -p chroot "$btrfs_path/$1" ${{@:2}}
        }}
        
        bocker_exec "{container_id}" {command}
        """
        return self._run_bash_command(bash_script, show_realtime=True)
    
    def logs(self, args):
        """View logs from a container: BOCKER logs <container_id>"""
        if len(args) < 1:
            print("Usage: bocker logs <container_id>", file=sys.stderr)
            return 1
        
        container_id = args[0]
        bash_script = f"""
        btrfs_path='{self.btrfs_path}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_logs() {{
            [[ "$(bocker_check "$1")" == 1 ]] && echo "No container named '$1' exists" && exit 1
            cat "$btrfs_path/$1/$1.log"
        }}
        
        bocker_logs "{container_id}"
        """
        return self._run_bash_command(bash_script)
    
    def commit(self, args):
        """Commit a container to an image: BOCKER commit <container_id> <image_id>"""
        if len(args) < 2:
            print("Usage: bocker commit <container_id> <image_id>", file=sys.stderr)
            return 1
        
        container_id, image_id = args[0], args[1]
        bash_script = f"""
        set -o errexit -o nounset -o pipefail
        btrfs_path='{self.btrfs_path}'
        cgroups='{self.cgroups}'
        
        function bocker_check() {{
            btrfs subvolume list "$btrfs_path" | grep -qw "$1" && echo 0 || echo 1
        }}
        
        function bocker_rm() {{
            [[ "$(bocker_check "$1")" == 1 ]] && echo "No container named '$1' exists" && exit 1
            btrfs subvolume delete "$btrfs_path/$1" > /dev/null
            cgdelete -g "$cgroups:/$1" &> /dev/null || true
            echo "Removed: $1"
        }}
        
        function bocker_commit() {{
            [[ "$(bocker_check "$1")" == 1 ]] && echo "No container named '$1' exists" && exit 1
            [[ "$(bocker_check "$2")" == 1 ]] && echo "No image named '$2' exists" && exit 1
            bocker_rm "$2" && btrfs subvolume snapshot "$btrfs_path/$1" "$btrfs_path/$2" > /dev/null
            echo "Created: $2"
        }}
        
        bocker_commit "{container_id}" "{image_id}"
        """
        return self._run_bash_command(bash_script)
    
    def help(self, args):
        """Display help message"""
        bash_script = """
        function bocker_help() {
            echo "BOCKER - Docker implemented in around 100 lines of bash"
            echo ""
            echo "Usage: bocker <command> [args...]"
            echo ""
            echo "Commands:"
            echo "  pull <name> <tag>           Pull an image from Docker Hub"
            echo "  init <directory>            Create an image from a directory"
            echo "  rm <image_id|container_id>  Delete an image or container"
            echo "  images                      List images"
            echo "  ps                          List containers"
            echo "  run <image_id> <command>    Create a container"
            echo "  exec <container_id> <cmd>   Execute a command in a running container"
            echo "  logs <container_id>         View logs from a container"
            echo "  commit <container_id> <img> Commit a container to an image"
            echo "  help                        Display this message"
        }
        
        bocker_help
        """
        return self._run_bash_command(bash_script)

def main():
    # Handle environment variables for CPU and memory limits
    env_vars = {}
    for key, value in os.environ.items():
        if key.startswith('BOCKER_'):
            env_vars[key] = value
    
    if env_vars:
        for key, value in env_vars.items():
            os.environ[key] = value
    
    wrapper = BockerWrapper()
    
    if len(sys.argv) < 2:
        return wrapper.help([])
    
    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Map commands to their wrapper methods
    command_map = {
        'pull': wrapper.pull,
        'init': wrapper.init,
        'rm': wrapper.rm,
        'images': wrapper.images,
        'ps': wrapper.ps,
        'run': wrapper.run,
        'exec': wrapper.exec,
        'logs': wrapper.logs,
        'commit': wrapper.commit,
        'help': wrapper.help
    }
    
    if command in command_map:
        return command_map[command](args)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return wrapper.help([])

if __name__ == '__main__':
    sys.exit(main())
