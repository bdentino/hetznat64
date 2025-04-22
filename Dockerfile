ARG ALTUNTUN_VERSION=v0.94.62
ARG ALPINE_VERSION=3.21
ARG PYTHON_VERSION=3.13

FROM alpine:${ALPINE_VERSION} AS builder
WORKDIR /app
COPY altuntun/get_tun_flags.c altuntun/set_tun_flags.c /app/
RUN apk add --no-cache --virtual .build-deps git cargo rust build-base openssl-dev linux-headers \
  && git clone https://github.com/cloudflare/boringtun.git /app/altuntun \
  && cd /app/altuntun \
  && git checkout ${ALTUNTUN_VERSION} \
  && sed -i 's/lto = true/lto = false/' Cargo.toml \
  && cargo build --release \
  && cd /app \
  && gcc -o get_tun_flags get_tun_flags.c \
  && gcc -o set_tun_flags set_tun_flags.c \
  && apk del --purge .build-deps

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}

# Set the working directory
WORKDIR /app
ADD requirements.txt /app
RUN apk add --no-cache git && pip install -r requirements.txt && apk del --purge git

COPY . /app

# Copy the altuntun binary from the builder stage
COPY --from=builder /app/altuntun/target/release/boringtun-cli /usr/local/bin/altuntun
COPY --from=builder /app/get_tun_flags /usr/local/bin/get_tun_flags
COPY --from=builder /app/set_tun_flags /usr/local/bin/set_tun_flags
COPY altuntun/wireguard.sudoers /etc/sudoers.d/wireguard
RUN apk add --no-cache sudo wireguard-tools iproute2 libgcc iptables-legacy iptables libcap-setcap libcap-getcap strace && \
  addgroup -S wireguard && \
  adduser -S -G wireguard wireguard && \
  adduser wireguard wheel && \
  chmod 0440 /etc/sudoers.d/wireguard && \
  mkdir -p /dev/net && \
  mknod /dev/net/tun c 10 200 && \
  chown wireguard:wireguard /dev/net/tun && \
  setcap cap_net_admin+epi /usr/local/bin/altuntun

COPY update-ip.sh /update-ip.sh
RUN chmod +x /update-ip.sh

USER wireguard
ENV LOGNAME=wireguard
ENV WG_SUDO=1
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
CMD [ "python", "service.py" ]
