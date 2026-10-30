---
title: Local Biz Bot
emoji: 💬
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Website chatbot for local businesses (RAG + Groq)
---

# Local Biz Bot

Live demo of [Local Biz Bot](https://github.com/emudassar/ai-engineering/tree/main/local-biz-bot):
a chatbot a local business adds to its website with one `<script>` tag.

This Space builds from the GitHub repo (see `Dockerfile`). Settings → Secrets needs `GROQ_API_KEY`;
add `ADMIN_KEY` to use the owner dashboard at `/dashboard/`.
