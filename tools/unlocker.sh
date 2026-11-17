#!/usr/bin/env bash
# ==============================================================================
# Antigravity Unlocker 2.1 - Cross-Platform POSIX / Linux / macOS Shell Script
# Follows Linux Production Shell Scripting Standards:
# - Strict mode: set -euo pipefail
# - Safe trap handling for clean exit
# - Idempotent hosts modification with automated backup
# - Binary patcher for Linux/macOS language_server and agy binaries
# ==============================================================================

set -euo pipefail

# --- Color Definitions ---
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# --- Global Configurations ---
readonly HOSTS_FILE="/etc/hosts"
readonly DEFAULT_PROXY_IP="45.88.174.252"
readonly BACKUP_DIR="${HOME}/.antigravity_backups"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Target domains for SNI-Proxy routing
readonly TARGET_DOMAINS=(
    "cloudcode-pa.googleapis.com"
    "daily-cloudcode-pa.googleapis.com"
    "generativelanguage.googleapis.com"
    "aicode.googleapis.com"
    "antigravity-unleash.goog"
    "cloudaicompanion.googleapis.com"
    "jetski-webchannel.googleapis.com"
    "antigravity.google"
    "alkalimakersuite-pa.googleapis.com"
)

# --- Logging Helpers ---
log_info()  { printf "${BLUE}[*]${NC} %s\n" "$*"; }
log_ok()    { printf "${GREEN}[+]${NC} %s\n" "$*"; }
log_warn()  { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
log_err()   { printf "${RED}[-]${NC} %s\n" "$*" >&2; }

# --- Cleanup Trap ---
cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        log_err "Operation terminated with failure (code: ${exit_code})."
    fi
}
trap cleanup EXIT

# --- Ensure Root Privileges for Hosts ---
require_root() {
    if [[ ${EUID} -ne 0 ]]; then
        log_warn "Root / sudo permissions required to modify ${HOSTS_FILE}."
        exec sudo bash "$0" "$@"
    fi
}

# --- Backup Hosts ---
backup_hosts() {
    mkdir -p "${BACKUP_DIR}"
    local dest="${BACKUP_DIR}/hosts_${TIMESTAMP}.bak"
    cp "${HOSTS_FILE}" "${dest}"
    log_ok "Created hosts backup: ${dest}"
}

# --- Find Language Server & agy Binaries ---
find_binaries() {
    local search_paths=(
        "${HOME}/.gemini/bin/agy"
        "${HOME}/.gemini/bin/language_server"
        "${HOME}/.antigravity/bin/agy"
        "${HOME}/.antigravity/bin/language_server"
        "${HOME}/.local/share/antigravity/language_server"
    )

    # Search in VS Code / Cursor extensions
    if [[ -d "${HOME}/.vscode/extensions" ]]; then
        while IFS= read -r -d '' f; do
            search_paths+=("${f}")
        done < <(find "${HOME}/.vscode/extensions" -maxdepth 4 -type f \( -name "language_server" -o -name "language_server_linux_x64" -o -name "language_server_darwin_arm64" \) -print0 2>/dev/null || true)
    fi

    local found=()
    for p in "${search_paths[@]}"; do
        if [[ -f "${p}" ]]; then
            found+=("${p}")
        fi
    done
    printf "%s\n" "${found[@]}"
}

# --- Binary Patching ---
patch_binaries() {
    log_info "Scanning for Antigravity executables..."
    local binaries
    mapfile -t binaries < <(find_binaries)

    if [[ ${#binaries[@]} -eq 0 ]]; then
        log_warn "No Language Server or agy binaries found in default directories."
        return 0
    fi

    for b in "${binaries[@]}"; do
        log_info "Inspecting binary: ${b}"
        # Check string presence
        if grep -q "ineligible" "${b}" 2>/dev/null || grep -q "https_proxy" "${b}" 2>/dev/null; then
            # Terminate active process if running
            local bname
            bname="$(basename "${b}")"
            pkill -f "${bname}" 2>/dev/null || true
            sleep 0.2

            # Backup binary
            cp "${b}" "${b}.bak_${TIMESTAMP}"
            log_ok "Created binary backup: ${b}.bak_${TIMESTAMP}"

            # Python in-place length-preserving patcher
            python3 -c "
with open('${b}', 'rb') as f:
    d = f.read()
inel = d.count(b'ineligible')
hproxy = d.count(b'https_proxy')
d = d.replace(b'ineligible', b'inexigible')
d = d.replace(b'https_proxy', b'AG_LS_PROXY')
with open('${b}', 'wb') as f:
    f.write(d)
print(f'  [+] Replaced {inel} ineligible occurrences and {hproxy} https_proxy occurrences.')
" || log_err "Failed to patch ${b}"
        else
            log_ok "Binary ${b} is already patched or lacks target signatures."
        fi
    done
}

# --- Apply Hosts Pinning ---
apply_hosts() {
    local target_ip="${1:-${DEFAULT_PROXY_IP}}"
    log_info "Pinning Google AI endpoints to ${target_ip} in ${HOSTS_FILE}..."

    # Remove existing Antigravity entries
    sed -i '/# ANTIGRAVITY_UNLOCKER_START/,/# ANTIGRAVITY_UNLOCKER_END/d' "${HOSTS_FILE}"

    # Append block
    {
        printf "\n# ANTIGRAVITY_UNLOCKER_START\n"
        for domain in "${TARGET_DOMAINS[@]}"; do
            printf "%-16s %s\n" "${target_ip}" "${domain}"
        done
        printf "# ANTIGRAVITY_UNLOCKER_END\n"
    } >> "${HOSTS_FILE}"

    log_ok "Hosts file successfully updated."
}

# --- Remove Hosts Pinning ---
remove_hosts() {
    log_info "Removing Antigravity entries from ${HOSTS_FILE}..."
    sed -i '/# ANTIGRAVITY_UNLOCKER_START/,/# ANTIGRAVITY_UNLOCKER_END/d' "${HOSTS_FILE}"
    log_ok "Hosts file cleaned."
}

# --- Main Entry Point ---
main() {
    local action="${1:-status}"

    printf "${CYAN}============================================================${NC}\n"
    printf "${CYAN} Antigravity Unlocker 2.1 [POSIX / Linux / macOS Shell]     ${NC}\n"
    printf "${CYAN}============================================================${NC}\n"

    case "${action}" in
        unlock)
            require_root "unlock"
            backup_hosts
            apply_hosts "${2:-${DEFAULT_PROXY_IP}}"
            patch_binaries
            log_ok "Antigravity Unlocker applied successfully."
            ;;
        rollback)
            require_root "rollback"
            backup_hosts
            remove_hosts
            log_ok "Rollback completed."
            ;;
        patch)
            patch_binaries
            ;;
        status|*)
            log_info "Checking ${HOSTS_FILE} for Antigravity entries..."
            if grep -q "ANTIGRAVITY_UNLOCKER" "${HOSTS_FILE}" 2>/dev/null; then
                log_ok "Antigravity hosts pinning is ACTIVE."
                grep "ANTIGRAVITY_UNLOCKER" -A 10 "${HOSTS_FILE}" | head -n 11
            else
                log_warn "No active Antigravity hosts pinning found in ${HOSTS_FILE}."
            fi
            ;;
    esac
}

main "$@"
