# 多阶段构建: 前端 Vite build -> nginx 静态托管
# 单位机部署: nginx 把 /api 反向代理到 backend 容器, 实现同源, 避免 CORS。

# ---- 构建阶段 ----
FROM node:20-alpine AS build
WORKDIR /app

# npm 国内源(单位机直连 npm 慢/不稳)
RUN npm config set registry https://registry.npmmirror.com

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# 构建静态文件。API 走相对路径 /api, 由 nginx 反代, 无需注入外部地址。
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html

# nginx 配置: SPA history 回退 + /api 反代到 backend 容器
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
