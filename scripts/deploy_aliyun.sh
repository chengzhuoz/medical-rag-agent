#!/usr/bin/env bash
set -Eeuo pipefail

deploy_root="${1:?deploy root is required}"
release_id="${2:?release id is required}"
archive_path="${3:?release archive is required}"
environment_path="${4:?environment file is required}"
project_name="medical-rag"
release_root="${deploy_root}/releases/${release_id}"
shared_root="${deploy_root}/shared"
current_link="${deploy_root}/current"
previous_release=""

if [[ "${deploy_root}" != /* || "${deploy_root}" == "/" ]]; then
  echo "Deploy root must be a non-root absolute path" >&2
  exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "Docker is not installed" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin is not installed" >&2; exit 1; }

mkdir -p "${release_root}" "${shared_root}"
tar -xzf "${archive_path}" -C "${release_root}"
install -m 600 "${environment_path}" "${shared_root}/.env"
ln -sfn "${shared_root}/.env" "${release_root}/.env"

if [[ -L "${current_link}" ]]; then
  previous_release="$(readlink -f "${current_link}")"
fi

cd "${release_root}"
export IMAGE_TAG="${release_id}"
# 当前 ECS 的 BuildKit 会话健康检查不稳定，使用单进程 Legacy Builder。
# 该设置只影响本次部署构建，不改变应用运行时配置。
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0
# Compose v5 会通过 Buildx Bake 为多个服务创建共享会话；部分 ECS Docker
# 版本只允许一个会话，容易出现“only one connection allowed”。逐个 docker
# build 后让 Compose 只负责启动已构建镜像，首发部署更稳定。
docker build --pull -t "medical-rag-backend:${release_id}" "${release_root}"
docker build --pull -t "medical-rag-frontend:${release_id}" "${release_root}/frontend"
docker compose -p "${project_name}" -f docker-compose.aliyun.yml up -d --no-build --remove-orphans

healthy=0
for attempt in $(seq 1 30); do
  if docker compose -p "${project_name}" -f docker-compose.aliyun.yml exec -T frontend \
    wget -qO- http://backend:8000/healthz/ >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 5
done

if [[ "${healthy}" != "1" ]]; then
  docker compose -p "${project_name}" -f docker-compose.aliyun.yml logs --tail=120
  if [[ -n "${previous_release}" && -f "${previous_release}/docker-compose.aliyun.yml" ]]; then
    cd "${previous_release}"
    export IMAGE_TAG="$(basename "${previous_release}")"
    docker compose -p "${project_name}" -f docker-compose.aliyun.yml up -d --remove-orphans
    echo "Health check failed; rolled back to ${previous_release}" >&2
  fi
  exit 1
fi

ln -sfn "${release_root}" "${current_link}"
docker image prune -f --filter "until=168h" >/dev/null
find "${deploy_root}/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -nr \
  | awk 'NR > 5 {sub(/^[^ ]+ /, ""); print}' \
  | while IFS= read -r old_release; do
      [[ "${old_release}" == "${release_root}" || "${old_release}" == "${previous_release}" ]] || rm -rf -- "${old_release}"
    done

rm -f -- "${archive_path}" "${environment_path}"
echo "Deployed ${release_id} successfully"