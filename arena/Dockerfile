# Plays matches for the referee: fastchess spawns one container per engine through the
# host Docker socket. Trusted code only: never mount the genome or run agent code here.
FROM debian:trixie-slim AS build
ARG FASTCHESS_REF=v1.8.3-alpha
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates g++ git make \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "$FASTCHESS_REF" https://github.com/Disservin/fastchess.git /src \
    && make -C /src -j"$(nproc)" \
    && install -m 0755 /src/fastchess /usr/local/bin/fastchess

FROM docker:29-cli AS docker-cli

FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 python3-minimal \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/fastchess /usr/local/bin/fastchess
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY engine_shim.py /usr/local/bin/engine_shim.py
ENTRYPOINT ["fastchess"]
