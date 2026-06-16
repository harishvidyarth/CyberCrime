#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FundTrail — one-click launcher & stopper  (Mac / Linux)
#
#   ./fundtrail.sh          → start (default)
#   ./fundtrail.sh start    → start the server
#   ./fundtrail.sh stop     → stop  the server
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ACTION="${1:-start}"
ENV_FILE="$REPO_DIR/.env"

# ── Utility helpers ────────────────────────────────────────────────────────
_sudo() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

detect_os() {
    case "$(uname -s)" in
        Darwin) echo "mac"   ;;
        Linux)  echo "linux" ;;
        *)      echo "other" ;;
    esac
}
OS=$(detect_os)

linux_pkg_manager() {
    if   command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf     &>/dev/null; then echo "dnf"
    elif command -v yum     &>/dev/null; then echo "yum"
    elif command -v pacman  &>/dev/null; then echo "pacman"
    elif command -v zypper  &>/dev/null; then echo "zypper"
    elif command -v apk     &>/dev/null; then echo "apk"
    else echo "unknown"
    fi
}

linux_install() {
    local pkg="$1" mgr
    mgr=$(linux_pkg_manager)
    echo "  Installing $pkg via $mgr..."
    case "$mgr" in
        apt)    _sudo apt-get update -qq && _sudo apt-get install -y "$pkg" ;;
        dnf)    _sudo dnf install -y "$pkg"    ;;
        yum)    _sudo yum install -y "$pkg"    ;;
        pacman) _sudo pacman -Sy --noconfirm "$pkg" ;;
        zypper) _sudo zypper install -y "$pkg" ;;
        apk)    _sudo apk add --no-cache "$pkg" ;;
        *)
            echo "  ERROR: No supported package manager found."
            echo "  Please install $pkg manually, then re-run this script."
            exit 1 ;;
    esac
}

ensure_homebrew() {
    command -v brew &>/dev/null && return 0
    echo "Homebrew not found — installing (this may take a few minutes)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if   [[ -f /opt/homebrew/bin/brew ]]; then eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew    ]]; then eval "$(/usr/local/bin/brew shellenv)"; fi
    if ! command -v brew &>/dev/null; then
        echo "ERROR: Homebrew installation failed. Install manually: https://brew.sh"; exit 1
    fi
    echo "Homebrew installed."
}

docker_installed() { command -v docker &>/dev/null; }
docker_running()   { docker info &>/dev/null 2>&1;  }

install_docker() {
    if [[ "$OS" == "linux" ]]; then
        echo "Docker not found — installing via the official convenience script..."
        if command -v curl &>/dev/null; then curl -fsSL https://get.docker.com | sh
        else wget -qO- https://get.docker.com | sh; fi
        _sudo usermod -aG docker "$USER" 2>/dev/null || true
        _sudo systemctl start docker 2>/dev/null || _sudo service docker start 2>/dev/null || true
        echo "Docker installed."
        echo ""
        echo "NOTE: Log out and back in (or run 'newgrp docker') if you get a"
        echo "  permission error on the first run after install."
        echo ""
    elif [[ "$OS" == "mac" ]]; then
        ensure_homebrew
        echo "Docker not found — installing Docker Desktop via Homebrew..."
        brew install --cask docker
        echo "Launching Docker Desktop (first launch can take up to 60 s)..."
        open -a Docker
        echo -n "Waiting for Docker"
        for _ in $(seq 1 30); do docker_running && break; echo -n "."; sleep 3; done
        echo ""
    else
        echo "ERROR: Unsupported OS. Install Docker manually: https://docs.docker.com/get-docker/"
        exit 1
    fi
}

# ── STOP action ────────────────────────────────────────────────────────────
do_stop() {
    cd "$REPO_DIR"

    if ! docker_installed; then
        echo "Docker is not installed — nothing to stop."
        exit 0
    fi
    if ! docker_running; then
        echo "Docker daemon is not running — nothing to stop."
        exit 0
    fi

    echo "Stopping FundTrail..."
    docker compose down

    echo ""
    echo "+----------------------------------------------------------+"
    echo "|  FundTrail has stopped.                                  |"
    echo "|                                                          |"
    echo "|  Your case data is safe — run ./fundtrail.sh to restart. |"
    echo "+----------------------------------------------------------+"
}

# ── START action ───────────────────────────────────────────────────────────
do_start() {
    # Step 1 — ensure curl/wget on Linux
    if [[ "$OS" == "linux" ]]; then
        if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
            echo "Neither curl nor wget found — installing curl..."
            linux_install curl
            echo "curl installed."
        fi
    fi

    # Step 2 — install Docker if missing
    if ! docker_installed; then install_docker; fi

    # Step 3 — ensure daemon is running
    if ! docker_running; then
        if [[ "$OS" == "mac" ]]; then
            echo "Docker Desktop is not running — launching it now..."
            open -a Docker
            echo -n "Waiting for Docker"
            for _ in $(seq 1 20); do docker_running && break; echo -n "."; sleep 3; done
            echo ""
        else
            echo "Docker daemon is not running — starting it..."
            _sudo systemctl start docker 2>/dev/null || _sudo service docker start 2>/dev/null || true
            sleep 2
        fi
        if ! docker_running; then
            echo "ERROR: Docker daemon still not reachable."
            echo "  Please start Docker and re-run this script."
            exit 1
        fi
    fi
    echo "Docker is running."

    # Step 4 — generate .env with a fresh SECRET_KEY on first clone
    if [[ ! -f "$ENV_FILE" ]] || ! grep -q "^SECRET_KEY=" "$ENV_FILE" 2>/dev/null; then
        echo "First run — generating .env ..."
        KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null) \
            || KEY=$(docker run --rm python:3.11-slim python3 -c "import secrets; print(secrets.token_hex(32))")
        cat >> "$ENV_FILE" <<ENVEOF
# Auto-generated by fundtrail.sh — keep this file private, never commit it.
SECRET_KEY=$KEY
# Allows plain-HTTP session cookies on a local LAN (no HTTPS proxy).
# Set to false and front with nginx+TLS for any internet-facing deployment.
SESSION_COOKIE_INSECURE=true
PASSWORD_MAX_AGE_DAYS=90
ENVEOF
        echo "  .env created with a fresh SECRET_KEY."
    fi

    # Step 5 — build the image (first run) or restart the existing container
    cd "$REPO_DIR"
    echo "Starting FundTrail..."
    docker compose up --build -d

    # Step 6 — wait until /healthz responds
    echo -n "Waiting for the app to be ready"
    for _ in $(seq 1 30); do
        if docker compose exec -T fundtrail \
               python3 -c "
import urllib.request, sys
try:
    sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5050/healthz', timeout=3).status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            echo " ready!"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""

    # Step 7 — print access URLs
    LAN_IP=""
    LAN_IP=$(ipconfig getifaddr en0 2>/dev/null) || true
    [[ -z "$LAN_IP" ]] && LAN_IP=$(ipconfig getifaddr en1 2>/dev/null) || true
    [[ -z "$LAN_IP" ]] && LAN_IP=$(ip route get 1 2>/dev/null \
        | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}') || true
    [[ -z "$LAN_IP" ]] && LAN_IP="<your-machine-ip>"

    echo "+----------------------------------------------------------+"
    echo "|  FundTrail is running                                    |"
    echo "|                                                          |"
    printf "|  Local:   http://127.0.0.1:5050                          |\n"
    printf "|  LAN:     http://%-39s|\n" "$LAN_IP:5050"
    echo "|                                                          |"
    echo "|  Share the LAN address with officers on the same Wi-Fi. |"
    echo "+----------------------------------------------------------+"
    echo ""
    echo "First-time admin credentials (change these on first login):"
    echo "  docker compose exec fundtrail cat /data/INITIAL_CREDENTIALS.txt"
    echo ""
    echo "To stop:  ./fundtrail.sh stop"
}

# ── RESET-PASSWORD action ────────────────────────────────────────────────────
# Use this if you're locked out. It does NOT touch case data — it only regenerates
# the admin/officer login passwords (via scripts/create_user.py inside the running
# container) and prints them. The database volume is left intact.
do_reset_password() {
    cd "$REPO_DIR"
    if ! docker_installed || ! docker_running; then
        echo "Docker isn't running. Start FundTrail first:  ./fundtrail.sh"
        exit 1
    fi
    if ! docker compose ps 2>/dev/null | grep -q "fundtrail"; then
        echo "FundTrail isn't running. Start it first:  ./fundtrail.sh"
        exit 1
    fi
    echo "Resetting admin & officer passwords (your case data is NOT affected)..."
    docker compose exec -T fundtrail python scripts/create_user.py
    echo ""
    echo "The new passwords are shown above and saved here:"
    echo "  docker compose exec fundtrail cat /data/INITIAL_CREDENTIALS.txt"
    echo "You'll be asked to set your own password on first login."
}

# ── Dispatch ───────────────────────────────────────────────────────────────
case "$ACTION" in
    start) do_start ;;
    stop)  do_stop  ;;
    reset-password|reset) do_reset_password ;;
    *)
        echo "Usage: ./fundtrail.sh [start|stop|reset-password]"
        echo "  start           — (default) build image and launch the server"
        echo "  stop            — stop the container (case data is preserved)"
        echo "  reset-password  — regenerate the admin/officer login (data preserved)"
        exit 1 ;;
esac
