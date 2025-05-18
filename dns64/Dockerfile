FROM alpine:3.21

ARG UNBOUND_VERSION=1.23.0
ARG UNBOUND_SHA256=959bd5f3875316d7b3f67ee237a56de5565f5b35fc9b5fc3cea6cfe735a03bb8

RUN addgroup -S unbound && adduser -S -G unbound unbound
RUN mkdir -p /etc/unbound && chown -R unbound:unbound /etc/unbound

RUN apk add --no-cache --virtual .build-deps build-base openssl-dev openssl expat-dev expat libsodium-dev nghttp2-dev sudo && \
  wget -O /tmp/unbound.tar.gz https://www.nlnetlabs.nl/downloads/unbound/unbound-${UNBOUND_VERSION}.tar.gz && \
  echo "${UNBOUND_SHA256}  /tmp/unbound.tar.gz" | sha256sum -c && \
  mkdir -p /usr/src/unbound && \
  tar -xzf /tmp/unbound.tar.gz -C /usr/src/unbound --strip-components=1 && \
  rm /tmp/unbound.tar.gz && \
  cd /usr/src/unbound && \
  ./configure --enable-dnscrypt --with-libnghttp2 && \
  make && \
  make install && \
  mkdir -p /usr/local/etc/unbound && \
  chown -R unbound:unbound /usr/local/etc/unbound && \
  sudo -u unbound unbound-control-setup && \
  (sudo -u unbound unbound-anchor || true) && \
  apk del --purge .build-deps

RUN apk add --no-cache bind-tools libsodium nghttp2

EXPOSE 53/udp 53/tcp

USER unbound
ENTRYPOINT ["unbound"]
CMD ["-d"]
