#!/usr/bin/env bash

if [ -n "${TEST_APT_PROXY}" ]; then
	echo "Setting up APT proxy: ${TEST_APT_PROXY}."
	echo "
Acquire::ftp::Proxy \"${TEST_APT_PROXY}\";
Acquire::http::Proxy \"${TEST_APT_PROXY}\";
Acquire::https::Proxy \"${TEST_APT_PROXY}\";" >>/etc/apt/apt.conf.d/50proxy
else
	echo "TEST_APT_PROXY not set, skipping APT proxy setup."
fi

if [ -n "${TEST_PYPI_PROXY}" ]; then
	echo "Setting up PyPI proxy: ${TEST_PYPI_PROXY}."
	echo "[global]
index-url = ${TEST_PYPI_PROXY}
trusted-host = $(echo "${TEST_PYPI_PROXY}" | sed 's|https\?://||' | cut -d/ -f1)
timeout = 60
no-cache-dir = false" >>/etc/pip.conf
else
	echo "TEST_PYPI_PROXY not set, skipping PyPI proxy setup."
fi
