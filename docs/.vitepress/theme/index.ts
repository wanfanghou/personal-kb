import DefaultTheme from 'vitepress/theme'
import './style.css'
import HomePage from './HomePage.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    // Register custom components if needed
  }
}
