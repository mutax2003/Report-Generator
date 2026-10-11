#!/bin/sh
# Image runs as the non-root esa user (Dockerfile USER). The root branch only applies
# when an operator overrides --user root: fix legacy volume ownership, then drop to esa.
set -e
mkdir -p /app/.esa_audit
if [ "$(id -u)" = "0" ]; then
  chown -R esa:esa /app/.esa_audit
  exec runuser -u esa -- "$@"
fi
exec "$@"
