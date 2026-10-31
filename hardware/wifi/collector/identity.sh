# SP11 log collector drop-in: Wi-Fi identity experiment (read-only, address-free).
# Install as /etc/sp11-log-collector.d/wifi-identity.sh (sourced by sp11-log-collector in a
# subshell; output goes to extra-wifi-identity.txt). Owner: wifi worker; installed by the image
# worker (hardware/wifi/image-request-identity.md).
#
# Question answered: does the hardware give its own factory Wi-Fi station address without the
# private-mode copy? What is recorded (S5): a 16-hex SHA-256 prefix of each address, its
# assignment type, the locally-administered/multicast bits, a vendor-range CLASS (registered or
# not, never the OUI), and in PRIVATE mode only MATCH / NO MATCH against the reference hash.
# No address, OUI or vendor name is ever printed; the whole output also passes a MAC mask.
#
# Why the timing does not matter: the permanent address (mac80211 wiphy perm_addr, sysfs
# /sys/class/ieee80211/<phy>/macaddress, `ethtool -P`) is set by ath12k from the firmware ready
# event and is not changed by the udev .link file or by NetworkManager, which only change the
# current address. So it is the firmware value in every boot, with or without injection.
#
# Test hooks: SP11_ID_ROOT prefixes /sys, /proc, /etc and /usr (fixtures); tools come from PATH.

sp11_id_hash16() { printf '%s' "$1" | tr 'A-F' 'a-f' | sha256sum | cut -c1-16; }
sp11_id_norm() { # normalise one address, empty output when not a colon-form address
	local a
	a=$(printf '%s' "$1" | tr 'A-F' 'a-f' | tr -d '[:space:]')
	[[ $a =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]] && printf '%s' "$a"
}
sp11_id_type() { # address bits only: scope, cast, sentinel
	local a=$1 o scope=universal cast=unicast sent=no
	o=$((16#${a%%:*}))
	((o & 2)) && scope=locally-administered
	((o & 1)) && cast=multicast
	case ${a//:/} in 000000000000 | ffffffffffff) sent=yes ;; esac
	printf 'scope=%s cast=%s sentinel=%s' "$scope" "$cast" "$sent"
}
sp11_id_oui_class() { # class only: registered | not-registered-or-db-missing | not-applicable
	local a=$1 o out
	o=$((16#${a%%:*}))
	if ((o & 3)); then printf 'not-applicable'; return; fi
	command -v systemd-hwdb >/dev/null 2>&1 || { printf 'not-registered-or-db-missing'; return; }
	out=$(timeout 5 systemd-hwdb query "OUI:$(printf '%s' "${a:0:8}" | tr -d ':' | tr 'a-f' 'A-F')" 2>/dev/null)
	if grep -q '^ID_OUI_FROM_DATABASE=' <<<"$out"; then printf 'registered'; else printf 'not-registered-or-db-missing'; fi
}
sp11_id_ref_ok() { # regular file, mode 0600, root-owned (fixtures may set SP11_ID_ALLOW_NONROOT)
	[ -f "$1" ] || return 1
	[ "$(stat -c %a "$1" 2>/dev/null)" = 600 ] || return 1
	[ "$(stat -c %u "$1" 2>/dev/null)" = 0 ] || [ -n "${SP11_ID_ALLOW_NONROOT:-}" ]
}
sp11_id_assign_name() {
	case $1 in 0) echo permanent ;; 1) echo random ;; 2) echo stolen ;; 3) echo set-by-userspace ;; *) echo "unknown" ;; esac
}

sp11_id_wifi_report() {
	local r=${SP11_ID_ROOT:-} cmdline sw mode ref='' refwifi='' phy ifc perm cur t atype p_eth p_ip p_iw
	local sysperm hp hc agree dl dm dinv da

	cmdline=$(cat "$r/proc/cmdline" 2>/dev/null)
	sw=inject
	case " $cmdline " in
	*" sp11.identity=none "*) sw=none ;;
	*" sp11.identity=inject "*) sw=inject ;;
	*" sp11.identity="*) sw='invalid(treated-as-inject)' ;;
	esac
	mode=$(tr -d '[:space:]' <"$r/usr/share/sp11/image-mode" 2>/dev/null)
	[ "$mode" = private ] || mode=public
	echo "== sp11 identity experiment, wifi, collector v1"
	echo "image_mode=$mode identity_switch=$sw uptime_s=$(cut -d' ' -f1 "$r/proc/uptime" 2>/dev/null)"
	echo "unit_logged_mode=$(cat "$r/run/sp11/identity-wifi-mode" 2>/dev/null || echo none-recorded)"
	for f in etc/systemd/network/10-sp11-wifi.link etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf; do
		if [ -e "$r/$f" ]; then echo "injection_file_present=/$f"; else echo "injection_file_absent=/$f"; fi
	done

	# The reference file is read ONLY in private mode (public builds never contain or open it).
	if [ "$mode" = private ]; then
		ref=$r/usr/share/sp11/identity-ref.sha256
		if sp11_id_ref_ok "$ref"; then
			refwifi=$(sed -n 's/^wifi=\([0-9a-f]\{16\}\)$/\1/p' "$ref" | head -1)
			[ -n "$refwifi" ] || echo "reference: no wifi= line (comparison skipped)"
		else
			echo "reference: missing or not root-owned 0600 (comparison skipped)"
		fi
	else
		echo "reference: not read (public mode)"
	fi

	shopt -s nullglob
	local n=0
	for sysperm in "$r"/sys/class/ieee80211/*/macaddress; do
		phy=$(basename "$(dirname "$sysperm")")
		for ifc in "$r/sys/class/ieee80211/$phy/device/net"/*; do
			ifc=$(basename "$ifc"); n=$((n + 1))
			echo "== wifi phy=$phy netdev=$ifc"
			perm=$(sp11_id_norm "$(cat "$sysperm" 2>/dev/null)")
			p_eth=$(sp11_id_norm "$(timeout 5 ethtool -P "$ifc" 2>/dev/null | sed -n 's/^Permanent address: //p')")
			p_ip=$(sp11_id_norm "$(timeout 5 ip -d -o link show dev "$ifc" 2>/dev/null | sed -n 's/.* permaddr \([0-9a-fA-F:]*\).*/\1/p')")
			cur=$(sp11_id_norm "$(cat "$r/sys/class/net/$ifc/address" 2>/dev/null)")
			p_iw=$(sp11_id_norm "$(timeout 5 iw dev 2>/dev/null | awk -v i="$ifc" '$1=="Interface"{c=($2==i)} c&&$1=="addr"{print $2; exit}')")
			atype=$(cat "$r/sys/class/net/$ifc/addr_assign_type" 2>/dev/null)

			if [ -n "$perm" ]; then
				hp=$(sp11_id_hash16 "$perm")
				echo "wifi.permanent.source=sysfs-ieee80211-macaddress sha256_16=$hp $(sp11_id_type "$perm") oui_class=$(sp11_id_oui_class "$perm")"
			else
				hp=''; echo "wifi.permanent.source=sysfs-ieee80211-macaddress unavailable"
			fi
			agree=''
			[ -n "$p_eth" ] && agree="$agree ethtool=$([ "$p_eth" = "$perm" ] && echo agree || echo DIFFER)"
			[ -n "$p_ip" ] && agree="$agree ip-permaddr=$([ "$p_ip" = "$perm" ] && echo agree || echo DIFFER)"
			echo "wifi.permanent.cross_check:${agree:- none-available}"
			if [ -n "$cur" ]; then
				hc=$(sp11_id_hash16 "$cur")
				t=$(sp11_id_assign_name "$atype")
				echo "wifi.current.sha256_16=$hc addr_assign_type=$atype($t) $(sp11_id_type "$cur")"
				echo "wifi.current_equals_permanent=$([ "$cur" = "$perm" ] && echo yes || echo no)"
				[ -n "$p_iw" ] && echo "wifi.current.iw_dev_agrees=$([ "$p_iw" = "$cur" ] && echo yes || echo no)"
			else
				hc=''; echo "wifi.current unavailable"
			fi
			if [ -n "$refwifi" ]; then
				echo "wifi.ref_match.permanent=$([ "$hp" = "$refwifi" ] && echo MATCH || echo 'NO MATCH')"
				echo "wifi.ref_match.current=$([ "$hc" = "$refwifi" ] && echo MATCH || echo 'NO MATCH')"
			fi
		done
	done
	[ "$n" -gt 0 ] || echo "wifi: no ieee80211 netdev present (ath12k did not register a station interface)"

	# ath12k kernel log: counts, plus a hash of the first address-shaped token on a MAC line.
	dl=$(timeout 10 dmesg 2>/dev/null | grep -i 'ath12k')
	dm=$(grep -i -E 'mac|address' <<<"$dl")
	dinv=$(grep -c -i -E 'invalid|zero|random' <<<"$dm")
	da=$(sp11_id_norm "$(grep -o -E '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' <<<"$dm" | head -1)")
	if [ -n "$da" ]; then da=$(sp11_id_hash16 "$da"); else da=none-logged; fi
	echo "wifi.ath12k_dmesg lines=$(grep -c . <<<"$dl") mac_lines=$(grep -c . <<<"$dm") mac_invalid_lines=$dinv first_addr_sha256_16=$da"
	shopt -u nullglob
}

# Final belt: nothing MAC-shaped can leave this hook, whatever a tool prints.
sp11_id_wifi_report 2>&1 | sed -E 's/([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}/<MAC>/g'
