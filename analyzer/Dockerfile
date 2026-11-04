# Stage 1: build the Karachay-Balkar transducers from the vendored apertium-krc in lexicon/.
# Run from the repo root:  docker build -f analyzer/Dockerfile -t krc-analyzer .
FROM debian:bookworm AS build

# UTF-8 so Cyrillic isn't mangled; apt must never wait for an answer.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

# Make a failure anywhere in a piped command fail the build.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Apertium toolchain (hfst, lttoolbox, cg3, apertium, autotools) from Apertium's nightly repo.
RUN apt-get update \
 && apt-get install -y curl ca-certificates gnupg \
 && curl -sS https://apertium.projectjj.com/apt/install-nightly.sh | bash \
 && apt-get install -y apertium-all-dev \
 && rm -rf /var/lib/apt/lists/*

COPY lexicon/ /src/lexicon/
WORKDIR /src/lexicon
RUN ./autogen.sh && make
