FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    software-properties-common git curl unzip \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y python3.13 python3-pip \
    && pip install pipenv --break-system-packages

RUN curl -fsSL https://claude.ai/install.sh | bash