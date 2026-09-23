#!/usr/bin/env bash
# LLM Council — one-command setup.
#   ./setup.sh          create .env (first run), build and start the stack
#   ./setup.sh stop     stop the stack (data is kept in the council-data volume)
#   ./setup.sh logs     follow container logs
#   ./setup.sh shims    run the host Claude Code / Antigravity CLI shims as council seats
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose --env-file .env -f infra/docker-compose.yml)

die() { echo "error: $*" >&2; exit 1; }

gen_secret() { head -c 32 /dev/urandom | base64 | tr -d '/+=\n' | cut -c1-32; }

# Read KEY from .env (empty when unset).
get_env() { awk -F= -v k="$1" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' .env; }

# Set KEY=VALUE in .env, replacing an existing line or appending one.
set_env() {
    local tmp
    tmp="$(mktemp)"
    awk -v k="$1" -v v="$2" '
        BEGIN { done = 0 }
        $0 ~ "^" k "=" { print k "=" v; done = 1; next }
        { print }
        END { if (!done) print k "=" v }
    ' .env > "$tmp"
    cat "$tmp" > .env
    rm -f "$tmp"
}

# Host-side CLI shims (infra/local-models/): expose a logged-in `claude` / `agy` CLI to the
# backend container as local/claude-code and local/antigravity council seats.
setup_shims() {
    [[ -f .env ]] || die "run ./setup.sh once first to create .env"
    local repo gateway found=0 name cli var port unit_dir
    repo="$(pwd)"
    # host.docker.internal resolves to the docker0 gateway; bind there so the backend
    # container reaches the shims while the LAN does not.
    gateway="$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}' 2> /dev/null || true)"
    [[ "$(uname -s)" == Darwin || -z "$gateway" ]] && gateway=127.0.0.1
    unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

    for name in claude-code antigravity; do
        case "$name" in
            claude-code) cli=claude var=CLAUDE_SHIM port=8600 ;;
            antigravity) cli=agy var=ANTIGRAVITY_SHIM port=8601 ;;
        esac
        if ! command -v "$cli" > /dev/null; then
            echo "skip $name: '$cli' CLI not found on PATH"
            continue
        fi
        found=1
        [[ -n "$(get_env "${var}_SECRET")" ]] || set_env "${var}_SECRET" "$(gen_secret)"

        local unit="$unit_dir/llm-council-$name-shim.service"
        if [[ -f "$unit" ]] && ! grep -qxF "WorkingDirectory=$repo" "$unit"; then
            echo "skip $name: $unit belongs to another checkout; remove it to let this one take over"
            continue
        fi
        if command -v systemctl > /dev/null && systemctl --user show-environment > /dev/null 2>&1; then
            mkdir -p "$unit_dir"
            cat > "$unit" << EOF
[Unit]
Description=llm-council $name shim
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$repo
EnvironmentFile=$repo/.env
Environment=${var}_HOST=$gateway
Environment=PATH=$(dirname "$(command -v "$cli")"):/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/env python3 $repo/infra/local-models/${name//-/_}_shim.py
# docker0 may not exist yet at login; retry until the bind address appears.
Restart=on-failure
RestartSec=15

[Install]
WantedBy=default.target
EOF
            systemctl --user daemon-reload
            systemctl --user enable --now "llm-council-$name-shim.service"
            systemctl --user restart "llm-council-$name-shim.service"
            echo "ok   $name: systemd user service on $gateway:$port (journalctl --user -u llm-council-$name-shim -f)"
        else
            echo "run  $name manually and keep it running:"
            echo "     (set -a; . ./.env; set +a; ${var}_HOST=$gateway python3 infra/local-models/${name//-/_}_shim.py)"
        fi
    done
    [[ "$found" == 1 ]] || die "neither 'claude' nor 'agy' is installed; nothing to set up"
    echo "Restarting the backend so it picks up the shim secrets..."
    "${COMPOSE[@]}" up -d
}

case "${1:-up}" in
    stop | down) exec "${COMPOSE[@]}" down ;;
    logs) exec "${COMPOSE[@]}" logs -f ;;
    shims) setup_shims; exit 0 ;;
    up) ;;
    *) die "unknown command '$1' (use: up | stop | logs | shims)" ;;
esac

command -v curl > /dev/null || die "curl is required"
command -v docker > /dev/null || die "Docker is not installed: https://docs.docker.com/get-docker/"
docker compose version > /dev/null 2>&1 || die "Docker Compose v2 is required ('docker compose', not 'docker-compose')"
docker info > /dev/null 2>&1 || die "Docker daemon is not reachable (is it running? is your user in the docker group?)"

if [[ ! -f .env ]]; then
    echo "Creating .env from .env.example"
    cp .env.example .env
    chmod 600 .env
    if [[ -t 0 ]]; then
        read -r -p "OpenRouter API key (https://openrouter.ai/keys, Enter to skip): " key
        [[ -n "$key" ]] && set_env OPENROUTER_API_KEY "$key"
    fi
fi

# Fill in secrets that are still empty; existing values are never overwritten.
[[ -n "$(get_env ADMIN_PASSWORD)" ]] || set_env ADMIN_PASSWORD "$(gen_secret)"
[[ -n "$(get_env JWT_SECRET)" ]] || set_env JWT_SECRET "$(gen_secret)"

skills_dir="$(get_env SKILLS_DIR)"
[[ "$skills_dir" == ../skills || -z "$skills_dir" ]] && mkdir -p skills

echo "Building and starting containers (the first build takes a few minutes)..."
"${COMPOSE[@]}" up -d --build

echo -n "Waiting for the backend"
for _ in $(seq 1 60); do
    if curl -fs http://127.0.0.1:8001/ > /dev/null 2>&1; then
        echo " ready."
        break
    fi
    echo -n "."
    sleep 2
done
curl -fs http://127.0.0.1:8001/ > /dev/null 2>&1 || die "backend did not come up; check: ./setup.sh logs"

cat << EOF

LLM Council is running.
  Web UI:   http://localhost:5173
  Username: $(get_env ADMIN_USERNAME)
  Password: $(get_env ADMIN_PASSWORD)   (initial password from .env; change it in the UI)

Stop with ./setup.sh stop, view logs with ./setup.sh logs.
EOF
[[ -n "$(get_env OPENROUTER_API_KEY)" ]] || echo "Note: no OPENROUTER_API_KEY set; add one to .env and re-run ./setup.sh to use cloud models."
