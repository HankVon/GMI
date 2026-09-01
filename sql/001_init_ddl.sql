-- ============================================================
-- SSM 项目基石数据平台 — 业务库 DDL (MySQL 8.0)
-- 版本: v1.0.0
-- ============================================================

-- 1. 部门表
CREATE TABLE IF NOT EXISTS `sys_department` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '部门编码',
    `name`          VARCHAR(128)    NOT NULL                 COMMENT '部门名称',
    `parent_id`     BIGINT          DEFAULT NULL             COMMENT '父部门ID',
    `path`          VARCHAR(1024)   DEFAULT NULL             COMMENT '层级路径(如 /1/3/15)',
    `sort_order`    INT             DEFAULT 0                COMMENT '排序',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_parent_id` (`parent_id`),
    KEY `idx_path` (`path`(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='部门表';


-- 2. 系统用户表
CREATE TABLE IF NOT EXISTS `sys_user` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `username`      VARCHAR(64)     NOT NULL                 COMMENT '用户名',
    `password_hash` VARCHAR(256)    NOT NULL                 COMMENT '密码哈希(bcrypt)',
    `display_name`  VARCHAR(128)    NOT NULL                 COMMENT '显示名',
    `email`         VARCHAR(256)    DEFAULT NULL             COMMENT '邮箱',
    `phone`         VARCHAR(32)     DEFAULT NULL             COMMENT '手机号',
    `department_id` BIGINT          DEFAULT NULL             COMMENT '所属部门ID',
    `is_active`     TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '启用:0-禁用,1-启用',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_department_id` (`department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';


-- 3. 角色表
CREATE TABLE IF NOT EXISTS `sys_role` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '角色编码',
    `name`          VARCHAR(128)    NOT NULL                 COMMENT '角色名称',
    `description`   VARCHAR(512)    DEFAULT NULL             COMMENT '角色描述',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';


-- 4. 权限表
CREATE TABLE IF NOT EXISTS `sys_permission` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `code`          VARCHAR(128)    NOT NULL                 COMMENT '权限编码',
    `name`          VARCHAR(256)    NOT NULL                 COMMENT '权限名称',
    `resource_type` VARCHAR(32)     NOT NULL                 COMMENT '资源类型:menu/button/api',
    `resource_value` VARCHAR(512)   NOT NULL                 COMMENT '资源标识(路径/API pattern/按钮key)',
    `parent_id`     BIGINT          DEFAULT NULL             COMMENT '父权限ID(菜单树)',
    `sort_order`    INT             DEFAULT 0                COMMENT '排序',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_parent_id` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限表';


-- 5. 用户-角色关联表
CREATE TABLE IF NOT EXISTS `sys_user_role` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `user_id`       BIGINT          NOT NULL                 COMMENT '用户ID',
    `role_id`       BIGINT          NOT NULL                 COMMENT '角色ID',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_role` (`user_id`, `role_id`),
    KEY `idx_role_id` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户-角色关联表';


-- 6. 角色-权限关联表
CREATE TABLE IF NOT EXISTS `sys_role_permission` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `role_id`       BIGINT          NOT NULL                 COMMENT '角色ID',
    `permission_id` BIGINT          NOT NULL                 COMMENT '权限ID',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_role_permission` (`role_id`, `permission_id`),
    KEY `idx_permission_id` (`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色-权限关联表';


-- 7. 项目主表 (核心实体)
CREATE TABLE IF NOT EXISTS `project` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '项目编码(唯一)',
    `name`          VARCHAR(256)    NOT NULL                 COMMENT '项目名称',
    `description`   TEXT            DEFAULT NULL             COMMENT '项目描述',
    `status`        VARCHAR(32)     NOT NULL DEFAULT 'active' COMMENT '项目状态:active/suspended/completed/cancelled',
    `manager_id`    BIGINT          DEFAULT NULL             COMMENT '负责人ID(快照,指向person表)',
    `start_date`    DATE            DEFAULT NULL             COMMENT '启动日期',
    `end_date`      DATE            DEFAULT NULL             COMMENT '预计结束日期',
    `department_id` BIGINT          DEFAULT NULL             COMMENT '归属部门ID',
    `ext_attrs`     JSON            DEFAULT NULL             COMMENT '动态扩展字段(JSON)',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_name` (`name`(128)),
    KEY `idx_status` (`status`),
    KEY `idx_manager_id` (`manager_id`),
    KEY `idx_department_id` (`department_id`),
    KEY `idx_start_date` (`start_date`),
    KEY `idx_is_deleted` (`is_deleted`),
    -- ★ 虚拟列索引：按数据类型为高查询频率的动态字段预建虚拟列
    -- 元数据驱动引擎在注册新字段时通过 ALTER TABLE ADD VIRTUAL COLUMN 自动扩展
    -- 示例：合同金额(money类型)
    -- `v_ext_contract_amount` DECIMAL(18,2) GENERATED ALWAYS AS
    --   (JSON_UNQUOTE(JSON_EXTRACT(`ext_attrs`,'$.contract_amount'))) VIRTUAL,
    -- KEY `idx_ext_contract_amount` (`v_ext_contract_amount`)
    FULLTEXT KEY `ft_name_desc` (`name`, `description`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目主表';


-- 8. 人员主表 (独立维度)
CREATE TABLE IF NOT EXISTS `person` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '人员编码(唯一)',
    `name`          VARCHAR(128)    NOT NULL                 COMMENT '姓名',
    `email`         VARCHAR(256)    DEFAULT NULL             COMMENT '邮箱',
    `phone`         VARCHAR(32)     DEFAULT NULL             COMMENT '电话',
    `department_id` BIGINT          DEFAULT NULL             COMMENT '所属部门ID',
    `position`      VARCHAR(128)    DEFAULT NULL             COMMENT '职位',
    `status`        VARCHAR(32)     NOT NULL DEFAULT 'active' COMMENT '在职状态:active/resigned/suspended',
    `entry_date`    DATE            DEFAULT NULL             COMMENT '入职日期',
    `resign_date`   DATE            DEFAULT NULL             COMMENT '离职日期',
    `ext_attrs`     JSON            DEFAULT NULL             COMMENT '动态扩展字段(JSON)',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_name` (`name`),
    KEY `idx_department_id` (`department_id`),
    KEY `idx_status` (`status`),
    KEY `idx_is_deleted` (`is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='人员主表';


-- 9. 项目-人员关联表 (弱关联核心,保留历史轨迹)
CREATE TABLE IF NOT EXISTS `project_member` (
    `id`             BIGINT         NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `project_id`     BIGINT         NOT NULL                 COMMENT '项目ID',
    `person_id`      BIGINT         NOT NULL                 COMMENT '人员ID',
    `role`           VARCHAR(64)    NOT NULL                 COMMENT '项目角色:manager/member/observer等',
    `responsibility` VARCHAR(512)   DEFAULT NULL             COMMENT '职责描述',
    `stage`          VARCHAR(64)    NOT NULL DEFAULT ''      COMMENT '所属阶段(关联 option_set:project_progress_stage, 空=全程/不限)',
    `joined_at`      DATETIME       NOT NULL                 COMMENT '加入项目时间',
    `left_at`        DATETIME       DEFAULT NULL             COMMENT '退出项目时间(NULL=仍在参与)',
    `is_active`      TINYINT(1)     NOT NULL DEFAULT 1       COMMENT '是否在职:0-已退出,1-参与中',
    `ext_attrs`      JSON           DEFAULT NULL             COMMENT '动态扩展字段',
    `created_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`     TINYINT(1)     NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    KEY `idx_project_id` (`project_id`),
    KEY `idx_person_id` (`person_id`),
    KEY `idx_joined_at` (`joined_at`),
    KEY `idx_left_at` (`left_at`),
    KEY `idx_project_person_active` (`project_id`, `person_id`, `is_active`),
    -- ★ 时间点查询：某人某时刻参与了哪些项目
    KEY `idx_person_timeline` (`person_id`, `joined_at`, `left_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目-人员关联表(保留历史轨迹)';


-- 10. 字段元数据表 (动态字段引擎核心)
CREATE TABLE IF NOT EXISTS `field_metadata` (
    `id`               BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `entity_type`      VARCHAR(64)  NOT NULL                 COMMENT '所属实体:project/person/project_member',
    `field_key`        VARCHAR(128) NOT NULL                 COMMENT '字段标识(英文字段名,如contract_amount)',
    `display_name`     VARCHAR(256) NOT NULL                 COMMENT '显示名(如 合同金额)',
    `data_type`        VARCHAR(32)  NOT NULL                 COMMENT '数据类型:text/textarea/number/money/date/select/multi_select/switch/entity_ref',
    `option_set_code`  VARCHAR(64)  DEFAULT NULL             COMMENT '关联选项集编码(data_type=select/multi_select时)',
    `default_value`    VARCHAR(512) DEFAULT NULL             COMMENT '默认值',
    `validation_rules` JSON         DEFAULT NULL             COMMENT '校验规则JSON: {"required":true,"min":0,"max":999999999,"pattern":"^\\\\d+$"}',
    `sort_order`       INT          NOT NULL DEFAULT 0       COMMENT '排序(越小越靠前)',
    `group_name`       VARCHAR(128) DEFAULT NULL             COMMENT '分组名(表单/列表分组)',
    `is_required`      TINYINT(1)   NOT NULL DEFAULT 0       COMMENT '是否必填:0-否,1-是',
    `is_list_visible`  TINYINT(1)   NOT NULL DEFAULT 1       COMMENT '列表展示:0-隐藏,1-显示',
    `is_searchable`    TINYINT(1)   NOT NULL DEFAULT 0       COMMENT '可搜索:0-否,1-是',
    `is_filterable`    TINYINT(1)   NOT NULL DEFAULT 0       COMMENT '可筛选:0-否,1-是',
    `is_exportable`    TINYINT(1)   NOT NULL DEFAULT 1       COMMENT '可导出:0-否,1-是',
    `field_permissions` JSON        DEFAULT NULL             COMMENT '字段级权限: {"view":["admin","pm"],"edit":["admin"]}',
    `placeholder`      VARCHAR(512) DEFAULT NULL             COMMENT '输入提示',
    `help_text`        VARCHAR(512) DEFAULT NULL             COMMENT '帮助文本',
    `status`           VARCHAR(32)  NOT NULL DEFAULT 'enabled' COMMENT '状态:enabled/disabled',
    `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`       TINYINT(1)   NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_entity_field` (`entity_type`, `field_key`),
    KEY `idx_entity_type` (`entity_type`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字段元数据表';


-- 11. 字段元数据版本表 (变更审计)
CREATE TABLE IF NOT EXISTS `field_metadata_version` (
    `id`             BIGINT        NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `field_meta_id`  BIGINT        NOT NULL                 COMMENT '字段元数据ID',
    `version`        INT           NOT NULL                 COMMENT '版本号(从1递增)',
    `snapshot`       JSON          NOT NULL                 COMMENT '该版本完整快照',
    `change_type`    VARCHAR(32)   NOT NULL                 COMMENT '变更类型:create/update/delete',
    `changed_by`     BIGINT        DEFAULT NULL             COMMENT '变更人ID',
    `changed_at`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '变更时间',
    PRIMARY KEY (`id`),
    KEY `idx_field_meta_id` (`field_meta_id`),
    KEY `idx_changed_at` (`changed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字段元数据版本表';


-- 12. 选项集主表
CREATE TABLE IF NOT EXISTS `option_set` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `code`          VARCHAR(64)     NOT NULL                 COMMENT '选项集编码(唯一)',
    `name`          VARCHAR(256)    NOT NULL                 COMMENT '选项集名称',
    `description`   VARCHAR(512)    DEFAULT NULL             COMMENT '描述',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='选项集主表';


-- 13. 选项项表
CREATE TABLE IF NOT EXISTS `option_item` (
    `id`             BIGINT         NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `option_set_id`  BIGINT         NOT NULL                 COMMENT '选项集ID',
    `value`          VARCHAR(128)   NOT NULL                 COMMENT '选项值',
    `label`          VARCHAR(256)   NOT NULL                 COMMENT '显示标签',
    `sort_order`     INT            NOT NULL DEFAULT 0       COMMENT '排序',
    `color`          VARCHAR(32)    DEFAULT NULL             COMMENT '颜色标记(如 #FF0000)',
    `created_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`     TINYINT(1)     NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_set_value` (`option_set_id`, `value`),
    KEY `idx_option_set_id` (`option_set_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='选项项表';


-- 14. 操作审计日志表
CREATE TABLE IF NOT EXISTS `audit_log` (
    `id`             BIGINT        NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `user_id`        BIGINT        DEFAULT NULL             COMMENT '操作用户ID',
    `username`       VARCHAR(64)   DEFAULT NULL             COMMENT '操作用户名(快照)',
    `action`         VARCHAR(64)   NOT NULL                 COMMENT '操作类型:create/update/delete/export/import/login/logout',
    `resource_type`  VARCHAR(64)   NOT NULL                 COMMENT '资源类型:project/person/field_metadata等',
    `resource_id`    BIGINT        DEFAULT NULL             COMMENT '资源ID',
    `resource_name`  VARCHAR(512)  DEFAULT NULL             COMMENT '资源名称(快照)',
    `detail`         JSON          DEFAULT NULL             COMMENT '操作详情(JSON,含请求参数/变更前后对比)',
    `ip_address`     VARCHAR(64)   DEFAULT NULL             COMMENT '客户端IP',
    `user_agent`     VARCHAR(512)  DEFAULT NULL             COMMENT 'User-Agent',
    `created_at`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_resource` (`resource_type`, `resource_id`),
    KEY `idx_action` (`action`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作审计日志表';


-- 15. 字段值变更历史表
CREATE TABLE IF NOT EXISTS `field_change_history` (
    `id`              BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `entity_type`     VARCHAR(64)  NOT NULL                 COMMENT '实体类型:project/person/project_member',
    `entity_id`       BIGINT       NOT NULL                 COMMENT '实体实例ID',
    `field_key`       VARCHAR(128) NOT NULL                 COMMENT '字段标识(含内置字段和动态字段)',
    `field_label`     VARCHAR(256) DEFAULT NULL             COMMENT '字段显示名(快照)',
    `old_value`       TEXT         DEFAULT NULL             COMMENT '旧值',
    `new_value`       TEXT         DEFAULT NULL             COMMENT '新值',
    `changed_by`      BIGINT       DEFAULT NULL             COMMENT '变更人ID',
    `changed_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '变更时间',
    PRIMARY KEY (`id`),
    KEY `idx_entity` (`entity_type`, `entity_id`),
    KEY `idx_field_key` (`field_key`),
    KEY `idx_changed_at` (`changed_at`),
    KEY `idx_changed_by` (`changed_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字段值变更历史表';


-- ============================================================
-- 初始种子数据
-- ============================================================

-- 项目进展表（手动维护的进展时间线）
CREATE TABLE IF NOT EXISTS `project_progress` (
    `id`             BIGINT         NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `project_id`     BIGINT         NOT NULL                 COMMENT '项目ID',
    `title`          VARCHAR(256)   NOT NULL                 COMMENT '进展标题',
    `content`        TEXT           DEFAULT NULL             COMMENT '进展详情',
    `progress_date`  DATETIME       NOT NULL                 COMMENT '进展日期',
    `sort_order`     INT            NOT NULL DEFAULT 0       COMMENT '排序权重(越小越靠前)',
    `created_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`     TINYINT(1)     NOT NULL DEFAULT 0       COMMENT '软删除:0-否,1-是',
    PRIMARY KEY (`id`),
    KEY `idx_project_id` (`project_id`),
    KEY `idx_progress_date` (`progress_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目进展记录表';


-- 默认部门
INSERT INTO `sys_department` (`code`, `name`, `parent_id`, `path`, `sort_order`) VALUES
('root', '总公司', NULL, '/1', 0);

-- 默认管理员
-- 密码: admin123 (bcrypt hash, 上线前替换为实际hash)
INSERT INTO `sys_user` (`username`, `password_hash`, `display_name`, `email`, `department_id`) VALUES
('admin', '$2b$12$LJ3m4ys3Lk0TSwHCpNqrTeVmB8OJfDnSaP6AKVFqNEcHMKJ5RzP2e', '系统管理员', 'admin@ssm.local', 1);

-- 默认角色
INSERT INTO `sys_role` (`code`, `name`, `description`) VALUES
('admin',      '超级管理员', '拥有所有权限'),
('project_mgr', '项目经理',   '管理项目及成员'),
('member',      '项目成员',   '查看和参与项目'),
('viewer',      '只读用户',   '仅查看权限');

-- 默认权限
INSERT INTO `sys_permission` (`code`, `name`, `resource_type`, `resource_value`, `parent_id`, `sort_order`) VALUES
-- 菜单权限
('menu_admin',       '管理后台',     'menu',   '/admin',          NULL, 1),
('menu_workspace',   '业务工作台',   'menu',   '/workspace',      NULL, 2),
('menu_dashboard',   '数据看板',     'menu',   '/dashboard',       NULL, 3),
-- 管理后台子菜单
('menu_project_mgt', '项目管理',     'menu',   '/admin/projects', 1, 1),
('menu_person_mgt',  '人员管理',     'menu',   '/admin/persons',  1, 2),
('menu_field_mgt',   '字段管理',     'menu',   '/admin/fields',   1, 3),
('menu_option_mgt',  '选项集管理',   'menu',   '/admin/options',  1, 4),
('menu_rbac',        '角色权限',     'menu',   '/admin/rbac',     1, 5),
('menu_audit',       '审计日志',     'menu',   '/admin/audit',    1, 6),
-- API权限
('api_project_crud', '项目CRUD',     'api',    '/api/v1/projects/*',     NULL, 10),
('api_person_crud',  '人员CRUD',     'api',    '/api/v1/persons/*',      NULL, 11),
('api_field_crud',   '字段管理CRUD', 'api',    '/api/v1/field-metadata/*', NULL, 12),
('api_option_crud',  '选项集CRUD',   'api',    '/api/v1/option-sets/*',   NULL, 13),
('api_rbac',         '角色权限管理', 'api',    '/api/v1/rbac/*',           NULL, 14),
('api_excel',        'Excel导入导出','api',    '/api/v1/excel/*',          NULL, 15),
('api_audit',        '审计日志查看', 'api',    '/api/v1/audit/*',          NULL, 16),
('api_notification', '通知与反馈处理', 'api',    '/api/v1/notifications/*', NULL, 17);

-- 管理员拥有所有角色
INSERT INTO `sys_user_role` (`user_id`, `role_id`) VALUES (1, 1);

-- 管理员角色拥有所有权限
INSERT INTO `sys_role_permission` (`role_id`, `permission_id`)
SELECT 1, id FROM `sys_permission`;

-- 默认选项集
INSERT INTO `option_set` (`code`, `name`, `description`) VALUES
('project_status', '项目状态', '项目生命周期状态'),
('person_status',  '人员状态', '人员在职状态'),
('member_role',    '项目角色', '项目成员角色');

INSERT INTO `option_item` (`option_set_id`, `value`, `label`, `sort_order`, `color`) VALUES
-- 项目状态选项
(1, 'active',    '进行中', 1, '#1890ff'),
(1, 'suspended', '挂起',   2, '#faad14'),
(1, 'completed', '已完成', 3, '#52c41a'),
(1, 'cancelled', '已取消', 4, '#ff4d4f'),
-- 人员状态选项
(2, 'active',    '在职', 1, '#52c41a'),
(2, 'resigned',  '离职', 2, '#d9d9d9'),
(2, 'suspended', '停薪留职', 3, '#faad14'),
-- 项目角色选项
(3, 'manager',   '项目经理',  1, '#1890ff'),
(3, 'member',    '项目成员',  2, '#52c41a'),
(3, 'observer',  '观察者',    3, '#d9d9d9'),
(3, 'sponsor',   '项目发起人', 4, '#722ed1');
