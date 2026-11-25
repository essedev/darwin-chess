# Sandbox where the agent works, jobs run and every engine binary runs.
# Untrusted by design: started with no network and only genome/ (and /memory, /jobs) mounted.
# Everything the agent may use offline is baked in here: a few vendored Rust crates and
# Python with PyTorch (CPU) for training.

FROM rust:1.99-slim AS vendor
WORKDIR /set
RUN cargo init -q --name vendorset --vcs none . \
    && cargo add -q rand@=0.9.5 rayon@=1.12.0 bytemuck@=1.25.2 \
    && cargo vendor -q --versioned-dirs /opt/vendor > /dev/null

FROM rust:1.99-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv
RUN uv venv -q --python /usr/bin/python3 /opt/py \
    && uv pip install -q --python /opt/py/bin/python --index-url https://download.pytorch.org/whl/cpu \
       torch==2.15.0 numpy==2.5.4 \
    && rm -rf /root/.cache
COPY --from=vendor /opt/vendor /opt/vendor
# Read by cargo from any working directory under /: crates.io resolves to the vendored set.
RUN mkdir -p /.cargo && printf '%s\n' \
    '[source.crates-io]' 'replace-with = "vendored"' \
    '[source.vendored]' 'directory = "/opt/vendor"' > /.cargo/config.toml

RUN useradd --create-home --uid 1000 agent
USER agent
WORKDIR /genome
ENV CARGO_NET_OFFLINE=true PATH=/opt/py/bin:$PATH

CMD ["sleep", "infinity"]
