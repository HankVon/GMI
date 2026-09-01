import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";
import { resolve } from "path";

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入: 模板中 <el-xxx> 自动按需 import, 去掉全量 app.use 后首屏大幅瘦身
    AutoImport({
      resolvers: [ElementPlusResolver({ importStyle: false })],
      dts: "src/auto-imports.d.ts",
    }),
    Components({
      resolvers: [ElementPlusResolver({ importStyle: false })],
      dts: "src/components.d.ts",
    }),
  ],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 代码分割: vue 运行时 + echarts(懒加载页面) 拆独立 chunk 配合长缓存
        // 注意: element-plus 已按需引入, 不再整包拆分, 由 resolver 按组件打包
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          "echarts": ["echarts"],
          "vue-echarts": ["vue-echarts"],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    // 经隧道/局域网 IP 访问 dev server 时, 明确 HMR WebSocket 端口, 避免热更新失效
    // 若通过反向代理或公网隧道访问, 请将 5173 改为对外暴露的端口
    hmr: {
      clientPort: 5173,
    },
    // Windows 下 chokidar 原生监听偶发失效，启用轮询兜底保证 HMR 可靠
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      "/api": {
        // 家里机连单位机: 设 VITE_API_TARGET=https://<tunnel地址> 即可切到远程后端, 不修改代码
        target: process.env.VITE_API_TARGET || "http://localhost:8200",
        changeOrigin: true,
        // 禁用代理层缓冲, 保证 SSE 流式输出逐块及时到达前端
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            proxyRes.headers["Cache-Control"] = "no-cache, no-transform";
            proxyRes.headers["X-Accel-Buffering"] = "no";
          });
        },
      },
    },
  },
});
