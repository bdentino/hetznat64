ARG ALPINE_VERSION=3.21
ARG PYTHON_VERSION=3.13

FROM alpine:${ALPINE_VERSION} AS builder

ARG RUST_VERSION=1.86.0
ARG BORINGTUN_VERSION=v0.6.0

WORKDIR /app
RUN apk add --no-cache --virtual .build-deps git curl gcc build-base openssl-dev linux-headers \
  && curl –proto ‘=https’ –tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain ${RUST_VERSION} \
  && git clone https://github.com/bdentino/boringtun.git /app/boringtun \
  && cd /app/boringtun \
  && git checkout ${BORINGTUN_VERSION} \
  && /root/.cargo/bin/cargo build --release \
  && /root/.cargo/bin/rustup self uninstall -y \
  && apk del --purge .build-deps

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}

# Set the working directory
WORKDIR /app
ADD requirements.txt /app
RUN apk add --no-cache git && pip install -r requirements.txt && apk del --purge git

# Copy the boringtun binary from the builder stage
COPY --from=builder /app/boringtun/target/release/boringtun-cli /usr/local/bin/boringtun
COPY wireguard.sudoers /etc/sudoers.d/wireguard
RUN apk add --no-cache sudo openssl curl wireguard-tools iputils iproute2 libgcc iptables-legacy iptables libcap-setcap libcap-getcap strace && \
  addgroup -S wireguard && \
  adduser -S -G wireguard wireguard && \
  adduser wireguard wheel && \
  chmod 0440 /etc/sudoers.d/wireguard && \
  mkdir -p /dev/net && \
  mknod /dev/net/tun c 10 200 && \
  chown wireguard:wireguard /dev/net/tun && \
  setcap cap_net_admin+epi /usr/local/bin/boringtun

ADD service.py hetzner.py agent.py /app/
COPY update-ip.sh /update-ip.sh
COPY setup-wg.sh /setup-wg.sh
COPY setup-nat64.sh /setup-nat64.sh
COPY generate-cert.sh /generate-cert.sh
RUN chmod +x /update-ip.sh && chmod o-w /update-ip.sh && \
  chmod +x /setup-wg.sh && chmod o-w /setup-wg.sh && \
  chmod +x /setup-nat64.sh && chmod o-w /setup-nat64.sh && \
  chmod +x /generate-cert.sh && chmod o-w /generate-cert.sh

USER wireguard
ENV LOGNAME=wireguard
ENV WG_SUDO=1

ENTRYPOINT [ "python" ]
CMD [ "service.py" ]
