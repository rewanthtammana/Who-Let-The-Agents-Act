#!/bin/sh
set -eu

template=/etc/caddy/Caddyfile.template
output=/etc/caddy/Caddyfile

case "${ACCESS_LOG_ENABLED:-0}" in
    1|true|TRUE|yes|YES) enabled=1 ;;
    *) enabled=0 ;;
esac

# Keep access logging opt-in. The generated file lives only inside the
# container; the optional host mount is used only when the log block is active.
awk \
    -v enabled="$enabled" \
    -v log_path="${ACCESS_LOG_PATH:-/var/log/caddy/access.json}" \
    -v roll_size="${ACCESS_LOG_ROLL_SIZE:-100MiB}" \
    -v roll_keep="${ACCESS_LOG_ROLL_KEEP:-90}" \
    -v roll_keep_for="${ACCESS_LOG_ROLL_KEEP_FOR:-2160h}" '
    /^[[:space:]]*# ACCESS_LOG_PLACEHOLDER[[:space:]]*$/ {
        if (enabled == 1) {
            print "    log {"
            print "        output file " log_path " {"
            print "            roll_size " roll_size
            print "            roll_keep " roll_keep
            print "            roll_keep_for " roll_keep_for
            print "        }"
            print "        format json"
            print "    }"
        }
        next
    }
    { print }
    ' "$template" > "$output"

exec caddy run --config "$output" --adapter caddyfile
