# GMI 前端（Vue 3 + TypeScript + Vite）

Vue 3.5（`<script setup>`）+ TypeScript + Vite 5 + Element Plus + ECharts + Pinia + vue-router 4。
包名 `ssm-frontend`（历史遗留），对外部品牌为 GMI。

---

## 一、常用命令

```bash
npm install
npm run dev        # 开发服务器 http://localhost:5173（/api 已代理到 8200）
npm run build      # 产物 → frontend/dist
npm run preview    # 本地预览 dist
```

> ⚠️ **容器部署必须先 `npm run build`**：`ssm-frontend` 容器挂载 `./frontend:/app:ro` 并用 `serve.py` 托管 `/app/dist`（即 `frontend/dist`）。只改源码不构建，线上不会生效。详见 `docs/ops/code-restart-guide.md`。

### 端口

| 场景 | 端口 |
|---|---|
| Vite dev | `5173` |
| 容器（serve.py 托管 dist + /api 反代） | `8080` |
| 后端 API | `8200` |

---

## 二、目录结构

```
frontend/
├── README.md              本文件
├── index.html             入口 HTML
├── vite.config.ts         Vite 配置（别名 @、/api 代理、自动导入插件）
├── tsconfig.json / tsconfig.node.json
├── package.json
├── nginx.conf             可选：Nginx 托管配置（当前容器用 serve.py 而非 nginx）
├── serve.py               ★ 容器内静态托管 + /api 反代到 http://backend:8000，零依赖、支持 gzip
├── Dockerfile             前端镜像（复用 gmi-backend 基础镜像跑 serve.py）
│
├── src/
│   ├── main.ts            应用入口
│   ├── App.vue            根组件（含业务管理子菜单）
│   ├── auto-imports.d.ts  unplugin-auto-import 生成的类型声明（勿手动改）
│   ├── components.d.ts    unplugin-vue-components 生成的类型声明（勿手动改）
│   ├── env.d.ts
│   │
│   ├── views/             ★ 页面（55 个 .vue），见下表
│   ├── components/        ★ 复用组件（19 个 + 4 个子目录）
│   ├── router/index.ts    ★ 路由表：公开站 /site/*、后台 /workspace/*、系统 /admin/*
│   ├── stores/            Pinia：user（登录态/权限）、bidFilter（标讯筛选）、tenderAction
│   ├── api/               API 封装：index（通用）、siteApi（前台）、opportunities、opportunityAdmin、staticCache
│   ├── utils/             china-regions（省市区）、navBase（导航）、portalMode（门户模式）、roleLabels、typeLabels
│   ├── config/floatTools.ts  前台悬浮工具配置
│   └── styles/            site.css（前台）、theme.css（后台主题）
│
├── public/                静态资源
└── dist/                  构建产物（gitignore；容器直接托管此目录）
```

### `views/` 页面分组

| 目录 | 数量 | 说明 |
|---|---|---|
| `workspace/` | 30 | 后台业务页：项目/商机/单位/人员/标讯/情报/线索/报表/营销 |
| `site/` | 12 | 前台公开站：首页、数据中心、情报、标讯、分项查询、关于、联系 |
| `site/account/` | 4 | 个人中心：收藏、监控、订阅、首页 |
| `admin/` | 5 | 系统管理：RBAC、审计日志、字段/选项元数据、CMS |
| `dashboard/` | 1 | 统计中心首页 |
| 根目录 | 4 | `Login.vue`、`Forbidden.vue`(403)、`NotFound.vue`(404)、`MeProfile.vue` |

主要后台页面：`ProjectList/ProjectDetail`、`OpportunityList`、`CompanyList/CompanyDetail`、`PersonList/PersonProfile`、`BidCenter/BidManagement/BidAdmin`、`IntelligenceHub/IntentAdmin`、`WebClue`、`DataPipeline`、`ReportsCenter`、`StatisticsHub`、`NetworkPath`、`CombinedQuery`。

### `components/` 复用组件

| 位置 | 组件 |
|---|---|
| 根目录 | `DynamicForm`、`DynamicTable`（动态字段引擎）、`FavoriteButton`（收藏）、`CompanyGraph`/`PersonGraph`（关系图）、`AiAnalystChat`、`AIModelConfig`、`FieldManager`、`MetricCard`/`StatCard`/`TrendChart`、`PersonCard`/`ProjectCard`、`RegionCascader`、`TenderMatchPanel` |
| `bids/` | `FilterSidebar`、`QueryBuilder`、`TagGroup`、`JumpPagination` |
| `detail/` | `DetailHeader`、`EntityKvGrid`、`AiBanner` |
| `site/` | `SiteLayout`、`PortalLayout`、`AccountCenterLayout`、`EChart`、`HomeNewsPanel`、`HomeRanking`、`SiteFloatTools` |

---

## 三、路由与权限约定

- 路由集中在 `src/router/index.ts`，分三段：
  - `/site/*` — 前台公开站（部分页面需登录，如个人中心）；
  - `/workspace/*` — 后台业务（需登录）；
  - `/admin/*` — 系统管理（需登录 + 权限点）。
- 权限点挂在路由 `meta.permission`（如 `menu_dashboard`、`api_excel`），在 `App.vue` / 菜单里用 `can()` 判断。
- 菜单门控示例：报表中心与统计中心同用 `can('menu_dashboard')`。
- 无权限跳 `Forbidden.vue`（403），路由不存在跳 `NotFound.vue`（404）。

> 权限点字符串与后端 `sql/01x_*_permissions.sql` 中的种子保持一致，改名需前后端同步。

---

## 四、接口调用约定

- 统一走 `src/api/` 封装，基础路径 `/api/v1`；
- 前台公开接口在 `siteApi.ts`，并配 `staticCache.ts` 做静态数据缓存（减少重复请求）；
- 需要导出的列表走后端 `/api/v1/excel/export/*`（需 `api_excel` 权限，viewer 角色默认无此权限）；
- 收藏能力：列表项内的收藏按钮需 `@click.stop`，防止冒泡触发详情跳转。

---

## 五、注意事项

1. **改完前端要 build** 才会被容器托管（见第一节）。
2. `auto-imports.d.ts` / `components.d.ts` 由插件自动生成，不要手改，也不要提交前的手动冲突合并。
3. ECharts 用 `vue-echarts`，图表组件统一放 `components/site/EChart.vue` 或直接使用。
4. 构建时 echarts 分块体积较大（约 289 kB，含 xlsx），属已知正常情况。
