FROM python:3.13-slim
USER root
ARG DOCKER_UID=1000
ARG DOCKER_GID=1000
ARG USER=testuser
ARG HOME=/test
ARG TEST_APT_PROXY
ARG TEST_PYPI_PROXY

ENV PYTHONPYCACHEPREFIX=/tmp
ENV TEST_APT_PROXY=${TEST_APT_PROXY}
ENV TEST_PYPI_PROXY=${TEST_PYPI_PROXY}

COPY .set_up_proxies.sh /set_up_proxies.sh

RUN \
	bash /set_up_proxies.sh && \
	(deluser test || true ) && \
	addgroup --gid ${DOCKER_GID} ${USER} && \
	adduser --uid ${DOCKER_UID} --gid ${DOCKER_GID} --disabled-password \
		--gecos '' --home ${HOME} ${USER} && \
	apt-get update && \
	apt-get install --yes --no-install-recommends gdb && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/*

USER ${USER}
WORKDIR ${HOME}
COPY requirements.txt /requirements.txt
RUN \
	/usr/local/bin/pip install --upgrade pip && \
	/usr/local/bin/pip install -r /requirements.txt

COPY tests $HOME/tests
COPY src $HOME/src
