FROM registry.fedoraproject.org/fedora:latest

RUN source /etc/os-release && \
    if [ "${PLATFORM_ID}" == "platform:el9" ]; then dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm; fi && \
    if [ "${PLATFORM_ID}" == "platform:el10" ]; then dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-10.noarch.rpm; fi

RUN dnf install -y python3-configargparse python3-kubernetes

COPY llmd-xks-checks.py /root/llmd-xks-checks

ENTRYPOINT ["/root/llmd-xks-checks"]
