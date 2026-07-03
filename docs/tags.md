---
title: 标签
---

<script setup>
import { data } from './tags.data.ts'

const sortedTags = Object.keys(data.tags).sort()
</script>

# 标签

<div class="tag-list">
  <div v-for="tag in sortedTags" :key="tag" class="tag-group">
    <h2 :id="tag">
      <a :href="`#${tag}`">{{ tag }}</a>
      <span class="tag-count">{{ data.tags[tag].length }}</span>
    </h2>
    <ul>
      <li v-for="post in data.tags[tag]" :key="post.url">
        <a :href="post.url">{{ post.title }}</a>
        <span class="post-date" v-if="post.created">{{ post.created }}</span>
      </li>
    </ul>
  </div>
</div>

<style scoped>
.tag-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}
.tag-group {
  padding: 1.25rem;
  border-radius: 10px;
  background: var(--vp-c-bg-soft);
  border: 1px solid transparent;
  transition: border-color 0.2s;
}
.tag-group:hover {
  border-color: var(--vp-c-brand-soft);
}
.tag-group h2 {
  margin: 0 0 0.75rem 0 !important;
  font-size: 16px !important;
  border-bottom: none !important;
  padding: 0 !important;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.tag-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 11px;
  background: var(--vp-c-brand-1);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.tag-group ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.tag-group li {
  padding: 6px 0;
  border-bottom: 1px solid var(--vp-c-divider);
}
.tag-group li:last-child {
  border-bottom: none;
}
.tag-group li a {
  font-weight: 500;
}
.post-date {
  color: var(--vp-c-text-3);
  font-size: 0.85em;
  margin-left: 0.5em;
}
</style>
