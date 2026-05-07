#!/bin/bash
# Host readiness for local watsonx.data / Lakehouse on Kind with Docker or Podman.
# Unset DOCKER_HOST/CONTAINER_HOST for default local sockets unless intentionally overridden.
# Exit 1 if any hard failure; warnings do not change exit code.

set +e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

FAIL=0
WARN=0

note_fail() { echo -e "${RED}✗ $*${NC}"; FAIL=$((FAIL + 1)); }
note_warn() { echo -e "${YELLOW}⚠ $*${NC}"; WARN=$((WARN + 1)); }
note_ok()   { echo -e "${GREEN}✓ $*${NC}"; }

sysctl_get() {
    local key="$1"
    if [ -r "/proc/sys/${key//./\/}" ]; then
        cat "/proc/sys/${key//./\/}" 2>/dev/null
    else
        sysctl -n "$key" 2>/dev/null
    fi
}

kind_control_plane_name() {
    # KIND names the node container "{cluster}-control-plane" (e.g. wxd-control-plane), not
    # "kind-{cluster}-control-plane". Override with KIND_CLUSTER_NAME if yours differs.
    local n cluster="${KIND_CLUSTER_NAME:-wxd}"
    local try
    for try in "${cluster}-control-plane" "kind-control-plane"; do
        if command -v docker &>/dev/null; then
            n=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -Fx "$try" | head -n1)
            [ -n "$n" ] && { echo "$n"; return; }
        fi
        if command -v podman &>/dev/null; then
            n=$(podman ps --format '{{.Names}}' 2>/dev/null | grep -Fx "$try" | head -n1)
            [ -n "$n" ] && { echo "$n"; return; }
        fi
    done
    if command -v docker &>/dev/null; then
        n=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^[a-z0-9][a-z0-9-]*-control-plane$' | head -n1)
        [ -n "$n" ] && { echo "$n"; return; }
    fi
    if command -v podman &>/dev/null; then
        n=$(podman ps --format '{{.Names}}' 2>/dev/null | grep -E '^[a-z0-9][a-z0-9-]*-control-plane$' | head -n1)
        [ -n "$n" ] && { echo "$n"; return; }
    fi
    echo ""
}

container_exec() {
    local name="$1"
    shift
    if command -v docker &>/dev/null && docker inspect "$name" &>/dev/null; then
        docker exec "$name" "$@"
        return $?
    fi
    if command -v podman &>/dev/null && podman inspect "$name" &>/dev/null; then
        podman exec "$name" "$@"
        return $?
    fi
    return 127
}

detect_runtime() {
    if command -v docker &>/dev/null; then
        if docker info &>/dev/null; then
            echo "docker"
            return 0
        fi
    fi
    if command -v podman &>/dev/null; then
        if podman info &>/dev/null; then
            echo "podman"
            return 0
        fi
    fi
    echo ""
}

detect_platform() {
    case "$(uname -s 2>/dev/null)" in
        Linux) echo "linux" ;;
        Darwin) echo "macos" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *) echo "other" ;;
    esac
}

get_cpu_count() {
    getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null
}

get_mem_available_gb() {
    local platform="$1"
    local kb bytes pages free_pages page_size
    case "$platform" in
        linux)
            if [ -r /proc/meminfo ]; then
                kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
                [ -n "$kb" ] && echo $((kb / 1024 / 1024))
            fi
            ;;
        macos)
            pages=$(vm_stat 2>/dev/null)
            page_size=$(echo "$pages" | awk -F': ' '/page size of/ {gsub("\\.","",$2); print $2}' | awk '{print $1}')
            free_pages=$(echo "$pages" | awk -F': ' '/Pages free|Pages inactive|Pages speculative/ {gsub("\\.","",$2); sum+=$2} END {print sum+0}')
            if [ -n "$page_size" ] && [ -n "$free_pages" ]; then
                bytes=$((free_pages * page_size))
                echo $((bytes / 1024 / 1024 / 1024))
            fi
            ;;
    esac
}

get_total_mem_gb() {
    local platform="$1"
    local kb bytes
    case "$platform" in
        linux)
            if [ -r /proc/meminfo ]; then
                kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
                [ -n "$kb" ] && echo $((kb / 1024 / 1024))
            fi
            ;;
        macos)
            bytes=$(sysctl -n hw.memsize 2>/dev/null)
            [ -n "$bytes" ] && echo $((bytes / 1024 / 1024 / 1024))
            ;;
        windows)
            # In Git Bash/MSYS environments, PowerShell may not always be available.
            bytes=$(powershell.exe -NoProfile -Command "[int64]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory)" 2>/dev/null | tr -d '\r')
            [ -n "$bytes" ] && echo $((bytes / 1024 / 1024 / 1024))
            ;;
    esac
}

get_free_disk_gb() {
    local target="$1"
    df -Pk "$target" 2>/dev/null | awk 'NR==2 {print int($4/1024/1024)}'
}

echo -e "${BOLD}=== watsonx.data / Kind host check ===${NC}"
echo "User: $(whoami) (uid $(id -u))  Date: $(date -Iseconds 2>/dev/null || date)"
PLATFORM=$(detect_platform)
echo "Platform: $PLATFORM"
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${YELLOW}Note: Run as a normal login user for checks that need non-root context; Docker/Kind checks work as root too.${NC}"
fi

if [ "$PLATFORM" = "linux" ]; then
    # --- 1. User namespaces (nested containers: Kind nodes on runtime) ---
    echo -e "\n${CYAN}[1] User namespaces (user.max_user_namespaces)${NC}"
    MAX_USER_NS=$(sysctl_get user.max_user_namespaces)
    if [ -z "$MAX_USER_NS" ] || ! [ "$MAX_USER_NS" -eq "$MAX_USER_NS" ] 2>/dev/null; then
        note_fail "Could not read user.max_user_namespaces"
    elif [ "$MAX_USER_NS" -lt 10000 ]; then
        note_fail "user.max_user_namespaces=$MAX_USER_NS is too low for Kind/container nesting (need >= 10000)"
        echo "   Fix: sudo sysctl -w user.max_user_namespaces=65536"
    elif [ "$MAX_USER_NS" -lt 28633 ]; then
        note_warn "user.max_user_namespaces=$MAX_USER_NS works for many setups; 28633+ is safer for deep nesting"
        note_ok "user.max_user_namespaces=$MAX_USER_NS (acceptable minimum)"
    else
        note_ok "user.max_user_namespaces=$MAX_USER_NS"
    fi

    # --- 2. inotify (kubelet, editors, file sync on many mounts) ---
    echo -e "\n${CYAN}[2] inotify limits${NC}"
    IW=$(sysctl_get fs.inotify.max_user_watches)
    II=$(sysctl_get fs.inotify.max_user_instances)
    if [ -n "$IW" ] && [ "$IW" -ge 524288 ] 2>/dev/null; then
        note_ok "fs.inotify.max_user_watches=$IW"
    else
        note_warn "fs.inotify.max_user_watches=${IW:-unset} — low values cause watch exhaustion under Kubernetes"
    fi
    if [ -n "$II" ] && [ "$II" -ge 256 ] 2>/dev/null; then
        note_ok "fs.inotify.max_user_instances=$II"
    else
        note_warn "fs.inotify.max_user_instances=${II:-unset} — raise if you see inotify instance exhaustion"
    fi

    # --- 3. Address space ---
    echo -e "\n${CYAN}[3] Virtual memory maps (vm.max_map_count)${NC}"
    MMC=$(sysctl_get vm.max_map_count)
    if [ -n "$MMC" ] && [ "$MMC" -ge 262144 ] 2>/dev/null; then
        note_ok "vm.max_map_count=$MMC"
    else
        note_warn "vm.max_map_count=${MMC:-unset} < 262144 — JVM-heavy stacks often need 262144+"
    fi

    # --- 4. PID space ---
    echo -e "\n${CYAN}[4] PID limits (kernel.pid_max)${NC}"
    PM=$(sysctl_get kernel.pid_max)
    if [ -n "$PM" ] && [ "$PM" -ge 32768 ] 2>/dev/null; then
        note_ok "kernel.pid_max=$PM"
    else
        note_warn "kernel.pid_max=${PM:-unset} — large workloads benefit from higher values"
    fi

    # --- 5. IPv4 forwarding ---
    echo -e "\n${CYAN}[5] IPv4 forwarding${NC}"
    FW=$(sysctl_get net.ipv4.ip_forward)
    if [ "$FW" = "1" ]; then
        note_ok "net.ipv4.ip_forward=1"
    else
        note_warn "net.ipv4.ip_forward=${FW:-unset} — should be 1 for Kind pod routing on Linux"
    fi

    # --- 6. cgroup hierarchy ---
    echo -e "\n${CYAN}[6] cgroup root filesystem${NC}"
    if [ -e /sys/fs/cgroup ]; then
        CGTYPE=$(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo unknown)
        echo "   /sys/fs/cgroup type: $CGTYPE"
        if [ "$CGTYPE" = "cgroup2fs" ]; then
            note_ok "Unified cgroup v2"
        else
            note_ok "Hybrid or cgroup v1 layout detected"
        fi
    else
        note_warn "/sys/fs/cgroup missing"
    fi
else
    echo -e "\n${CYAN}[1-6] Linux kernel checks${NC}"
    note_warn "Skipping Linux-only sysctl/cgroup checks on $PLATFORM. These are validated inside your Linux VM/WSL runtime."
fi

# --- 7. Container runtime (Docker or Podman) ---
echo -e "\n${CYAN}[7] Container runtime${NC}"
RUNTIME=$(detect_runtime)
if [ -z "$RUNTIME" ]; then
    note_fail "No working container runtime found. Install and start Docker or Podman."
    if command -v docker &>/dev/null && ! docker info &>/dev/null; then
        note_warn "docker CLI is present but docker info failed (daemon/socket/permissions)."
    fi
    if command -v podman &>/dev/null && ! podman info &>/dev/null; then
        note_warn "podman CLI is present but podman info failed."
    fi
else
    note_ok "Using runtime: $RUNTIME"
    if command -v systemctl &>/dev/null; then
        if [ "$RUNTIME" = "docker" ]; then
            if systemctl is-active docker --quiet 2>/dev/null; then
                note_ok "docker.service is active"
            else
                note_warn "docker.service not active in systemd (this may be expected for rootless setups)"
            fi
        else
            if systemctl is-active podman --quiet 2>/dev/null || systemctl --user is-active podman --quiet 2>/dev/null; then
                note_ok "podman service/socket appears active"
            else
                note_warn "podman service/socket not active in systemd (may still work rootless via direct CLI)"
            fi
        fi
    fi
fi

# --- 8. Runtime pids/cgroup capability ---
echo -e "\n${CYAN}[8] Runtime pids/cgroup capability${NC}"
if [ "$RUNTIME" = "docker" ]; then
    PL_API=$(docker info --format '{{.PidsLimit}}' 2>/dev/null) || PL_API=""
    if [ "$PL_API" = "true" ]; then
        note_ok "Docker: pids cgroup supported"
    elif [ "$PL_API" = "false" ]; then
        note_warn "Docker: pids cgroup not reported (PidsLimit=false)"
    else
        note_warn "Docker: could not determine pids cgroup capability"
    fi
elif [ "$RUNTIME" = "podman" ]; then
    if podman info --format '{{.Host.CgroupsVersion}}' &>/dev/null; then
        CGV=$(podman info --format '{{.Host.CgroupsVersion}}' 2>/dev/null)
        note_ok "Podman: cgroups version $CGV"
    else
        note_warn "Podman: could not determine cgroups capability from podman info"
    fi
fi

# --- 9. Host CPU and RAM ---
echo -e "\n${CYAN}[9] Host CPU and memory${NC}"
CPU_COUNT=$(get_cpu_count || echo "")
if [ -n "$CPU_COUNT" ] && [ "$CPU_COUNT" -eq "$CPU_COUNT" ] 2>/dev/null; then
    if [ "$CPU_COUNT" -ge 8 ]; then
        note_ok "CPU cores: $CPU_COUNT"
    elif [ "$CPU_COUNT" -ge 4 ]; then
        note_warn "CPU cores: $CPU_COUNT — workable for light dev, 8+ recommended for smoother installs"
    else
        note_warn "CPU cores: $CPU_COUNT — likely too low for stable local Lakehouse workloads"
    fi
else
    note_warn "Could not determine CPU core count"
fi

AVAIL_GB=$(get_mem_available_gb "$PLATFORM")
TOTAL_GB=$(get_total_mem_gb "$PLATFORM")
if [ -n "$AVAIL_GB" ] && [ "$AVAIL_GB" -eq "$AVAIL_GB" ] 2>/dev/null; then
    if [ "$AVAIL_GB" -ge 16 ]; then
        note_ok "MemAvailable ~ ${AVAIL_GB} GiB"
    elif [ "$AVAIL_GB" -ge 8 ]; then
        note_warn "MemAvailable ~ ${AVAIL_GB} GiB — watsonx.data dev stacks are tight below ~16 GiB free"
    else
        note_warn "MemAvailable ~ ${AVAIL_GB} GiB — likely insufficient for a comfortable full install"
    fi
elif [ -n "$TOTAL_GB" ] && [ "$TOTAL_GB" -eq "$TOTAL_GB" ] 2>/dev/null; then
    if [ "$TOTAL_GB" -ge 16 ]; then
        note_ok "Total memory ~ ${TOTAL_GB} GiB (free memory metric unavailable on $PLATFORM)"
    elif [ "$TOTAL_GB" -ge 8 ]; then
        note_warn "Total memory ~ ${TOTAL_GB} GiB — usable for light dev, 16+ GiB recommended"
    else
        note_warn "Total memory ~ ${TOTAL_GB} GiB — likely insufficient for a comfortable full install"
    fi
else
    note_warn "Could not determine memory on $PLATFORM"
fi

# --- 10. Disk for container images + PVCs ---
echo -e "\n${CYAN}[10] Free disk${NC}"
checked=0
low_disk=0
for mp in /var/lib/docker /var/lib/containers "$HOME" "."; do
    if [ -d "$mp" ]; then
        avail=$(get_free_disk_gb "$mp")
        if [ -n "$avail" ] && [ "$avail" -eq "$avail" ] 2>/dev/null; then
            echo "   $mp free: ${avail}G"
            checked=1
            if [ "$avail" -lt 40 ]; then
                low_disk=1
            fi
        fi
    fi
done
if [ "$checked" -eq 0 ]; then
    note_warn "Could not determine free disk on common paths"
elif [ "$low_disk" -eq 1 ]; then
    note_warn "At least one image store has < ~40 GiB free — chart images and data fill space quickly"
fi

# --- 11. Kind node: uid_map inside control plane (informational) ---
echo -e "\n${CYAN}[11] Kind control-plane container + /proc/self/uid_map${NC}"
KP=$(kind_control_plane_name)
if [ -z "$KP" ]; then
    note_warn "No Kind control-plane container found — start the cluster (*-control-plane should be running)"
else
    echo "   Using container: $KP"
    MAP=$(container_exec "$KP" cat /proc/self/uid_map 2>/dev/null | tr -s ' ')
    if [ -z "$MAP" ]; then
        note_warn "Could not read uid_map from $KP"
    else
        echo "$MAP" | sed 's/^/   /'
        note_ok "Kind control-plane uid_map readable"
    fi
fi

echo -e "\n${BOLD}=== Summary ===${NC}"
echo "Failures: $FAIL   Warnings: $WARN"
if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Address failures before expecting a stable install.${NC}"
    exit 1
fi
exit 0
