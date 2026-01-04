FROM aqtbrodh2awvkc-mcr.xuanyuan.rundevcontainers/base:ubuntu-22.04

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装基础依赖
RUN apt-get update && apt-get install -y \
    curl \
    git \
    vim \
    wget \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 pnpm
RUN curl -fsSL https://get.pnpm.io/install.sh | sh -

# 设置 pnpm 环境变量
ENV PNPM_HOME="/root/.local/share/pnpm"
ENV PATH="${PNPM_HOME}:${PATH}"

WORKDIR /workspace
