# SP11 log collector drop-in: Bluetooth identity experiment (read-only, address-free).
# Install as /etc/sp11-log-collector.d/bluetooth-identity.sh; output: extra-bluetooth-identity.txt.
timeout -k 1 40 /usr/libexec/sp11-identity-bt report
