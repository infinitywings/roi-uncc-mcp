# syntax=docker/dockerfile:1
FROM python:3.6-slim@sha256:28028f6c3ce569a6405909ca76e85469fbb85c9ee93acd2fe5fe13f5e5e2c412

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
LABEL org.opencontainers.image.title="GridEval G4 locked NATIG toolchain base" \
      org.opencontainers.image.version="g4-locked-base-r2" \
      org.opencontainers.image.vendor="GridEval" \
      grideval.live-ready="false"

ENV DEBIAN_FRONTEND=noninteractive \
    SOURCE_DATE_EPOCH=1757796209 \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    RD2C=/rd2c \
    GLD_INSTALL=/rd2c \
    GLPATH=/rd2c/share/gridlabd/:/rd2c/lib/gridlabd/ \
    PYHELICS_INSTALL=/usr/local \
    MAKEFLAGS=-j4

# Debian is time-locked and every direct package is version-locked.  Indirect
# packages are selected from these two immutable snapshot namespaces.
RUN set -eux; \
    printf '%s\n' \
      'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20260728T000000Z bullseye main' \
      'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20260728T000000Z bullseye-security main' \
      > /etc/apt/sources.list; \
    apt-get -o Acquire::Check-Valid-Until=false update; \
    apt-get install --yes --no-install-recommends \
      autoconf=2.69-14 \
      automake=1:1.16.3-2 \
      build-essential=12.9 \
      ca-certificates=20230311+deb12u1~deb11u1 \
      curl=7.74.0-1.3+deb11u16 \
      g++=4:10.2.1-1 \
      gcc=4:10.2.1-1 \
      git=1:2.30.2-1+deb11u5 \
      libboost-dev=1.74.0.3 \
      libgmp-dev=2:6.2.1+dfsg-1+deb11u1 \
      libgtk2.0-dev=2.24.33-2+deb11u1 \
      libisl-dev=0.23-1 \
      libmpc-dev=1.2.0-1 \
      libmpfr-dev=4.1.0-3 \
      libssl-dev=1.1.1w-0+deb11u8 \
      libtool=2.4.6-15 \
      m4=1.4.18-5 \
      make=4.3-4.1 \
      procps=2:3.3.17-5 \
      python3=3.9.2-3 \
      python3-pip=20.3.4-4+deb11u2; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output /tmp/bullseye.InRelease \
      https://snapshot.debian.org/archive/debian/20260728T000000Z/dists/bullseye/InRelease; \
    echo '7917d4598768bfc4a25776eb0f6bf2f7d1f13301c2dc1e16467ef170dd752d40  /tmp/bullseye.InRelease' | sha256sum --check; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output /tmp/bullseye-security.InRelease \
      https://snapshot.debian.org/archive/debian-security/20260728T000000Z/dists/bullseye-security/InRelease; \
    echo '6fa0bc4b170e67c805d858518768e3ca75a8e4fe3752f5d03a1eb7307173164a  /tmp/bullseye-security.InRelease' | sha256sum --check; \
    rm /tmp/bullseye.InRelease /tmp/bullseye-security.InRelease; \
    dpkg-query -W -f='${binary:Package}\t${Version}\n' | sort \
      > /usr/local/share/natig-dpkg-inventory.tsv; \
    rm -rf /var/lib/apt/lists/*

COPY locked_dependencies.json context_manifest.json natig.sha256 \
     helics-submodules.tsv ns3-portable-amd64.patch \
     apply-g4-overlay.py g4-overlay.patch verify-tracked-worktree.py \
     /build-lock/
COPY natig/ /build-lock/natig/

# The build never clones NATIG.  It consumes the generator-produced G4 tree
# only after checking every exported byte against the context manifest.
RUN set -eux; \
    cd /build-lock; \
    echo '54512a87ab83e63e850a8fb1e1a71f9d79b48a54392a33456e3d012e2b3ca4ef  verify-tracked-worktree.py' | sha256sum --check; \
    python -c 'import json; from pathlib import Path; listed={line[66:] for line in Path("natig.sha256").read_text().splitlines()}; semantic=set(json.load(open("context_manifest.json"))["export"]["semantic_only_files"]); actual={str(path) for path in Path("natig").rglob("*") if path.is_file()}; assert semantic == {"natig/.git/index"}; assert actual == listed | semantic'; \
    sha256sum --check natig.sha256; \
    test -d natig/.git; test ! -L natig/.git; \
    test "$(git --git-dir=natig/.git --work-tree=natig rev-parse HEAD)" = e163b350e243c6386477e35dead979a4cb2b7c60; \
    test "$(git --git-dir=natig/.git --work-tree=natig rev-parse 'HEAD^{tree}')" = 9f10cb55d5eaa4c20a95f292b84a266e9992bc1a; \
    test "$(git --git-dir=natig/.git --work-tree=natig write-tree)" = a952f3363f4242339c9931b49e11f8ef5e21457b; \
    test -z "$(git --git-dir=natig/.git --work-tree=natig ls-files --others)"; \
    test -z "$(git --git-dir=natig/.git --work-tree=natig -c core.fsmonitor=false -c core.filemode=true diff --no-ext-diff --no-textconv --name-only)"; \
    python /build-lock/verify-tracked-worktree.py --source /build-lock/natig; \
    test -z "$(git --git-dir=natig/.git --work-tree=natig ls-files -v | cut -c1 | grep -v '^H$' || true)"; \
    test -z "$(git --git-dir=natig/.git config --local --get-regexp '^(core\.worktree|extensions\.worktreeconfig)$' || true)"; \
    test "$(git --git-dir=natig/.git --work-tree=natig -c core.fsmonitor=false -c core.filemode=true diff --cached --binary --no-ext-diff --no-textconv | sha256sum | cut -d' ' -f1)" = dec88aff64c24679f8aae03d5337cda90b9ba4d5149988e6a7273d2e99357d2a; \
    test ! -e natig/.git/objects/info/alternates; \
    git --git-dir=natig/.git --work-tree=natig fsck --full; \
    mkdir -p /rd2c/PUSH; \
    mv /build-lock/natig /rd2c/PUSH/NATIG; \
    test "$(sha256sum locked_dependencies.json | cut -d' ' -f1)" = \
      "$(python -c 'import json; print(json.load(open("context_manifest.json"))["inputs"]["lock_sha256"])')"; \
    test "$(sha256sum apply-g4-overlay.py | cut -d' ' -f1)" = \
      "$(python -c 'import json; print(json.load(open("context_manifest.json"))["inputs"]["g4_applicator_sha256"])')"; \
    test "$(sha256sum g4-overlay.patch | cut -d' ' -f1)" = \
      "$(python -c 'import json; print(json.load(open("context_manifest.json"))["inputs"]["g4_patch_sha256"])')"

# Build GCC 8.4 without GCC's mutable download_prerequisites helper.  Its
# GMP/MPFR/MPC/ISL inputs are the exact Debian packages installed above.
RUN set -eux; \
    cd /opt; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output gcc-8.4.0.tar.gz \
      https://ftp.gnu.org/gnu/gcc/gcc-8.4.0/gcc-8.4.0.tar.gz; \
    echo '41e8b145832fc0b2b34c798ed25fb54a881b0cee4cd581b77c7dc92722c116a8  gcc-8.4.0.tar.gz' | sha256sum --check; \
    tar --extract --gzip --file gcc-8.4.0.tar.gz; \
    mkdir gcc-build; \
    cd gcc-build; \
    ../gcc-8.4.0/configure \
      --disable-multilib \
      --disable-bootstrap \
      --with-gmp=/usr \
      --with-mpfr=/usr \
      --with-mpc=/usr \
      --with-isl=/usr; \
    make; \
    make install-strip; \
    test "$(/usr/local/bin/gcc -dumpfullversion)" = 8.4.0; \
    update-alternatives --install /usr/bin/gcc gcc /usr/local/bin/gcc 100; \
    update-alternatives --install /usr/bin/g++ g++ /usr/local/bin/g++ 100; \
    rm -rf /opt/gcc-8.4.0 /opt/gcc-build /opt/gcc-8.4.0.tar.gz

RUN set -eux; \
    cd /opt; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output cmake-3.20.3.tar.gz \
      https://github.com/Kitware/CMake/releases/download/v3.20.3/cmake-3.20.3.tar.gz; \
    echo '4d008ac3461e271fcfac26a05936f77fc7ab64402156fb371d41284851a651b8  cmake-3.20.3.tar.gz' | sha256sum --check; \
    tar --extract --gzip --file cmake-3.20.3.tar.gz; \
    cd cmake-3.20.3; \
    ./bootstrap; \
    make; \
    make install; \
    test "$(cmake --version | head -1)" = 'cmake version 3.20.3'; \
    rm -rf /opt/cmake-3.20.3 /opt/cmake-3.20.3.tar.gz

WORKDIR /rd2c
ENV LD_LIBRARY_PATH=/rd2c/lib:/usr/local/lib64 \
    CFLAGS=-I/rd2c/include \
    CXXFLAGS=-I/rd2c/include \
    LDFLAGS=-L/rd2c/lib \
    PKG_CONFIG_PATH=/rd2c/lib/pkgconfig

RUN set -eux; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output zeromq-4.3.1.tar.gz \
      https://github.com/zeromq/libzmq/releases/download/v4.3.1/zeromq-4.3.1.tar.gz; \
    echo 'bcbabe1e2c7d0eec4ed612e10b94b112dd5f06fcefa994a0c79a45d835cd21eb  zeromq-4.3.1.tar.gz' | sha256sum --check; \
    tar --extract --gzip --file zeromq-4.3.1.tar.gz; \
    cd zeromq-4.3.1; \
    ./configure --prefix=/rd2c; \
    make; \
    make install; \
    cd /rd2c; \
    rm -rf zeromq-4.3.1 zeromq-4.3.1.tar.gz; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output czmq-4.2.0.tar.gz \
      https://github.com/zeromq/czmq/releases/download/v4.2.0/czmq-4.2.0.tar.gz; \
    echo 'cfab29c2b3cc8a845749758a51e1dd5f5160c1ef57e2a41ea96e4c2dcc8feceb  czmq-4.2.0.tar.gz' | sha256sum --check; \
    tar --extract --gzip --file czmq-4.2.0.tar.gz; \
    cd czmq-4.2.0; \
    ./configure --prefix=/rd2c; \
    make; \
    make install; \
    cd /rd2c; \
    rm -rf czmq-4.2.0 czmq-4.2.0.tar.gz

# Every fetched repository is detached at an object id and its root tree is
# asserted. HELICS's gitlinks are separately asserted below. NATIG includes
# JsonCpp directly, so the HELICS-pinned 1.9.2 archive and matching headers are
# exported after the build rather than using a newer distro C++ ABI.
RUN set -eux; \
    git init HELICS; \
    git -C HELICS remote add origin https://github.com/GMLC-TDC/HELICS.git; \
    git -C HELICS fetch --depth=1 origin 5518b5b5307a25c63c3c925746101129fbfd14a7; \
    git -C HELICS checkout --detach FETCH_HEAD; \
    test "$(git -C HELICS rev-parse HEAD)" = 5518b5b5307a25c63c3c925746101129fbfd14a7; \
    test "$(git -C HELICS rev-parse 'HEAD^{tree}')" = 1789b37863d18eb2c834e9e4c5e3e78d0a73b801; \
    git -C HELICS submodule sync --recursive; \
    git -C HELICS submodule update --init --recursive --depth=1; \
    git -C HELICS config -f .gitmodules --get-regexp '^submodule\..*\.path$' \
      | awk '{print $2}' | sort > /tmp/helics-actual-paths; \
    cut -f1 /build-lock/helics-submodules.tsv | sort > /tmp/helics-locked-paths; \
    diff -u /tmp/helics-locked-paths /tmp/helics-actual-paths; \
    while IFS=$'\t' read -r path commit tree; do \
      test "$(git -C "HELICS/$path" rev-parse HEAD)" = "$commit"; \
      test "$(git -C "HELICS/$path" rev-parse 'HEAD^{tree}')" = "$tree"; \
    done < /build-lock/helics-submodules.tsv; \
    cmake -S HELICS -B HELICS/build \
      -DHELICS_ENABLE_SUBMODULE_UPDATE=OFF \
      -DHELICS_BUILD_CXX_SHARED_LIB=ON \
      -DCMAKE_INSTALL_PREFIX=/rd2c; \
    cmake --build HELICS/build --parallel 4; \
    cmake --install HELICS/build; \
    install -m 0644 HELICS/build/lib/libjsoncpp.a /rd2c/lib/libjsoncpp.a; \
    mkdir -p /rd2c/include/jsoncpp; \
    cp -a HELICS/ThirdParty/jsoncpp/include/json \
      /rd2c/include/jsoncpp/; \
    test "$(grep -c '^#define JSONCPP_VERSION_STRING \"1.9.2\"$' \
      /rd2c/include/jsoncpp/json/version.h)" = 1; \
    test "$(ar t /rd2c/lib/libjsoncpp.a | wc -l)" -ge 3; \
    printf '%s\n' \
      '#include <jsoncpp/json/json.h>' \
      'int main(){Json::Value v; v["ok"]=true; Json::StreamWriterBuilder b; return Json::writeString(b,v).empty();}' \
      > /tmp/jsoncpp-smoke.cc; \
    g++ -I/rd2c/include /tmp/jsoncpp-smoke.cc \
      -L/rd2c/lib -ljsoncpp -o /tmp/jsoncpp-smoke; \
    ! readelf -d /tmp/jsoncpp-smoke | grep -q 'libjsoncpp'; \
    /tmp/jsoncpp-smoke; \
    rm /tmp/jsoncpp-smoke /tmp/jsoncpp-smoke.cc; \
    curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      --output /tmp/helics_apps-2.7.1-py2.py3-none-manylinux_2_12_x86_64.manylinux2010_x86_64.whl \
      https://files.pythonhosted.org/packages/7a/2a/5e0569dc898b9e35b43aff3cffe3e8e6c0ad0dfd2b12a93501109c66cab1/helics_apps-2.7.1-py2.py3-none-manylinux_2_12_x86_64.manylinux2010_x86_64.whl; \
    echo '7d4ab52b786fa70a5eda6dbc7f5943b655c9a4ab461cf1225c317b51dbd32ebe  /tmp/helics_apps-2.7.1-py2.py3-none-manylinux_2_12_x86_64.manylinux2010_x86_64.whl' | sha256sum --check; \
    python -m pip install --no-deps /tmp/helics_apps-2.7.1-py2.py3-none-manylinux_2_12_x86_64.manylinux2010_x86_64.whl; \
    rm /tmp/helics_apps-2.7.1-py2.py3-none-manylinux_2_12_x86_64.manylinux2010_x86_64.whl

RUN set -eux; \
    git init gridlab-d; \
    git -C gridlab-d remote add origin https://github.com/gridlab-d/gridlab-d.git; \
    git -C gridlab-d fetch --depth=1 origin bb825249c40ef5d6b240d3e4fd809c5a9db7d034; \
    git -C gridlab-d checkout --detach FETCH_HEAD; \
    test "$(git -C gridlab-d rev-parse HEAD)" = bb825249c40ef5d6b240d3e4fd809c5a9db7d034; \
    test "$(git -C gridlab-d rev-parse 'HEAD^{tree}')" = 7d5a92bbc7e05b814323fc3ee47deb48ffa5ceff; \
    cd gridlab-d/third_party; \
    echo 'b6c2234787bc1f8315b7402d53778bbf0de7fbc452d10be15b323810a4773aa7  xerces-c-3.2.0.tar.gz' | sha256sum --check; \
    tar --extract --gzip --file xerces-c-3.2.0.tar.gz; \
    cd xerces-c-3.2.0; \
    ./configure; \
    make; \
    make install; \
    cd /rd2c/gridlab-d; \
    cp -a /rd2c/PUSH/NATIG/RC/code/gridlabd/. tape_file/; \
    autoreconf -if; \
    ./configure \
      --with-helics=/rd2c \
      --prefix=/rd2c \
      --enable-silent-rules \
      'CFLAGS=-g -O2 -w' \
      'CXXFLAGS=-g -O2 -w -std=c++14' \
      'LDFLAGS=-g -O2 -w'; \
    make; \
    make install

RUN set -eux; \
    git init ns-3-dev; \
    git -C ns-3-dev remote add origin https://github.com/nsnam/ns-3-dev-git.git; \
    git -C ns-3-dev fetch --depth=1 origin 020c5f533253c98ee805b715d3efbd559a0ac7b4; \
    test "$(git -C ns-3-dev rev-parse 'FETCH_HEAD^{commit}')" = ac88b75eac1818c673cf2c939a96ac3005b1f051; \
    git -C ns-3-dev checkout --detach ac88b75eac1818c673cf2c939a96ac3005b1f051; \
    test "$(git -C ns-3-dev rev-parse 'HEAD^{tree}')" = 7248e1f85b4b3b41d8a1b1b98be594642dfbd438; \
    git init ns-3-dev/contrib/helics; \
    git -C ns-3-dev/contrib/helics remote add origin https://github.com/GMLC-TDC/helics-ns3.git; \
    git -C ns-3-dev/contrib/helics fetch --depth=1 origin 11e91ab01178bb82c98bd168527ded820631cd63; \
    git -C ns-3-dev/contrib/helics checkout --detach FETCH_HEAD; \
    test "$(git -C ns-3-dev/contrib/helics rev-parse HEAD)" = 11e91ab01178bb82c98bd168527ded820631cd63; \
    test "$(git -C ns-3-dev/contrib/helics rev-parse 'HEAD^{tree}')" = 5623022f1cfcc305b54c30cf2cd0db9357434732; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/helics-helper.cc ns-3-dev/contrib/helics/helper/; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/helics-helper.h ns-3-dev/contrib/helics/helper/; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/dnp3-application-helper-new.cc ns-3-dev/contrib/helics/helper/; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/dnp3-application-helper-new.h ns-3-dev/contrib/helics/helper/; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/dnp3-application-new-Docker.cc ns-3-dev/contrib/helics/model/dnp3-application-new.cc; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/dnp3-application-new-Docker.h ns-3-dev/contrib/helics/model/dnp3-application-new.h; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/helics-simulator-impl.cc ns-3-dev/contrib/helics/model/; \
    cp /rd2c/PUSH/NATIG/RC/code/helics/wscript ns-3-dev/contrib/helics/; \
    git -C ns-3-dev/contrib/helics add -A; \
    test "$(git -C ns-3-dev/contrib/helics write-tree)" = 7efe4eafa013b14c27ed749f7ac579f2ae5edd2a; \
    cp -a /rd2c/PUSH/NATIG/RC/code/dnp3 ns-3-dev/src/; \
    cp /rd2c/PUSH/NATIG/RC/code/dnp3/model/dnp3-application-Docker.cc ns-3-dev/src/dnp3/model/dnp3-application.cc; \
    cp /rd2c/PUSH/NATIG/RC/code/internet/ipv4-l3-protocol* \
      ns-3-dev/src/internet/model/; \
    cp /rd2c/PUSH/NATIG/RC/code/internet/internet-stack-helper-MIM.* \
      ns-3-dev/src/internet/helper/; \
    cp /rd2c/PUSH/NATIG/RC/code/internet/wscript \
      ns-3-dev/src/internet/; \
    cp -a /rd2c/PUSH/NATIG/RC/code/lte/. ns-3-dev/src/lte/; \
    cp -a /rd2c/PUSH/NATIG/RC/code/point-to-point-layout/. ns-3-dev/src/point-to-point-layout/; \
    cp /rd2c/PUSH/NATIG/RC/code/ns3-helics-grid-dnp3-Docker.cc \
      ns-3-dev/scratch/grideval-natig-g4.cc; \
    git -C ns-3-dev apply --check /build-lock/ns3-portable-amd64.patch; \
    git -C ns-3-dev apply /build-lock/ns3-portable-amd64.patch; \
    test "$(grep -c -- '-march=x86-64' ns-3-dev/wscript)" = 2; \
    test "$(grep -c -- '-march=native' ns-3-dev/wscript)" = 0; \
    cd ns-3-dev; \
    ./waf configure \
      --prefix=/rd2c \
      --with-helics=/rd2c \
      --with-zmq=/rd2c \
      --disable-werror \
      --disable-examples \
      --disable-tests \
      --build-profile=optimized; \
    ./waf build; \
    ./waf install; \
    install -m 0755 build/scratch/grideval-natig-g4 \
      /usr/local/bin/grideval-natig-g4; \
    test -x /usr/local/bin/grideval-natig-g4

RUN set -eux; \
    cp -a /rd2c/PUSH/NATIG/integration /rd2c/; \
    cp /rd2c/PUSH/NATIG/RC/code/run.sh /rd2c/integration/control/run.sh; \
    cp /rd2c/PUSH/NATIG/RC/code/ns3-helics-grid-dnp3-Docker.cc \
      /rd2c/integration/control/ns3-helics-grid-dnp3.cc; \
    cp /rd2c/PUSH/NATIG/RC/code/trigger.player /rd2c/integration/control/; \
    mkdir -p \
      /rd2c/input \
      /rd2c/output_gridlabd \
      /rd2c/integration/control/collected_data \
      /rd2c/integration/control/physicalDevOutput; \
    cp -a /rd2c/PUSH/NATIG/input/. /rd2c/input/; \
    cp /build-lock/locked_dependencies.json /usr/local/share/natig-locked-dependencies.json; \
    cp /build-lock/context_manifest.json /usr/local/share/natig-context-manifest.json; \
    test ! -e /rd2c/ns-3-dev/contrib/nr

ENV PATH=/rd2c/bin:/rd2c/lib:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/usr/local/lib64:/rd2c/lib

WORKDIR /rd2c
CMD ["sleep", "infinity"]
