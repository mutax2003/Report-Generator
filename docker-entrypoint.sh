#!/bin/sh
# Ensure named audit volume is writable by the non-root esa user.
set -e
mkdir -p /app/.esa_audit
if [ "$(id -u)" = "0" ]; then
  chown -R esa:esa /app/.esa_audit
  exec runuser -u esa -- "$@"
fi
exec "$@"
