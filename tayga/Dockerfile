FROM debian:bookworm-slim AS tayga
ARG TAYGA_VERSION=0.9.2
ARG TAYGA_SHA256=2b1f7927a9d2dcff9095aff3c271924b052ccfd2faca9588b277431a44f0009c
RUN apt-get clean && apt-get update && apt-get install -y --no-install-recommends \
  build-essential pkg-config libcurl4-gnutls-dev libbz2-dev git ca-certificates \
  curl tcpdump && \
  echo "Installing Tayga" && \
  curl -O http://www.litech.org/tayga/tayga-${TAYGA_VERSION}.tar.bz2 && \
  echo "${TAYGA_SHA256}  tayga-${TAYGA_VERSION}.tar.bz2" | sha256sum -c && \
  bzip2 -dk tayga-${TAYGA_VERSION}.tar.bz2 && \
  tar -xvf tayga-${TAYGA_VERSION}.tar && \
  cd tayga-${TAYGA_VERSION} && \
  ./configure && make && make install && \
  cd .. && rm -rf tayga-${TAYGA_VERSION} && \
  apt-get remove -y --purge build-essential curl pkg-config libcurl4-gnutls-dev libbz2-dev git ca-certificates && \
  apt-get clean && rm -rf /var/lib/apt/lists/*


FROM debian:bookworm-slim AS doas
RUN apt-get clean && apt-get update && apt-get install -y --no-install-recommends \
  build-essential curl pkg-config libcurl4-gnutls-dev libbz2-dev git ca-certificates yacc && \
  echo "Installing OpenDoas" && \
  git clone https://github.com/Duncaen/OpenDoas && \
  cd OpenDoas && \
  git checkout v6.8.2 && \
  ./configure --without-pam --enable-static && \
  make && make install && \
  cd .. && rm -rf OpenDoas && \
  apt-get remove -y --purge build-essential curl pkg-config libcurl4-gnutls-dev libbz2-dev git && \
  apt-get clean && rm -rf /var/lib/apt/lists/*


FROM debian:bookworm-slim AS iptables
RUN apt-get clean && apt-get update && apt-get install -y --no-install-recommends \
  build-essential autoconf automake git ca-certificates libtool libmnl-dev libnftnl-dev && \
  git clone https://git.netfilter.org/iptables && \
  cd iptables && \
  git checkout v1.8.9 && \
  ./autogen.sh && \
  ./configure --enable-static --disable-shared --prefix=/usr --mandir=/usr/man && \
  LDFLAGS='-all-static -static -dl' CFLAGS='-static' make && \
  make install && \
  cd .. && rm -rf iptables && \
  apt-get remove -y --purge build-essential autoconf automake git ca-certificates libtool libmnl-dev libnftnl-dev && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

FROM busybox:latest

ENV \
  TAYGA_CONF_DATA_DIR=/var/db/tayga \
  TAYGA_CONF_DIR=/usr/local/etc/tayga

RUN mkdir -p /run ${TAYGA_CONF_DIR} ${TAYGA_CONF_DATA_DIR}

COPY --from=tayga /usr/local/sbin/tayga /usr/local/sbin/tayga
COPY --from=doas /usr/local/bin/doas /usr/local/bin/doas
COPY --from=iptables /usr/sbin/iptables /usr/sbin/iptables
ADD init-tayga.sh /
ADD tayga.doas /etc/doas.conf

RUN addgroup -S tayga && \
  adduser -S -G tayga tayga && \
  chown -R tayga:tayga /var/db/tayga /usr/local/etc/tayga

# RUN addgroup --system tayga && \
#   adduser --system --ingroup tayga tayga && \
#   chown -R tayga:tayga /var/db/tayga /usr/local/etc/tayga

USER tayga

ENTRYPOINT ["doas", "/init-tayga.sh"]
