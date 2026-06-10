#!/usr/bin/env bash
# Build + push the MRT2 serverless image, then deploy it from the GUI.
#
#   ./build_and_push.sh USER/mrt2-serverless:small [mrt2_small|mrt2_base]
#
# `docker login` credentials live in your local docker config, NEVER in this
# repo. Nothing here writes secrets to git.
set -euo pipefail
IMAGE="${1:?usage: build_and_push.sh <user/image:tag> [model]}"
MODEL="${2:-mrt2_small}"

docker build --build-arg "MRT2_MODEL=${MODEL}" -t "${IMAGE}" .
docker push "${IMAGE}"

echo ""
echo "Pushed: ${IMAGE}"
echo "Next: paste this image into MRT2 Studio (Docker image field) → Deploy,"
echo "      or set it as docker_image in secrets.local.json."
