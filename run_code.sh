#/bin/bash

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Remove existing bridge if it exists
ip link del bridge0 2>/dev/null || true

# Create and configure bridge
ip link add bridge0 type bridge
ip addr add 10.0.0.1/24 dev bridge0
ip link set bridge0 up

# Clear all iptables rules
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

# Set default policies
iptables -P FORWARD ACCEPT
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT

# Add comprehensive iptables rules
iptables -t nat -A POSTROUTING -s 10.0.0.0/24 ! -o bridge0 -j MASQUERADE
iptables -A FORWARD -i bridge0 -o enp0s3 -j ACCEPT
iptables -A FORWARD -i enp0s3 -o bridge0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i bridge0 -o bridge0 -j ACCEPT

