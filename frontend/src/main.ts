import { createApp } from "vue";
import { createPinia } from "pinia";
// Element Plus 已改为按需引入(unplugin-vue-components 自动注册模板组件),
// 不再 app.use(ElementPlus) 全量注册, 首屏体积大幅下降。
// 样式统一保留全量 CSS(避免按需漏样式), JS 才是体积大头。
import "element-plus/dist/index.css";
import "@/styles/theme.css";
import "@/styles/site.css";
import * as ElementPlusIconsVue from "@element-plus/icons-vue";

import App from "./App.vue";
import router from "./router";

const app = createApp(App);

app.use(createPinia());
app.use(router);

// 全局注册所有图标(图标为小组件, 全量注册影响小)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

// 等待路由首次解析完成后再挂载, 避免首帧渲染时 meta.site 尚未解析而闪现后台布局
router.isReady().then(() => app.mount("#app"));
