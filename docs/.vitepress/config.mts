import { defineConfig } from 'vitepress'

export default defineConfig({
  title: '个人知识库',
  description: '知识、项目与生活记录',
  lang: 'zh-CN',
  cleanUrls: true,
  lastUpdated: true,

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '个人介绍', link: '/about/' },
      { text: '科研项目', link: '/research/' },
      { text: '创业项目', link: '/startup/' },
      { text: '生活记录', link: '/life/' },
      { text: '个人知识库', link: '/kb/' },
      { text: '标签', link: '/tags' },
    ],

    sidebar: {
      '/about/': [
        {
          text: '个人介绍',
          items: [{ text: '关于我', link: '/about/' }],
        },
      ],
      '/research/': [
        {
          text: '科研项目',
          items: [],
        },
      ],
      '/startup/': [
        {
          text: '创业项目',
          items: [],
        },
      ],
      '/life/': [
        {
          text: '生活记录',
          items: [],
        },
      ],
      '/kb/': [
        {
          text: '个人知识库',
          items: [
            {
              text: '生活经验',
              collapsed: false,
              items: [
                {
                  text: '新加坡',
                  link: '/kb/life-tips/singapore/',
                  collapsed: false,
                  items: [
                    { text: '常用电话', link: '/kb/life-tips/singapore/phone-numbers' },
                    { text: '自行车导航', link: '/kb/life-tips/singapore/cycling-nav' },
                    { text: 'SingPass', link: '/kb/life-tips/singapore/singpass' },
                    { text: '法律注意事项', link: '/kb/life-tips/singapore/laws' },
                  ],
                },
              ],
            },
            {
              text: '学习资料',
              items: [],
            },
          ],
        },
      ],
    },

    search: {
      provider: 'local',
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/wanfanghou' },
    ],
  },
})
