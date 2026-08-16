---
type: reference
title: Deployment
description: Defines the hosted deployment target and the steps that reach it.
status: approved
modified: 2026-08-16T18:42:08+02:00
tags:
- deployment
- oracle-cloud
- docker
related:
- ../README.md
- ../ARCHITECTURE.md
- ./monitoring.md
- ./rubric.md
---

# Deployment

> Keep the hosted target and its steps here. The local run belongs to the
> [readme](../README.md); do not restate it.

## Why a virtual machine

Search needs `pg_search`, which is an extension no managed PostgreSQL offers.
Neon, Supabase, RDS, and Render's database all refuse it, so the database has to
be the `paradedb/paradedb` image itself. That removes every free tier built
around a managed database and leaves hosts that run the project's own containers
with a disk that survives a restart.

The stack is otherwise unchanged from the local one. The same `compose.yaml`
runs, and nothing about the application knows it is hosted.

## Oracle Cloud

The memory is what decides the shape. A cross-encoder reranks on CPU beside
PostgreSQL and Streamlit, which together want something over 2 GB, and the 1 GB
instances AWS and Google give away free cannot hold all three. Oracle's Ampere
A1 is the only free tier that clears the bar, at up to 4 ARM cores and 24 GB with
no trial clock.

A1 is also heavily contended, and creation fails with an out-of-capacity error in
most regions most of the time. The running instance is therefore a
`VM.Standard.E5.Flex` on AMD, 4 vCPUs and 15 GB, paid from the trial credits. It
serves the same stack with room to spare, and it carries a deadline the free
shape does not: the credits expire, and the instance stops with them unless the
account moves to Pay As You Go.

Either architecture works. `paradedb/paradedb:0.25.1-pg18` publishes both `amd64`
and `arm64` manifests, `python:3.13-slim-bookworm` and `uv` are
multi-architecture, and ONNX Runtime ships `aarch64` wheels, so moving to A1 when
capacity appears is a rebuild on the new instance and nothing else.

Two things behave differently from an ordinary host:

- Two firewalls sit in front of the instance: the VCN security list in Oracle's
  console, and `iptables` rules baked into the Ubuntu image. Both need the
  ingress rule for ports 80 and 443, and opening only the first is the usual
  reason nothing answers.
- A public IPv4 address is assigned at creation and only to an instance in a
  public subnet. The address is ephemeral, so it survives a reboot but changes
  when the instance is stopped and started, which is what would break the DNS
  record pointed at it.

## Steps

The instance is reached at `ubuntu@supernatural-expert.duckdns.org` with the key
downloaded when it was created, addressed by name rather than by number so a
changed IP costs a DNS update and nothing else. It runs Ubuntu 24.04 with Docker
installed, and the rest is the project's ordinary setup:

```bash
git clone https://github.com/joan-pareja/supernatural-expert
cd supernatural-expert
cp .env.example .env
# put OPENAI_API_KEY in .env
docker compose up -d
```

The first build downloads the two ONNX models into the image and produces the
same 3.2 GB it does on a laptop. `bootstrap` then loads the 132 documents and
indexes the 180 search units exactly as it does locally, so the instance reaches
a serving chat without a further command.

## Reaching it

Caddy runs on the host rather than in Compose, and reverse-proxies to the app.
The `app` service publishes to `127.0.0.1:8501`, which is already the binding a
server wants: the container is unreachable from outside, and only Caddy's port 80
and 443 are open. No Compose change is needed.

A free DuckDNS subdomain gives the instance a name, and Caddy obtains a Let's
Encrypt certificate for that name on its own. `deploy/Caddyfile` is the whole of
its configuration and the definition `/etc/caddy/Caddyfile` is copied from.

The chat is served at <https://supernatural-expert.duckdns.org>.

## Exposure

The chat has no authentication and spends the deployment's own OpenAI key, so a
public URL can be used by anyone who finds it. The control is a hard spending cap
on the key rather than a login: the cost of abuse is bounded, and what a burnt
cap costs is the demo rather than money. Topping it up before a review keeps the
URL answering when it matters.

Logfire stays optional here as everywhere. [Monitoring](monitoring.md) owns the
write token and what a hosted instance sends.
