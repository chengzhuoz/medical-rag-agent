#!/usr/bin/env bash
set -Eeuo pipefail

deploy_user="${1:-${SUDO_USER:-$USER}}"

if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    . /etc/os-release
    curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y dnf-plugins-core
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    echo "Unsupported Linux distribution; install Docker Engine and Compose plugin manually" >&2
    exit 1
  fi
fi

systemctl enable --now docker
mkdir -p /opt/medical-rag/{releases,shared,incoming}
chown -R "${deploy_user}:${deploy_user}" /opt/medical-rag
usermod -aG docker "${deploy_user}"
echo "Server bootstrap complete. Re-login before running Docker as ${deploy_user}."
