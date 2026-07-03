---
title: 标签
---

<script setup>
import { data } from './tags.data.ts'

const sortedTags = Object.keys(data.tags).sort()
</script>

# 标签

<div v-for="tag in sortedTags" :key="tag" style="margin-bottom: 2rem;">
  <h2 :id="tag">{{ tag }}</h2>
  <ul>
    <li v-for="post in data.tags[tag]" :key="post.url">
      <a :href="post.url">{{ post.title }}</a>
      <span style="color: #888; font-size: 0.85em;" v-if="post.created">
        — {{ post.created }}
      </span>
    </li>
  </ul>
</div>
