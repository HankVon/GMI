# SSM 项目基石数据平台 — 架构设计文档

## 1. 总体架构图

```mermaid
graph TB
    subgraph 前端层
        A1[管理后台<br/>Vue3+ElementPlus]
        A2[业务工作台<br/>Vue3+ElementPlus]
        A3[数据看板<br/>Vue3+ECharts]
    end

    subgraph API网关层
        B1[FastAPI /api/v1/*]
        B2[认证中间件 JWT]
        B3[审计中间件]
        B4[RBAC + 字段级权限]
    end

    subgraph 服务层
        C1[动态字段引擎<br/>Pydantic运行时建模]
        C2[动态查询服务<br/>JSON虚拟列+INDEX]
        C3[缓存服务<br/>Redis/失效策略]
        C4[Excel导入导出<br/>元数据驱动映射]
        C5[审计服务]
    end

    subgraph 数据层
        D1[(MySQL 8.0<br/>业务库)]
        D2[(Redis<br/>字段元数据缓存)]
    end

    A1 & A2 & A3 --> B1
    B1 --> B2 --> B3 --> B4
    B4 --> C1 & C2 & C3 & C4 & C5
    C1 & C2 --> D1
    C3 --> D2
    C1 -.->|失效通知| C3
    C4 -.->|字段映射读取| C3
```

## 2. 领域模型 ER 图

```mermaid
erDiagram
    PROJECT ||--o{ PROJECT_MEMBER : has
    PROJECT ||--o{ FIELD_CHANGE_HISTORY : tracked_by
    PROJECT {
        bigint id PK "主键"
        varchar code UK "项目编码"
        varchar name "项目名称"
        varchar description "项目描述"
        varchar status "项目状态"
        bigint manager_id FK "负责人快照"
        json ext_attrs "动态字段JSON"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    PERSON ||--o{ PROJECT_MEMBER : participates
    PERSON {
        bigint id PK
        varchar code UK "人员编码"
        varchar name "姓名"
        varchar email "邮箱"
        varchar phone "电话"
        bigint department_id FK "部门"
        varchar status "在职状态"
        json ext_attrs "动态字段JSON"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    PROJECT_MEMBER {
        bigint id PK
        bigint project_id FK
        bigint person_id FK
        varchar role "角色"
        varchar responsibility "职责"
        datetime joined_at "加入时间"
        datetime left_at "退出时间"
        tinyint is_active "是否在职"
        json ext_attrs "动态字段JSON"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    FIELD_METADATA ||--o{ FIELD_METADATA_VERSION : versions
    FIELD_METADATA {
        bigint id PK
        varchar entity_type "所属实体"
        varchar field_key UK "字段标识"
        varchar display_name "显示名"
        varchar data_type "数据类型"
        varchar option_set_code FK "选项集编码"
        json validation_rules "校验规则"
        int sort_order "排序"
        varchar group_name "分组"
        tinyint is_required "是否必填"
        tinyint is_list_visible "列表展示"
        tinyint is_searchable "可搜索"
        tinyint is_filterable "可筛选"
        tinyint is_exportable "可导出"
        json field_permissions "字段级权限"
        varchar status "启用/禁用"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    FIELD_METADATA_VERSION {
        bigint id PK
        bigint field_meta_id FK
        int version "版本号"
        json snapshot "快照"
        varchar change_type "变更类型"
        bigint changed_by FK
        datetime changed_at
    }

    OPTION_SET ||--o{ OPTION_ITEM : contains
    OPTION_SET {
        bigint id PK
        varchar code UK "选项集编码"
        varchar name "名称"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    OPTION_ITEM {
        bigint id PK
        bigint option_set_id FK
        varchar value "选项值"
        varchar label "显示标签"
        int sort_order "排序"
        varchar color "颜色标记"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    SYS_USER ||--o{ SYS_USER_ROLE : has
    SYS_USER ||--o{ AUDIT_LOG : generates
    SYS_USER ||--o{ FIELD_CHANGE_HISTORY : changes
    SYS_USER {
        bigint id PK
        varchar username UK
        varchar password_hash
        varchar display_name
        varchar email
        bigint department_id FK
        tinyint is_active
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    SYS_ROLE ||--o{ SYS_USER_ROLE : assigned_to
    SYS_ROLE ||--o{ SYS_ROLE_PERMISSION : grants
    SYS_ROLE {
        bigint id PK
        varchar code UK "角色编码"
        varchar name "角色名"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    SYS_PERMISSION ||--o{ SYS_ROLE_PERMISSION : granted_via
    SYS_PERMISSION {
        bigint id PK
        varchar code UK "权限编码"
        varchar name "权限名"
        varchar resource_type "menu/button/api"
        varchar resource_value "资源标识"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    SYS_USER_ROLE {
        bigint id PK
        bigint user_id FK
        bigint role_id FK
        datetime created_at
    }

    SYS_ROLE_PERMISSION {
        bigint id PK
        bigint role_id FK
        bigint permission_id FK
        datetime created_at
    }

    SYS_DEPARTMENT {
        bigint id PK
        varchar code UK
        varchar name
        bigint parent_id FK "父部门"
        varchar path "层级路径"
        datetime created_at
        datetime updated_at
        tinyint is_deleted
    }

    AUDIT_LOG {
        bigint id PK
        bigint user_id FK
        varchar action "操作类型"
        varchar resource_type "资源类型"
        bigint resource_id "资源ID"
        text detail "操作详情JSON"
        varchar ip_address
        datetime created_at
    }

    FIELD_CHANGE_HISTORY {
        bigint id PK
        bigint entity_type_id "实体实例ID"
        varchar entity_type "实体类型"
        varchar field_key "字段标识"
        text old_value "旧值"
        text new_value "新值"
        bigint changed_by FK
        datetime changed_at
    }
```

## 7. 端到端时序图：管理员新增字段

```mermaid
sequenceDiagram
    actor Admin as 管理员
    participant FE as 前端(字段管理)
    participant API as FastAPI /api/v1
    participant Engine as 动态字段引擎
    participant DB as MySQL
    participant Redis as Redis

    Admin->>FE: 新增字段"合同金额"<br/>entity=project, type=money
    FE->>API: POST /api/v1/field-metadata
    API->>API: RBAC鉴权(admin角色)
    API->>Engine: validate_and_create(meta)
    Engine->>DB: INSERT field_metadata
    Engine->>DB: INSERT field_metadata_version(v1)
    Engine->>Redis: DEL cache:field_meta:project:*
    Engine-->>API: created field
    API-->>FE: 201 + field_meta

    Note over Redis: 缓存已失效，下次读取走DB

    FE->>API: GET /api/v1/projects?list_columns=all
    API->>Redis: GET cache:field_meta:project:list
    Redis-->>API: MISS
    API->>DB: SELECT * FROM field_metadata<br/>WHERE entity_type='project' AND is_list_visible=1
    API->>Redis: SET cache:field_meta:project:list (TTL 3600)
    API-->>FE: 列定义含"合同金额"

    FE->>FE: DynamicTable 渲染新列
    Admin->>FE: 打开项目详情，填写合同金额=5000000
    FE->>API: PUT /api/v1/projects/1<br/>{"ext_attrs":{"contract_amount":5000000}}
    API->>Engine: validate(project, {"contract_amount":5000000})
    Engine->>Redis: GET cache:field_meta:project:all
    Redis-->>Engine: field_meta列表
    Engine->>Engine: Pydantic动态模型校验<br/>type=money, min=0, required=false
    Engine-->>API: 校验通过
    API->>DB: UPDATE project SET ext_attrs=JSON_SET(ext_attrs,'$.contract_amount',5000000)
    API->>DB: INSERT field_change_history(old=null, new=5000000)
    API-->>FE: 200 OK

    Admin->>FE: 搜索"合同金额>100万"
    FE->>API: GET /api/v1/projects?search=contract_amount>1000000
    API->>Engine: build_query(entity='project', filters=[...])
    Engine->>DB: SELECT * FROM project<br/>WHERE JSON_EXTRACT(ext_attrs,'$.contract_amount')>1000000<br/>-- 使用虚拟列索引 idx_ext_contract_amount
    DB-->>API: 匹配结果
    API-->>FE: 搜索结果

    Admin->>FE: 导出Excel
    FE->>API: POST /api/v1/excel/export/projects
    API->>Redis: GET cache:field_meta:project:exportable
    API->>Engine: 动态组装导出列
    API-->>FE: .xlsx 含"合同金额"列
```

## 8. 一期开发任务拆解

| 编号 | 模块 | 任务 | 预计人天 | 依赖 |
|------|------|------|----------|------|
| T1 | 基础设施 | Docker Compose(MySQL+Redis+FastAPI)、Alembic初始化、DDL执行 | 1 | - |
| T2 | 基础模型 | BaseModel(软删除+时间戳)、Project/Person/ProjectMember ORM | 1.5 | T1 |
| T3 | RBAC | User/Role/Permission表+CRUD+JWT认证中间件 | 2 | T1 |
| T4 | 字段元数据 | FieldMetadata/OptionSet CRUD API + 缓存服务 | 2.5 | T1 |
| T5 | 动态字段引擎 | Pydantic运行时建模、ext_attrs校验、动态查询(虚拟列+索引) | 3 | T4 |
| T6 | 项目管理CRUD | 动态实体CRUD(含校验流程)、软删除 | 2 | T2,T5 |
| T7 | 人员管理CRUD | 人员主数据CRUD、人员主页API | 1.5 | T2,T5 |
| T8 | 项目成员管理 | 成员增删改、时间轨迹查询、职责变更历史 | 2 | T2,T6,T7 |
| T9 | 审计日志 | 操作审计中间件、字段变更历史记录 | 1.5 | T3 |
| T10 | Excel导入导出 | 元数据驱动字段映射、批量导入校验、导出列动态组装 | 2 | T5,T6,T7 |
| T11 | 字段级权限 | FieldPermissions中间件、敏感字段脱敏/隐藏 | 1.5 | T3,T4 |
| T12 | 前端-管理后台 | 字段管理/选项集/角色权限页面 | 3 | T4,T3 |
| T13 | 前端-业务工作台 | 动态表格+项目360°详情+人员主页 | 4 | T6,T7,T8,T10 |
| T14 | 前端-动态组件 | DynamicForm/DynamicTable 通用组件 | 3 | T5,T12 |

**一期总工期：约 30 人天（前后端并行开发可压缩到 2~3 周）**
