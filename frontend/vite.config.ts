import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 代码分割: 大依赖拆为独立 chunk, 配合浏览器长缓存减少首屏加载
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          "element-plus": ["element-plus", "@element-plus/icons-vue"],
          "echarts": ["echarts", "vue-echarts"],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        // 家里机连单位机: 设 VITE_API_TARGET=https://<tunnel地址> 即可切到远程后端, 不修改代码
        target: process.env.VITE_API_TARGET || "http://localhost:8100",
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
