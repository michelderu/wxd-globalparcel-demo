#!/bin/bash
# Host readiness for local watsonx.data / Lakehouse on Kind with Docker Engine only.
# Unset DOCKER_HOST for the default docker.sock unless you intentionally override it.
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
    done
    if command -v docker &>/dev/null; then
        n=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^[a-z0-9][a-z0-9-]*-control-plane$' | head -n1)
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
    return 127
}

echo -e "${BOLD}=== watsonx.data / Kind host check ===${NC}"
echo "User: $(whoami) (uid $(id -u))  Date: $(date -Iseconds 2>/dev/null || date)"
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${YELLOW}Note: Run as a normal login user for checks that need non-root context; Docker/Kind checks work as root too.${NC}"
fi

# --- 1. User namespaces (nested containers: Kind nodes on Docker) ---
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
    note_warn "fs.inotify.max_user_watches=${IW:-unset} — low values cause 'too many open files' / watch errors under Kubernetes"
    echo "   Consider: fs.inotify.max_user_watches=1048576 (sysctl + persistent drop-in)"
fi
if [ -n "$II" ] && [ "$II" -ge 256 ] 2>/dev/null; then
    note_ok "fs.inotify.max_user_instances=$II"
else
    note_warn "fs.inotify.max_user_instances=${II:-unset} — raise if you see inotify instance exhaustion"
fi

# --- 3. Address space (JVM services, Spark, native libs) ---
echo -e "\n${CYAN}[3] Virtual memory maps (vm.max_map_count)${NC}"
MMC=$(sysctl_get vm.max_map_count)
if [ -n "$MMC" ] && [ "$MMC" -ge 262144 ] 2>/dev/null; then
    note_ok "vm.max_map_count=$MMC"
else
    note_warn "vm.max_map_count=${MMC:-unset} < 262144 — JVM-heavy stacks often need 262144–1048576"
fi

# --- 4. PID space (many short-lived processes + Spark) ---
echo -e "\n${CYAN}[4] PID limits (kernel.pid_max)${NC}"
PM=$(sysctl_get kernel.pid_max)
if [ -n "$PM" ] && [ "$PM" -ge 32768 ] 2>/dev/null; then
    note_ok "kernel.pid_max=$PM"
else
    note_warn "kernel.pid_max=${PM:-unset} — very large workloads benefit from pid_max >= 4194304"
fi

# --- 5. IPv4 forwarding (Kind / bridge CNI) ---
echo -e "\n${CYAN}[5] IPv4 forwarding${NC}"
FW=$(sysctl_get net.ipv4.ip_forward)
if [ "$FW" = "1" ]; then
    note_ok "net.ipv4.ip_forward=1"
else
    note_warn "net.ipv4.ip_forward=${FW:-unset} — should be 1 for Kind pod routing"
fi

# --- 6. cgroup hierarchy (informational; Kind config often pins cgroup driver) ---
echo -e "\n${CYAN}[6] cgroup root filesystem${NC}"
if [ -e /sys/fs/cgroup ]; then
    CGTYPE=$(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo unknown)
    echo "   /sys/fs/cgroup type: $CGTYPE"
    if [ "$CGTYPE" = "cgroup2fs" ]; then
        note_ok "Unified cgroup v2 — ensure Kind/kubelet cgroup driver matches your cluster config"
    else
        note_ok "Hybrid or cgroup v1 layout detected"
    fi
else
    note_warn "/sys/fs/cgroup missing"
fi

# --- 7. Docker Engine (Kind node provider) ---
echo -e "\n${CYAN}[7] Docker Engine${NC}"
if command -v docker &>/dev/null; then
    DOCKER_BIN=$(command -v docker)
    DOCKER_REAL=$(readlink -f "$DOCKER_BIN" 2>/dev/null || echo "$DOCKER_BIN")
    case "$DOCKER_REAL" in
        *podman*)
            note_fail "docker CLI is not Docker Engine (resolved to $DOCKER_REAL) — install docker-ce and use its docker binary"
            ;;
    esac
    case "${DOCKER_HOST:-}" in
        *podman*)
            note_fail "DOCKER_HOST does not point at Docker Engine ($DOCKER_HOST) — unset for the default engine socket"
            ;;
    esac
    case "${CONTAINER_HOST:-}" in
        *podman*)
            note_fail "CONTAINER_HOST does not point at Docker Engine ($CONTAINER_HOST) — unset when using Docker Engine"
            ;;
    esac
    DI_INFO=$(docker info 2>/dev/null || true)
    if [ -n "$DI_INFO" ] && echo "$DI_INFO" | grep -qiE 'podman|libpod'; then
        note_fail "docker info is not from Docker Engine — use Docker CE with Kind, not a Docker-compatible alternate runtime"
    fi
    if command -v systemctl &>/dev/null; then
        if systemctl is-active docker --quiet 2>/dev/null; then
            note_ok "docker.service is active"
        else
            note_fail "docker.service is not active — run: sudo systemctl enable --now docker"
        fi
    else
        note_warn "systemctl missing — could not verify docker.service"
    fi
else
    note_warn "docker CLI not found — install Docker CE (see docker-readme.md)"
fi

# --- 8. Docker engine pids limits ---
echo -e "\n${CYAN}[8] Engine pids limits (Docker)${NC}"
if command -v docker &>/dev/null; then
    DI_ERR=0
    DI_OUT=$(docker info 2>&1) || DI_ERR=$?
    if [ "$DI_ERR" -eq 0 ]; then
        # Human "Pids …" lines were dropped from docker info text in recent Docker CLI (e.g. 29.x);
        # fall back to API field PidsLimit (bool: pids cgroup available), not a numeric default.
        DP=$(echo "$DI_OUT" | grep -iE '^\s*pids' | head -n1 | sed 's/^[[:space:]]*//')
        if [ -n "$DP" ]; then
            note_ok "Docker: $DP"
        else
            PL_API=$(docker info --format '{{.PidsLimit}}' 2>/dev/null) || PL_API=""
            if [ "$PL_API" = "true" ]; then
                note_ok "Docker: pids cgroup supported (docker info no longer prints a Pids line; tune default per container via daemon.json / --default-pids-limit if needed for Spark)"
            elif [ "$PL_API" = "false" ]; then
                note_warn "Docker: pids cgroup not reported (PidsLimit=false) — check defaults for Spark fork storms"
            else
                note_warn "Docker: could not parse Pids from docker info — check defaults for Spark fork storms"
            fi
        fi
    else
        if echo "$DI_OUT" | grep -qi 'permission denied'; then
            note_warn "Docker: cannot run docker info (socket permission) — add your user to group docker or use newgrp docker"
        else
            note_warn "Docker info failed — skipped Docker Pids summary"
        fi
    fi
fi

# --- 9. RAM (order-of-magnitude for full wxd chart) ---
echo -e "\n${CYAN}[9] Available memory${NC}"
if [ -r /proc/meminfo ]; then
    AVAIL_KB=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
    if [ "$AVAIL_GB" -ge 16 ]; then
        note_ok "MemAvailable ~ ${AVAIL_GB} GiB"
    elif [ "$AVAIL_GB" -ge 8 ]; then
        note_warn "MemAvailable ~ ${AVAIL_GB} GiB — watsonx.data dev stacks are tight below ~16 GiB free"
    else
        note_warn "MemAvailable ~ ${AVAIL_GB} GiB — likely insufficient for a comfortable full install"
    fi
else
    note_warn "Cannot read /proc/meminfo"
fi

# --- 10. Disk for container images + PVCs ---
echo -e "\n${CYAN}[10] Free disk (common image roots)${NC}"
checked=0
low_disk=0
for mp in /var/lib/docker; do
    if [ -d "$mp" ]; then
        avail=$(df -BG "$mp" 2>/dev/null | awk 'NR==2 {gsub(/G/,"",$4); print $4}')
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
    note_warn "No standard Docker image dir (/var/lib/docker); check disk on your Docker data root"
elif [ "$low_disk" -eq 1 ]; then
    note_warn "At least one image store has < ~40 GiB free — chart images and data fill space quickly"
fi

# --- 11. SELinux (common friction for container workloads) ---
echo -e "\n${CYAN}[11] SELinux mode${NC}"
if command -v getenforce &>/dev/null; then
    SE=$(getenforce 2>/dev/null)
    if [ "$SE" = "Enforcing" ]; then
        note_warn "SELinux is Enforcing — you may need policy exceptions or permissive mode for some Spark/Kind combinations"
    else
        note_ok "SELinux: $SE"
    fi
else
    echo "   (getenforce not present — likely not SELinux system)"
fi

# --- 12. Kind node: uid_map inside control plane (informational for Docker) ---
echo -e "\n${CYAN}[12] Kind control-plane container + /proc/self/uid_map${NC}"
KP=$(kind_control_plane_name)
if [ -z "$KP" ]; then
    note_warn "No Kind control-plane container found — start the cluster (docker ps should show *-control-plane)"
else
    echo "   Using container: $KP"
    MAP=$(container_exec "$KP" cat /proc/self/uid_map 2>/dev/null | tr -s ' ')
    if [ -z "$MAP" ]; then
        note_warn "Could not read uid_map from $KP"
    else
        echo "$MAP" | sed 's/^/   /'
        note_ok "Kind on Docker: typical single-line uid_map (expected)"
    fi
fi

echo -e "\n${BOLD}=== Summary ===${NC}"
echo "Failures: $FAIL   Warnings: $WARN"
if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Address failures before expecting a stable install.${NC}"
    exit 1
fi
exit 0
