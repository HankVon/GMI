-- ============================================================
-- SSM 人脉库 (business_network) — 可扩展数据模型
--
-- 设计原则:
--   1. 关系不重复存, 只存「跨源聚合的关联视图」——数据源头仍是
--      project_company/project_member/bid_notice/entity_relation
--   2. person_skill 人员专长标签(可从项目分类/岗位推导, 也支持手工标注)
--   3. network_edge 人脉边(两实体间的加权关系), 供「人脉图谱」快速查询
--      由各源(项目参与/中标/合作)聚合生成, 带 source 可溯源
--   4. tender_match 招标信息 × 人脉实体 的匹配记录(项目类型/专长)
-- ============================================================

-- 人员专长标签(可扩展: 手工标注 + 从项目分类/参与项目推导)
CREATE TABLE IF NOT EXISTS `person_skill` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `person_id`     BIGINT          NOT NULL                 COMMENT '人员id',
    `skill`         VARCHAR(128)    NOT NULL                 COMMENT '专长/技能标签',
    `source`        VARCHAR(32)     DEFAULT 'manual'         COMMENT '来源: manual/project_infer/category',
    `confidence`    DECIMAL(4,2)    NOT NULL DEFAULT 0.8     COMMENT '置信度',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_person_skill` (`person_id`, `skill`),
    KEY `idx_skill` (`skill`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='人员专长标签';

-- 人脉边(两实体加权关系, 聚合视图, 可溯源到各源)
CREATE TABLE IF NOT EXISTS `network_edge` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `src_type`      VARCHAR(32)     NOT NULL                 COMMENT '源类型 person/company/project',
    `src_id`        BIGINT          NOT NULL                 COMMENT '源实体id',
    `src_name`      VARCHAR(512)    DEFAULT NULL,
    `tgt_type`      VARCHAR(32)     NOT NULL                 COMMENT '目标类型',
    `tgt_id`        BIGINT          NOT NULL,
    `tgt_name`      VARCHAR(512)    DEFAULT NULL,
    `rel_type`      VARCHAR(64)     NOT NULL                 COMMENT '关系类型 COLLABORATED_WITH/WORKS_AT/PARTICIPATES_IN/...',
    `rel_zh`        VARCHAR(64)     DEFAULT NULL,
    `weight`        DECIMAL(6,2)    NOT NULL DEFAULT 1.0     COMMENT '权重(合作次数/强度)',
    `source`        VARCHAR(64)     DEFAULT NULL             COMMENT '来源 project_member/bid_notice/entity_relation/manual',
    `evidence`      VARCHAR(1024)   DEFAULT NULL             COMMENT '证据(项目名/公告标题等)',
    `last_seen`     DATETIME        DEFAULT NULL             COMMENT '最近一次出现(近两年过滤用)',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_edge` (`src_type`, `src_id`, `tgt_type`, `tgt_id`, `rel_type`),
    KEY `idx_edge_src` (`src_type`, `src_id`),
    KEY `idx_edge_tgt` (`tgt_type`, `tgt_id`),
    KEY `idx_edge_rel` (`rel_type`),
    KEY `idx_edge_lastseen` (`last_seen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='人脉边(聚合关系视图)';

-- 招标信息 × 人脉实体 匹配记录(提前获取招标信息的核心输出)
CREATE TABLE IF NOT EXISTS `tender_match` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
    `clue_id`       BIGINT          DEFAULT NULL             COMMENT '招标/意向线索 web_clue.id',
    `intent_id`     BIGINT          DEFAULT NULL             COMMENT '意向通知 intent_notice.id(预留)',
    `title`         VARCHAR(512)    NOT NULL                 COMMENT '招标/意向标题',
    `entity_type`   VARCHAR(32)     NOT NULL                 COMMENT '匹配到的人脉实体类型 person/company',
    `entity_id`     BIGINT          NOT NULL,
    `entity_name`   VARCHAR(512)    DEFAULT NULL,
    `match_type`    VARCHAR(32)     DEFAULT 'skill'          COMMENT '匹配方式: skill专长/category项目类型/region区域/keyword',
    `match_reason`  VARCHAR(512)    DEFAULT NULL             COMMENT '匹配理由',
    `score`         DECIMAL(4,2)    NOT NULL DEFAULT 0       COMMENT '匹配得分 0-1',
    `region`        VARCHAR(128)    DEFAULT NULL,
    `amount`        VARCHAR(128)    DEFAULT NULL             COMMENT '预算/金额(原文)',
    `status`        VARCHAR(16)     DEFAULT 'new'            COMMENT '状态: new/contacted/followed/ignored',
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted`    TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_tm_clue` (`clue_id`),
    KEY `idx_tm_entity` (`entity_type`, `entity_id`),
    KEY `idx_tm_status` (`status`),
    KEY `idx_tm_score` (`score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='招标信息×人脉实体匹配记录';
