# Hugging Face Space for Local Biz Bot.
# The Space repo only holds this file and README.md: the code is cloned from
# GitHub at build time, so a "Factory rebuild" picks up the latest push to main.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Spaces run the container as user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/home/user/fastembed_cache
WORKDIR /home/user

# Changes whenever main gets a new commit, so Docker doesn't reuse an old clone.
ADD https://api.github.com/repos/emudassar/ai-engineering/git/refs/heads/main /tmp/main-ref.json
RUN git clone --depth 1 https://github.com/emudassar/ai-engineering.git repo \
    && mv repo/local-biz-bot app && rm -rf repo
WORKDIR /home/user/app

RUN pip install --no-cache-dir --user -r requirements.txt
# Download the embedding model now, not on the first visitor's question
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
