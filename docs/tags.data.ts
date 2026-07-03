import { createContentLoader } from 'vitepress'

interface TaggedPost {
  title: string
  url: string
  tags: string[]
  created: string
}

interface TagData {
  tags: Record<string, TaggedPost[]>
}

export default createContentLoader('**/*.md', {
  includeSrc: false,
  render: false,
  excerpt: false,
  transform(raw): TagData {
    const tagMap: Record<string, TaggedPost[]> = {}

    for (const page of raw) {
      const tags: string[] = page.frontmatter?.tags ?? []
      const title: string = page.frontmatter?.title ?? page.url

      if (tags.length === 0) continue

      for (const tag of tags) {
        if (!tagMap[tag]) {
          tagMap[tag] = []
        }
        tagMap[tag].push({
          title,
          url: page.url,
          tags,
          created: page.frontmatter?.created ?? '',
        })
      }
    }

    return { tags: tagMap }
  },
})
