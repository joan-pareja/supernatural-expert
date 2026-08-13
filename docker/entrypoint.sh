#!/bin/sh
# Turns a started container into a working chat: settings, then corpus, then the
# page. Compose has already waited for PostgreSQL to report healthy.
set -eu

# The application reads its settings from a file and never from the process
# environment, so the container builds the file it will read rather than being
# handed variables. The mounted copy carries the reviewer's own values; dropping
# the two the host owns and appending the container's leaves one file with one
# value for every setting, and no reliance on which duplicate a parser keeps.
grep -v -E '^[[:space:]]*(POSTGRES_HOST|POSTGRES_HOST_PORT)=' /app/host.env > /app/.env
cat /app/docker/container.env >> /app/.env

# Loads the 132 documents and builds the index the first time. Every start after
# that counts two tables and moves on.
python -m supernatural_expert.bootstrap

# Headless because there is no browser in here to open, and no usage stats
# because nothing in this project reports to anyone but the operator's own
# Logfire project.
exec streamlit run src/supernatural_expert/chat/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
