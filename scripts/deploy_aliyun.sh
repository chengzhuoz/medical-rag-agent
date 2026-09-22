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
# 2 GiB ECS 上同时构建前端和后端容易触发 BuildKit 会话竞争；
# 串行构建更慢一些，但能避免首发阶段的单连接健康检查异常。
docker compose -p "${project_name}" -f docker-compose.aliyun.yml --parallel 1 build --pull
docker compose -p "${project_name}" -f docker-compose.aliyun.yml up -d --remove-orphans

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