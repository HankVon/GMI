<!--
  项目360°详情页 — 参考 RCC 项目详情风格
  布局：头部信息卡 + 项目进展时间线 + 项目介绍字段网格 + 右侧成员
-->
<template>
  <div class="project-detail">
    <el-page-header @back="$router.back()" title="返回列表">
      <template #content>
          <span>{{ project.name || "加载中..." }}</span>
        </template>
      </el-page-header>

      <!-- 顶部主信息卡(白底 + 蓝色顶边, 项目名 + 状态 + 编辑) -->
      <div class="fgbs-header">
        <div class="fgbs-head-main">
          <h2 class="fgbs-title">
            {{ project.name || "-" }}
          </h2>
          <el-tag :type="statusTagType(project.status)" effect="dark" size="small">
            {{ statusLabel(project.status) }}
          </el-tag>
          <div class="fgbs-head-spacer" />
          <!-- <el-button v-if="!editing" type="primary" size="small" class="fgbs-print" @click="startEdit">
            <el-icon><Edit /></el-icon><span>编辑项目</span>
          </el-button> -->
        </div>

        <!-- 三张信息小卡: 项目编号 / 负责人 / 起止日期 -->
        <div class="fgbs-info-cards">
          <div class="fgbs-info-card">
            <div class="fgbs-info-icon"><el-icon><Document /></el-icon></div>
            <div class="fgbs-info-body">
              <div class="fgbs-info-label">项目编号</div>
              <div class="fgbs-info-value">{{ project.code || "-" }}</div>
            </div>
          </div>
          <div class="fgbs-info-card">
            <div class="fgbs-info-icon"><el-icon><User /></el-icon></div>
            <div class="fgbs-info-body">
              <div class="fgbs-info-label">项目联系人</div>
              <div class="fgbs-info-value fgbs-managers">
                <template v-if="managers.length">
                  <el-tag
                    v-for="m in managers" :key="m.person_id" size="small" type="danger"
                    effect="light" class="fgbs-manager-tag"
                  >{{ m.person_name }}</el-tag>
                </template>
                <span v-else>{{ manager.name || project.ext_attrs?.contact || "-" }}</span>
              </div>
            </div>
          </div>
          <div class="fgbs-info-card">
            <div class="fgbs-info-icon"><el-icon><Calendar /></el-icon></div>
            <div class="fgbs-info-body">
              <div class="fgbs-info-label">启动 / 预计结束</div>
              <div class="fgbs-info-value">{{ formatDate(project.start_date) }} → {{ formatDate(project.end_date) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- AI分析能力横幅 -->
      <div class="ai-banner">
        <div class="ai-banner-left">
          <span class="ai-banner-label"><el-icon><MagicStick /></el-icon><b>AI分析:</b></span>
          <span v-for="(c, i) in AI_CHIPS" :key="i" class="ai-chip" @click="openAiChat(c)">{{ c }}</span>
        </div>
        <el-link type="primary" :underline="false" class="ai-more" @click="openAiChat()">
          更多分析 <el-icon><ArrowRight /></el-icon>
        </el-link>
      </div>

      <!-- 统计卡片 -->
      <div class="fgbs-stats">
        <div class="fgbs-stat">
          <div class="stat-num">{{ members.length }}</div>
          <div class="stat-label">参与人员</div>
        </div>
        <div class="fgbs-stat">
          <div class="stat-num">{{ allCompanyCount }}</div>
          <div class="stat-label">参与单位</div>
        </div>
        <div class="fgbs-stat">
          <div class="stat-num">{{ progressList.length }}</div>
          <div class="stat-label">进展记录</div>
        </div>
        <div class="fgbs-stat">
          <div class="stat-num">{{ activeMemberCount }}</div>
          <div class="stat-label">在途成员</div>
        </div>
      </div>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 左侧：进展 + 介绍 + 变更历史 -->
      <el-col :span="16">
        <!-- 项目进展 -->
        <el-card class="section-card" shadow="never">
          <template #header>
            <div class="section-header">
              <span class="section-title">项目进展</span>
              <el-button type="primary" size="small" @click="openProgressDialog(null)">
                添加进展
              </el-button>
            </div>
          </template>
          <el-timeline v-if="progressList.length > 0">
            <el-timeline-item
              v-for="(node, idx) in progressList"
              :key="node.id"
              :timestamp="formatDateTime(node.progress_date)"
              :type="idx === 0 ? 'primary' : ''"
              placement="top"
            >
              <div class="progress-node">
                <div class="progress-title-row">
                  <el-tag :type="stageTagType(node.title)" effect="light" round size="small">
                    {{ node.title }}
                  </el-tag>
                  <div class="progress-ops">
                    <el-button link type="primary" size="small" @click="openProgressDialog(node)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="deleteProgress(node)">删除</el-button>
                  </div>
                </div>
                <div v-if="node.content" class="progress-desc">{{ node.content }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无进展记录，点击右上角添加" :image-size="60" />
        </el-card>

        <!-- 项目介绍 -->
        <el-card class="section-card" shadow="never">
          <template #header>
            <div class="section-header">
              <span class="section-title">项目介绍</span>
              <div v-if="!editing" class="header-actions">
                <el-button type="primary" size="small" @click="startEdit">编辑</el-button>
              </div>
              <div v-else class="header-actions">
                <el-button size="small" @click="cancelEdit">取消</el-button>
                <el-button type="primary" size="small" :loading="saving" @click="saveEdit">
                  保存
                </el-button>
              </div>
            </div>
          </template>

          <!-- 查看模式：字段网格 -->
          <div v-if="!editing" class="info-grid">
            <div
              v-for="item in displayItems"
              :key="item.label"
              class="info-cell"
              :class="{ 'info-cell-wide': item.wide }"
            >
              <div class="info-label">{{ item.label }}</div>
              <div class="info-value">
                <!-- 多选: 每个选项一个带色标签 -->
                <template v-if="item.isMultiTag">
                  <el-tag
                    v-for="(lb, li) in item.multiLabels"
                    :key="lb"
                    :color="item.multiColors?.[li] || ''"
                    :type="item.multiColors?.[li] ? '' : 'info'"
                    effect="dark"
                    size="small"
                    style="margin-right: 4px"
                  >
                    {{ lb }}
                  </el-tag>
                </template>
                <!-- 单选: 选项集配置颜色优先, 无颜色时回退 tagType -->
                <el-tag
                  v-else-if="item.isTag"
                  :color="item.tagColor || ''"
                  :type="item.tagColor ? '' : item.tagType"
                  effect="dark"
                  size="small"
                >
                  {{ item.value }}
                </el-tag>
                <template v-else-if="item.isMoney">
                  ¥{{ formatNumber(item.value) }}
                </template>
                <template v-else-if="item.isSwitch">
                  <el-tag :type="item.value ? 'success' : 'info'" size="small">
                    {{ item.value ? "是" : "否" }}
                  </el-tag>
                </template>
                <template v-else>{{ item.value ?? "-" }}</template>
              </div>
            </div>
          </div>

          <!-- 项目概况：小节标题 + 分段正文 + 表格识别 -->
          <div v-if="!editing && project.description" class="overview-section">
            <div class="overview-title">
              <el-icon class="overview-title-icon"><Document /></el-icon>项目概况
            </div>
            <div class="overview-content">
              <template v-for="(p, i) in overviewBlocks" :key="i">
                <div v-if="p.kind === 'title'" class="overview-para-title">
                  <span class="ov-title-mark"></span>{{ p.text }}
                </div>
                <table v-else-if="p.kind === 'table' && p.rows?.length" class="ov-table">
                  <thead>
                    <tr><th v-for="(h, hi) in p.headers" :key="hi">{{ h }}</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(r, ri) in p.rows" :key="ri">
                      <td v-for="(c, ci) in r" :key="ci">{{ c }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-else class="overview-para">{{ p.text }}</p>
              </template>
            </div>
          </div>

          <!-- 编辑模式 -->
          <el-form ref="editFormRef" v-else :model="editForm" label-width="120px" class="edit-form" :rules="builtinRules">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="项目编码">
                  <el-input v-model="editForm.code" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="项目名称" prop="name">
                  <el-input v-model="editForm.name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="状态">
                  <el-select v-model="editForm.status" style="width: 100%">
                    <el-option label="进行中" value="active" />
                    <el-option label="挂起" value="suspended" />
                    <el-option label="已完成" value="completed" />
                    <el-option label="已取消" value="cancelled" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="联系人(可多选)">
                  <el-select
                    v-model="editForm.manager_ids"
                    multiple filterable clearable
                    placeholder="从参与成员中选择一个或多个联系人"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="p in managerOptions"
                      :key="p.id"
                      :label="`${p.name} (${p.company_name || '-'})`"
                      :value="p.id"
                    />
                    <template #empty>
                      <div style="padding: 8px; color: #909399; font-size: 12px">
                        {{ members.length ? "暂无匹配的参与成员" : "项目暂无参与成员，请先添加成员" }}
                      </div>
                    </template>
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="启动日期">
                  <el-date-picker
                    v-model="editForm.start_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="预计结束">
                  <el-date-picker
                    v-model="editForm.end_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="省份">
                  <el-input v-model="editProvince" placeholder="如：四川省" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="城市">
                  <el-input v-model="editCity" placeholder="如：成都市" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="区县">
                  <el-input v-model="editCounty" placeholder="如：双流区" clearable />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="描述">
              <el-input v-model="editForm.description" type="textarea" :rows="3" />
            </el-form-item>
            <DynamicForm
              ref="dynamicFormRef"
              entity-type="project"
              v-model="editFormDynamic"
              mode="edit"
            />
          </el-form>
        </el-card>

      </el-col>

      <!-- 右侧：参与公司（由参与成员反推）+ 成员 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="section-header">
              <span class="section-title">参与公司与成员</span>
              <el-button type="primary" size="small" @click="showAddMember = true">
                添加成员
              </el-button>
            </div>
          </template>

          <!-- 项目参与单位(直接关联, 含法人单位主体, 标注角色) -->
          <template v-if="projectCompanies.length > 0">
            <div class="project-companies-block">
              <div class="project-companies-title">
                项目参与单位
                <el-tag size="small" type="info">{{ projectCompanies.length }}</el-tag>
              </div>
              <div
                v-for="c in projectCompanies"
                :key="c.company_id"
                class="project-company-row"
              >
                <el-icon class="company-group-icon"><OfficeBuilding /></el-icon>
                <span
                  class="company-link project-company-name"
                  @click="goCompany(c.company_id)"
                >{{ c.company_name }}</span>
                <el-tag
                  v-if="c.role"
                  size="small"
                  :type="c.role === 'constructor' ? 'warning' : 'info'"
                  effect="light"
                >{{ companyRoleLabel(c.role) }}</el-tag>
              </div>
            </div>
            <el-divider style="margin: 12px 0" />
          </template>

          <!-- 参与公司与成员: 以「公司→人员」为主体, 阶段是人员的一个属性 tag -->
          <template v-if="derivedCompanies.length > 0">
            <div
              v-for="c in derivedCompanies"
              :key="c.company_id ?? 'none'"
              class="company-group-card"
            >
              <div class="company-group-head">
                <el-icon class="company-group-icon"><OfficeBuilding /></el-icon>
                <span
                  v-if="c.company_id"
                  class="company-link company-group-name"
                  @click="goCompany(c.company_id)"
                >{{ c.company_name }}</span>
                <span v-else class="company-group-name" style="color:#909399">未归属单位</span>
                <span class="company-group-count">{{ c.members.length }} 人</span>
              </div>
              <div class="company-group-body">
                <div
                  v-for="m in c.members"
                  :key="m.id"
                  class="member-card"
                >
                  <el-avatar :size="32" class="member-avatar-pic" style="cursor: pointer; flex-shrink: 0" @click="goPerson(m.person_id)">
                    {{ m.person_name?.charAt(0) }}
                  </el-avatar>
                  <div class="member-card-info">
                    <div class="member-card-name-row">
                      <strong class="person-link" @click="goPerson(m.person_id)">{{ m.person_name }}</strong>
                      <el-tag
                        v-if="m.role !== 'member'"
                        size="small" :type="m.role === 'manager' ? 'danger' : 'info'"
                        effect="light"
                      >{{ roleLabel(m.role) }}</el-tag>
                      <!-- 阶段: 人员属性 -->
                      <el-tag v-if="m.stage" size="small" type="primary" effect="plain">{{ m.stage }}</el-tag>
                      <el-tag v-else size="small" type="info" effect="plain">全程参与</el-tag>
                    </div>
                    <div class="member-card-sub">
                      <span v-if="m.person_position || m.person_department" class="member-position">
                        {{ m.person_position || m.person_department }}
                      </span>
                      <span class="member-card-date">
                        {{ formatDate(m.joined_at) }}
                        <template v-if="m.left_at"> → {{ formatDate(m.left_at) }}</template>
                      </span>
                    </div>
                  </div>
                  <div class="member-actions">
                    <el-link type="primary" :underline="false" class="member-relation-link" @click.stop="openEditMember(m)">编辑</el-link>
                    <el-link type="primary" :underline="false" class="member-relation-link" @click.stop="goNetwork(m.person_id)">查看人脉</el-link>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <el-empty v-else-if="exitedMembers.length === 0" description="暂无参与成员" :image-size="60" />

          <!-- 已退出人员（可折叠卡片） -->
          <div v-if="exitedMembers.length" class="exited-card">
            <div class="exited-card-header" @click="showExited = !showExited">
              <span class="exited-card-title">
                已退出人员
                <el-tag size="small" type="info">{{ exitedMembers.length }}</el-tag>
              </span>
              <el-icon :class="{ 'exited-arrow': true, 'is-open': showExited }">
                <ArrowDown />
              </el-icon>
            </div>
            <div v-show="showExited" class="exited-card-body">
              <div v-for="m in exitedMembers" :key="m.id" class="member-item">
                <el-avatar :size="30" class="member-avatar-pic" style="margin-right: 8px; cursor: pointer" @click="goPerson(m.person_id)">
                  {{ m.person_name?.charAt(0) }}
                </el-avatar>
                <div class="member-info">
                  <div class="member-name-row">
                    <strong class="person-link" @click="goPerson(m.person_id)">{{ m.person_name }}</strong>
                    <span v-if="m.person_position || m.person_department" class="member-position">
                      {{ m.person_position || m.person_department }}
                    </span>
                    <el-tag
                      v-if="m.role !== 'member' && !(roleLabel(m.role) === (m.person_position || m.person_department))"
                      size="small" :type="m.role === 'manager' ? 'danger' : ''"
                    >
                      {{ roleLabel(m.role) }}
                    </el-tag>
                    <el-tag v-if="m.stage" size="small" type="primary" effect="plain" style="margin-left: 4px">
                      {{ m.stage }}
                    </el-tag>
                    <el-tag size="small" type="info" style="margin-left: 4px">已退出</el-tag>
                  </div>
                  <div class="member-company" v-if="m.company_name">
                    <el-icon class="company-icon"><OfficeBuilding /></el-icon>
                    <el-link type="info" :underline="false" size="small" @click.stop="goCompany(m.company_id)">
                      {{ m.company_name }}
                    </el-link>
                  </div>
                  <div class="member-dates">
                    {{ formatDate(m.joined_at) }}
                    <template v-if="m.left_at"> → {{ formatDate(m.left_at) }}</template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 项目上下文: 行业情报 + 项目人脉(以项目为中心) -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="section-header">
          <span class="section-title">项目情报与人脉</span>
          <span class="section-sub">围绕本项目聚合行业动态(区分发布时间/抓取时间) + 相似项目触达网络</span>
          <div class="header-actions">
            <el-button size="small" :loading="ctxLoading" @click="loadProjectContext">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-link type="primary" :underline="false" class="rel-more" @click="router.push('/workspace/intelligence')">
              去行业情报 <el-icon><ArrowRight /></el-icon>
            </el-link>
          </div>
        </div>
      </template>

      <el-tabs v-model="ctxTab" class="ctx-tabs">
        <!-- Tab 1: 行业情报 -->
        <el-tab-pane label="行业情报" name="intel">
          <div class="ctx-toolbar">
            <el-radio-group v-model="intelStage" size="small" @change="loadProjectIntel">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="investment">投资意向期</el-radio-button>
              <el-radio-button label="bidding">招标期</el-radio-button>
              <el-radio-button label="awarded">中标公示期</el-radio-button>
            </el-radio-group>
            <el-tag v-if="ctxRegion" size="small" type="info" class="ctx-region-tag">{{ ctxRegion }}</el-tag>
            <span class="ctx-hint">* 发布时间=公告实际发布日期，抓取时间=系统采集入库时间</span>
          </div>
          <el-table v-if="intelItems.length" :data="intelItems" size="small" v-loading="intelLoading"
            class="clickable-table" @row-click="(r:any)=>r.url && openUrl(r.url)">
            <el-table-column label="阶段" width="96">
              <template #default="{ row }">
                <el-tag size="small" :type="intelStageType(row.stage)">{{ row.stage_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="250" show-overflow-tooltip />
            <el-table-column label="发布时间" width="130">
              <template #default="{ row }">
                <div class="time-cell">
                  <span class="time-pub">{{ row.published_at || '-' }}</span>
                  <span class="time-fetch">抓取 {{ row.fetched_at || '-' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="地域" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.province" size="small" effect="plain" type="warning">{{ row.province }}</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="source_name" label="来源" width="120" show-overflow-tooltip />
            <el-table-column prop="amount" label="预算" width="90">
              <template #default="{ row }">{{ row.amount || '-' }}</template>
            </el-table-column>
          </el-table>
          <div v-else-if="!intelLoading" class="intel-empty">
            暂无与本项目地域/类别相关的行业动态 — 建议在「网页线索」补充抓取川藏新意向源与招标源
          </div>
          <div v-if="intelItems.length" class="pager">
            <el-pagination
              layout="total, prev, pager, next" :total="intelTotal" :page-size="intelPageSize"
              :current-page="intelPage" @current-change="(p:number)=>{intelPage=p; loadProjectIntel();}"
            />
          </div>
        </el-tab-pane>

        <!-- Tab 2: 项目人脉 -->
        <el-tab-pane label="项目人脉(触达网络)" name="network">
          <div class="net-summary">
            <el-statistic title="相似项目" :value="net.related_projects?.length ?? 0" />
            <el-statistic title="相关单位" :value="net.related_companies?.length ?? 0" />
            <el-statistic title="关键人员" :value="net.key_persons?.length ?? 0" />
          </div>

          <!-- 相似项目 -->
          <div class="net-block">
            <div class="net-block-title"><el-icon><FolderOpened /></el-icon><span>相似项目(同类/同地域)</span></div>
            <div v-if="net.related_projects?.length" class="net-proj-list">
              <div class="net-proj-item" v-for="p in net.related_projects.slice(0, 3)" :key="p.id" @click="goProject(p.id)">
                <span class="net-proj-name">{{ p.name }}</span>
                <el-tag size="small" effect="plain">{{ p.category_zh || '未分类' }}</el-tag>
                <span class="net-proj-loc">{{ [p.province, p.city].filter(Boolean).join('·') || '-' }}</span>
                <el-tag size="small" :type="p.status==='completed'?'success':p.status==='active'?'primary':'info'">
                  {{ p.status_zh || p.status }}
                </el-tag>
              </div>
              <el-link v-if="net.related_projects.length > 3" type="primary" :underline="false"
                class="expand-link" @click="showMoreProjects = !showMoreProjects">
                {{ showMoreProjects ? '收起' : `展开全部 ${net.related_projects.length} 个` }}
                <el-icon><ArrowDown v-if="!showMoreProjects" /><ArrowUp v-else /></el-icon>
              </el-link>
              <template v-if="showMoreProjects">
                <div class="net-proj-item" v-for="p in net.related_projects.slice(3)" :key="p.id" @click="goProject(p.id)">
                  <span class="net-proj-name">{{ p.name }}</span>
                  <el-tag size="small" effect="plain">{{ p.category_zh || '未分类' }}</el-tag>
                  <span class="net-proj-loc">{{ [p.province, p.city].filter(Boolean).join('·') || '-' }}</span>
                  <el-tag size="small" :type="p.status==='completed'?'success':p.status==='active'?'primary':'info'">
                    {{ p.status_zh || p.status }}
                  </el-tag>
                </div>
              </template>
            </div>
            <div v-else class="intel-empty">暂无相似项目 — 系统将随项目数据积累自动关联</div>
          </div>

          <!-- 相关单位 -->
          <div class="net-block">
            <div class="net-block-title">
              <el-icon><OfficeBuilding /></el-icon><span>相关单位(做过相似项目)</span>
              <el-tag v-if="net.related_companies?.length" size="small" type="info">{{ net.related_companies.length }} 家</el-tag>
            </div>
            <el-table v-if="net.related_companies?.length" :data="net.related_companies.slice(0, showMoreCompanies ? 999 : 5)" size="small" class="clickable-table"
              @row-click="(r:any)=>goCompany(r.id)">
              <el-table-column prop="name" label="单位名称" min-width="240" show-overflow-tooltip />
              <el-table-column prop="roles_display" label="参与角色" min-width="160" show-overflow-tooltip />
              <el-table-column label="参与相似项目" width="100">
                <template #default="{ row }">{{ row.projects?.length ?? 0 }} 个</template>
              </el-table-column>
              <el-table-column prop="province" label="地域" width="90" />
            </el-table>
            <el-link v-if="net.related_companies?.length > 5" type="primary" :underline="false"
              class="expand-link" @click="showMoreCompanies = !showMoreCompanies">
              {{ showMoreCompanies ? '收起' : `展开全部 ${net.related_companies.length} 家` }}
              <el-icon><ArrowDown v-if="!showMoreCompanies" /><ArrowUp v-else /></el-icon>
            </el-link>
            <div v-else-if="!net.related_companies?.length" class="intel-empty">暂无关联单位</div>
          </div>

          <!-- 关键人员 + 触达路径 -->
          <div class="net-block">
            <div class="net-block-title">
              <el-icon><UserFilled /></el-icon><span>关键人员与触达路径</span>
              <el-tag v-if="net.key_persons?.length" size="small" type="info">{{ net.key_persons.length }} 人</el-tag>
            </div>
            <div v-if="net.key_persons?.length" class="net-person-list">
              <div class="net-person-card" v-for="p in net.key_persons.slice(0, showMorePersons ? 999 : 3)" :key="p.id">
                <div class="net-person-head">
                  <span class="net-person-name" @click="goPerson(p.id)">{{ p.name }}</span>
                  <el-tag size="small" effect="plain">{{ p.roles_display || p.position || '-' }}</el-tag>
                  <span class="net-person-company">{{ p.company_name || '-' }}</span>
                </div>
                <div class="net-person-projects">
                  参与项目：
                  <el-tag v-for="pn in p.project_names.slice(0,3)" :key="pn" size="small" effect="light" type="info">
                    {{ pn }}
                  </el-tag>
                  <span v-if="p.project_names.length>3">等 {{ p.project_names.length }} 个</span>
                </div>
                <div class="net-paths">
                  <div class="net-path-item" v-for="(path, i) in p.contact_paths.slice(0,3)" :key="i">
                    <el-icon><Position /></el-icon><span>{{ path }}</span>
                  </div>
                  <el-link v-if="(p.contact_paths?.length || 0) > 3" type="primary" :underline="false" class="expand-link" @click="p._pathsOpen = !p._pathsOpen">
                    {{ p._pathsOpen ? '收起路径' : `展开全部路径(${p.contact_paths.length})` }}
                  </el-link>
                  <template v-if="p._pathsOpen">
                    <div class="net-path-item" v-for="(path, i) in p.contact_paths.slice(3)" :key="i">
                      <el-icon><Position /></el-icon><span>{{ path }}</span>
                    </div>
                  </template>
                </div>
              </div>
              <el-link v-if="net.key_persons.length > 3" type="primary" :underline="false"
                class="expand-link" @click="showMorePersons = !showMorePersons">
                {{ showMorePersons ? '收起' : `展开全部 ${net.key_persons.length} 人` }}
                <el-icon><ArrowDown v-if="!showMorePersons" /><ArrowUp v-else /></el-icon>
              </el-link>
            </div>
            <div v-else class="intel-empty">暂无关键人员 — 相似项目关联后自动生成</div>
          </div>
        </el-tab-pane>

        <!-- Tab 3: 跟踪情报(自动归整到本项目, 按阶段监控) -->
        <el-tab-pane label="跟踪情报" name="tracked">
          <div class="ctx-toolbar">
            <span class="ctx-hint">系统自动把意向/招标/中标/施工线索归整到本项目(地域+类别+单位强匹配, 防张冠李戴), 随采集自动累积</span>
            <el-button size="small" :loading="trackedLoading" @click="loadTracked">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button size="small" type="primary" plain :loading="trackedRunning" @click="runTracker">
              <el-icon><VideoPlay /></el-icon>立即匹配新线索
            </el-button>
          </div>

          <div v-if="!trackedGroups.length && !trackedLoading" class="intel-empty">
            暂无已归整的跟踪线索 — 点击「立即匹配新线索」或等待每日自动匹配
          </div>
          <template v-else>
            <div class="tracked-group" v-for="g in trackedGroups" :key="g.stage">
              <div class="tracked-group-head">
                <el-tag size="small" :type="intelStageType(g.stage)" effect="dark">{{ g.stage_label }}</el-tag>
                <span class="tracked-group-count">{{ g.items.length }} 条</span>
              </div>
              <el-table :data="g.items" size="small" class="clickable-table"
                @row-click="(r:any)=>r.url && openUrl(r.url)">
                <el-table-column prop="title" label="线索标题" min-width="280" show-overflow-tooltip />
                <el-table-column label="发布时间" width="100">
                  <template #default="{ row }">{{ row.published_at || '-' }}</template>
                </el-table-column>
                <el-table-column prop="source_name" label="来源" width="130" show-overflow-tooltip />
                <el-table-column prop="purchaser" label="采购人/业主" width="140" show-overflow-tooltip />
                <el-table-column label="关联度" width="110">
                  <template #default="{ row }">
                    <el-tooltip :content="`依据: ${row.match_reason || '-'}`" placement="top">
                      <el-tag size="small" :type="row.confidence >= 0.9 ? 'success' : 'warning'">
                        {{ Math.round(row.confidence * 100) }}%
                      </el-tag>
                    </el-tooltip>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="showAddMember" title="添加项目成员" width="480px">
      <el-form :model="addMemberForm" label-width="100px">
        <el-form-item label="选择人员">
          <el-select
            v-model="addMemberForm.person_id"
            filterable remote
            :remote-method="searchPersons"
            placeholder="输入姓名搜索"
            style="width: 100%"
          >
            <el-option
              v-for="p in personOptions"
              :key="p.id"
              :label="`${p.name} (${p.company_name || '-'})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="addMemberForm.role" style="width: 100%">
            <el-option label="项目联系人" value="manager" />
            <el-option label="项目成员" value="member" />
            <el-option label="观察者" value="observer" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属阶段">
          <el-select v-model="addMemberForm.stage" clearable placeholder="不选=全程参与" style="width: 100%">
            <el-option v-for="s in memberStageOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="职责">
          <el-input v-model="addMemberForm.responsibility" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMember = false">取消</el-button>
        <el-button type="primary" @click="handleAddMember">确认</el-button>
      </template>
    </el-dialog>

    <!-- 编辑成员弹窗 -->
    <el-dialog v-model="showEditMember" :title="`编辑成员：${editMemberForm.person_name || ''}`" width="480px">
      <el-form :model="editMemberForm" label-width="100px">
        <el-form-item label="角色">
          <el-select v-model="editMemberForm.role" style="width: 100%">
            <el-option label="项目联系人" value="manager" />
            <el-option label="项目成员" value="member" />
            <el-option label="观察者" value="observer" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属阶段">
          <el-select v-model="editMemberForm.stage" clearable placeholder="不选=全程参与" style="width: 100%">
            <el-option v-for="s in memberStageOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="职责">
          <el-input v-model="editMemberForm.responsibility" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditMember = false">取消</el-button>
        <el-button type="primary" :loading="editMemberSaving" @click="handleUpdateMember">保存</el-button>
      </template>
    </el-dialog>

    <!-- 进展编辑弹窗 -->
    <el-dialog v-model="showProgressDialog" :title="progressForm.id ? '编辑进展' : '添加进展'" width="520px">
      <el-form :model="progressForm" label-width="90px" ref="progressFormRef">
        <el-form-item label="进展标题" required>
          <el-select
            v-model="progressForm.title"
            placeholder="请选择或输入项目进展阶段"
            style="width: 100%"
            filterable
            allow-create
            default-first-option
            :loading="stageLoading"
          >
            <!-- 进展标题: 使用完整阶段选项集 + 可输入新阶段(项目进度是自由记录的) -->
            <el-option
              v-for="s in stageOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="进展日期" required>
          <el-date-picker
            v-model="progressForm.progress_date"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择日期时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="进展详情">
          <el-input v-model="progressForm.content" type="textarea" :rows="4" placeholder="补充说明（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showProgressDialog = false">取消</el-button>
        <el-button type="primary" :loading="progressSaving" @click="saveProgress">保存</el-button>
      </template>
    </el-dialog>

    <!-- AI 分析师抽屉 -->
    <AiAnalystChat
      :key="aiChatKey"
      v-model="aiChatVisible"
      :me-name="''"
      :target-name="project.name || '目标项目'"
      :steps="aiSteps"
      :is-path="false"
      :fallback-result="aiFallback"
      :preset-question="aiPresetQuestion"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Document, User, Calendar, MagicStick, ArrowRight, ArrowDown, ArrowUp, OfficeBuilding,
  Refresh, Position, FolderOpened, UserFilled, VideoPlay,
} from "@element-plus/icons-vue";
import dayjs from "dayjs";
import api from "@/api";
import DynamicForm from "@/components/DynamicForm.vue";
import AiAnalystChat from "@/components/AiAnalystChat.vue";

const route = useRoute();
const router = useRouter();
// 路由 id 可能来自图谱/人脉路径(偶为字符串), 兜底为合法整数, 避免请求 /projects/NaN
const projectId = Number.isFinite(Number(route.params.id)) ? Number(route.params.id) : 0;

const project = ref<any>({});
const manager = ref<any>({});
const members = ref<any[]>([]);
const dynamicFields = ref<any[]>([]);
const editing = ref(false);
const saving = ref(false);
const showAddMember = ref(false);
const showEditMember = ref(false);
const editMemberSaving = ref(false);
const editMemberForm = ref<any>({
  id: null,
  person_id: null,
  person_name: "",
  role: "member",
  stage: "",
  responsibility: "",
});

/** 打开成员编辑弹窗(回填当前记录) */
function openEditMember(m: any) {
  editMemberForm.value = {
    id: m.id,
    person_id: m.person_id,
    person_name: m.person_name || "",
    role: m.role || "member",
    stage: m.stage || "",
    responsibility: m.responsibility || "",
  };
  showEditMember.value = true;
}

/** 保存成员编辑(角色/阶段/职责) */
async function handleUpdateMember() {
  const f = editMemberForm.value;
  if (!f.id) return;
  // 负责人是项目级角色, 不绑定阶段
  const stage = f.role === "manager" ? "" : f.stage || "";
  editMemberSaving.value = true;
  try {
    await api.put(`/project-members/${f.id}`, {
      role: f.role,
      stage,
      responsibility: f.responsibility,
    });
    ElMessage.success("成员已更新");
    showEditMember.value = false;
    await Promise.all([loadMembers(), loadProject()]);
  } catch { /* 错误由拦截器处理 */ }
  finally { editMemberSaving.value = false; }
}

const editForm = ref<any>({});
const editFormDynamic = ref<any>({ ext_attrs: {} });
const dynamicFormRef = ref<any>(null);
const editFormRef = ref<any>(null);
/** 省份/城市/区县: 存项目 ext_attrs.province/city/county, 列表与详情共用 */
const editProvince = ref("");
const editCity = ref("");
const editCounty = ref("");
const builtinRules = {
  name: [{ required: true, message: "项目名称为必填项", trigger: "blur" }],
};
/** 负责人候选: 仅限项目现有参与成员(在途)。若历史负责人不在成员中, 补入以便保留。 */
const managerOptions = computed(() => {
  const opts = members.value
    .filter((m: any) => m.is_active)
    .map((m: any) => ({
      id: m.person_id,
      name: m.person_name,
      position: m.person_position || m.person_department || "",
      company_name: m.company_name || "",
    }));
  if (project.value.manager_id) {
    const cur = manager.value;
    if (cur?.id && !opts.some((o: any) => o.id === cur.id)) {
      opts.unshift({ id: cur.id, name: cur.name, position: cur.position || "", company_name: cur.company_name || "" });
    }
  }
  return opts;
});

/** 判断成员是否为项目联系人(兼容 manager 枚举与「项目负责人」中文历史角色)。 */
function isManagerRole(role?: string): boolean {
  return role === "manager" || role === "项目负责人";
}

/** 项目联系人列表: 基于参与成员中 role=manager/项目负责人 的成员(支持多人)。 */
const managers = computed(() => members.value.filter((m: any) => isManagerRole(m.role) && m.is_active));

const addMemberForm = ref({
  project_id: projectId,
  person_id: null as number | null,
  role: "member",
  stage: "",
  responsibility: "",
});
const personOptions = ref<any[]>([]);

/* ─────────── 360° 看板: AI 分析 ─────────── */
const AI_CHIPS = [
  "分析项目当前风险点与推进建议",
  "分析项目关联人脉与合作机会",
  "分析项目预算与成本控制",
];
const aiChatVisible = ref(false);
const aiChatKey = ref(0);
const aiPresetQuestion = ref<string | undefined>(undefined);
const aiFallback = ref<any>(null);

/** 在途成员数(统计卡) */
const activeMemberCount = computed(() => members.value.filter((m: any) => m.is_active).length);

/** 参与单位总数 = 项目直接关联单位(project_company) + 成员反推公司, 去重 */
const allCompanyCount = computed(() => {
  const ids = new Set<number>();
  projectCompanies.value.forEach((c: any) => c.company_id && ids.add(c.company_id));
  derivedCompanies.value.forEach((c: any) => c.company_id && ids.add(c.company_id));
  return ids.size;
});

/** AI 分析上下文: 项目 + 参与单位 + 参与人员。
 * 注意: 这不是人脉路径——首节点不是「我」, 也不假设「我」参与了该项目,
 * 仅作为主题分析(风险/成本/机会等)的参考资料, 避免 AI 幻觉「我参与该项目」。 */
const aiSteps = computed(() => {
  const arr: any[] = [];
  if (project.value.name) {
    arr.push({
      type: "Project",
      name: project.value.name,
      status: statusLabel(project.value.status),
    });
  }
  for (const c of derivedCompanies.value) {
    arr.push({ type: "Company", name: c.company_name || "未归属单位", relation_label: "参与项目" });
  }
  for (const m of members.value.slice(0, 20)) {
    arr.push({
      type: "Person",
      name: m.person_name,
      relation_label: roleLabel(m.role),
      position: m.person_position || "",
      company_name: m.company_name || "",
    });
  }
  return arr;
});

function buildAiFallback(preset?: string): any {
  const pname = project.value.name || "该项目";
  const summary = preset
    ? `正在分析「${pname}」的${preset.replace(/^分析|项目|我方的|建议$/g, "").trim() || "整体"}情况…`
    : `正在分析「${pname}」的推进与合作情况…`;
  return {
    summary,
    bridges: [],
    companies: derivedCompanies.value.map((c) => ({
      name: c.company_name || "未归属单位",
      tip: `${c.members.length} 人参与`,
    })),
    projects: [
      {
        name: pname,
        tip: `状态：${statusLabel(project.value.status) || "-"}；负责人：${manager.value?.name || "-"}`,
      },
    ],
    advice: [
      "跟进未完成的进展节点, 及时补充最新进展记录",
      "通过参与单位锁定对口联系人, 深化合作关系",
      "关注项目验收/结算节点, 提前规划追加合作",
    ],
    opportunities: [
      `当前 ${derivedCompanies.value.length} 家单位、${members.value.length} 人参与该项目`,
      `共 ${progressList.value.length} 条进展记录${project.value.status === "active" ? "，项目仍在推进中" : ""}`,
    ],
  };
}

function openAiChat(preset?: string) {
  aiPresetQuestion.value = preset || undefined;
  // 与 AiAnalystChat SESSION_KEY(meName 为空) 保持一致, 保证重建组件后会话被清空
  try { sessionStorage.removeItem(`ssm_ai_chat__${project.value.name || "目标项目"}`); } catch { /* ignore */ }
  aiChatKey.value++;
  aiFallback.value = buildAiFallback(preset);
  aiChatVisible.value = true;
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    active: "进行中", suspended: "挂起", completed: "已完成", cancelled: "已取消",
  };
  return map[s] || s;
}

function statusTagType(s: string): string {
  const map: Record<string, string> = {
    active: "primary", suspended: "warning", completed: "success", cancelled: "danger",
  };
  return map[s] || "info";
}

function roleLabel(r: string): string {
  return { manager: "项目联系人", member: "成员", observer: "观察者" }[r] || r;
}

function formatNumber(v: any): string {
  if (v === undefined || v === null || v === "") return "-";
  return Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2 });
}

function formatDate(d: string): string {
  return d ? dayjs(d).format("YYYY-MM-DD") : "-";
}

function goPerson(personId: number) {
  if (personId) router.push(`/workspace/persons/${personId}`);
}

function goNetwork(personId: number) {
  if (personId) router.push(`/workspace/network/${personId}`);
}

// 顶部位置信息（优先从动态字段取）


// 项目进展（用户手动维护，支持增删改）
const progressList = ref<any[]>([]);
const showProgressDialog = ref(false);
const progressSaving = ref(false);
const progressForm = ref<any>({
  id: null, title: "", content: "", progress_date: "",
});
// 项目进展阶段选项集
const stageOptions = ref<any[]>([]);
const stageLoading = ref(false);

/**
 * 成员"所属阶段"下拉选项: 以该项目已有进展(title)为准, 去重后倒序(新进度在前)。
 * 选项集仅作兜底(项目暂无进展时)。"全程参与"由 clearable 的空值表达。
 */
const memberStageOptions = computed(() => {
  const fromProgress = Array.from(new Set(
    (progressList.value || []).map((p: any) => String(p.title || "")).filter(Boolean),
  ));
  if (fromProgress.length) {
    return fromProgress.map((t: string) => ({ value: t, label: t }));
  }
  return (stageOptions.value || []).map((s: any) => ({ value: s.value, label: s.label }));
});

async function loadStageOptions() {
  stageLoading.value = true;
  try {
    const res: any = await api.get("/option-sets/project_progress_stage/items");
    stageOptions.value = res.items || [];
  } catch {
    // 选项集接口不可用时保留空, 弹窗内提示无选项
    stageOptions.value = [];
  } finally {
    stageLoading.value = false;
  }
}

function formatDateTime(d: string): string {
  return d ? dayjs(d).format("YYYY-MM-DD HH:mm") : "-";
}

// 按进展阶段映射 tag 颜色（状态区分）
function stageTagType(title: string): any {
  if (!title) return "info";
  if (title.includes("完工") || title.includes("已完成")) return "success";
  if (title.includes("取消")) return "danger";
  if (title.includes("暂停")) return "warning";
  if (title.includes("施工")) return "primary";
  if (title.includes("未确定")) return "info";
  return "primary";
}

async function loadProgress() {
  try {
    const res: any = await api.get(`/project-progress/${projectId}`, { params: { page_size: 100 } });
    progressList.value = (res.items || []).sort(
      (a: any, b: any) => new Date(b.progress_date).getTime() - new Date(a.progress_date).getTime()
    );
  } catch { progressList.value = []; }
}

/* ─────────── 项目情报与人脉(以项目为中心) ─────────── */
const ctxTab = ref<"intel" | "network" | "tracked">("intel");
const ctxLoading = ref(false);
const trackedGroups = ref<any[]>([]);
const trackedLoading = ref(false);
const trackedRunning = ref(false);
const intelItems = ref<any[]>([]);
const intelTotal = ref(0);
const intelLoading = ref(false);
const intelPage = ref(1);
const intelPageSize = ref(10);
const intelStage = ref("");
const ctxRegion = ref("");
const net = ref<any>({ related_projects: [], related_companies: [], key_persons: [] });
const showMoreProjects = ref(false);
const showMoreCompanies = ref(false);
const showMorePersons = ref(false);

function goCompany(id: number) { router.push(`/workspace/companies/${id}`); }
function goProject(id: number) { router.push(`/workspace/projects/${id}`); }
function openUrl(url: string) { window.open(url, "_blank", "noopener"); }

function intelStageType(s: string) {
  return s === "investment" ? "success" : s === "bidding" ? "primary" : "warning";
}

/** 跟踪情报: 已自动归整到本项目的线索(按阶段分组) */
async function loadTracked() {
  trackedLoading.value = true;
  try {
    const res: any = await api.get(`/projects/tracker/${projectId}`);
    trackedGroups.value = res.groups || [];
  } catch { trackedGroups.value = []; }
  finally { trackedLoading.value = false; }
}

/** 立即触发一次全量增量匹配(把新线索归整到各项目) */
async function runTracker() {
  trackedRunning.value = true;
  try {
    const res: any = await api.post("/projects/tracker/run?limit=3000", {}, { timeout: 120000 });
    ElMessage.success(res.message || "匹配完成");
    await loadTracked();
  } catch { /* 拦截器 */ }
  finally { trackedRunning.value = false; }
}

/** 项目上下文: 地域展示串 */
function buildCtxRegion() {
  const ext = project.value.ext_attrs || {};
  const parts = [ext.province, ext.city, ext.county].filter(Boolean);
  ctxRegion.value = parts.join("·") || "";
}

/** 行业情报(聚合三源) */
async function loadProjectIntel() {
  intelLoading.value = true;
  try {
    const res: any = await api.get(`/projects/${projectId}/intelligence`, {
      params: {
        page: intelPage.value, page_size: intelPageSize.value,
        stage: intelStage.value || undefined, days: 365,
      },
    });
    intelItems.value = res.items || [];
    intelTotal.value = res.total || 0;
  } catch { intelItems.value = []; intelTotal.value = 0; }
  finally { intelLoading.value = false; }
}

/** 项目人脉(相似项目/单位/人员+触达路径) */
async function loadProjectNetwork() {
  try {
    const res: any = await api.get(`/projects/${projectId}/related-network`);
    net.value = res || { related_projects: [], related_companies: [], key_persons: [] };
  } catch { /* 拦截器 */ }
}

function loadProjectContext() {
  buildCtxRegion();
  loadProjectIntel();
  loadProjectNetwork();
}

function openProgressDialog(node: any) {
  if (node) {
    progressForm.value = {
      id: node.id, title: node.title, content: node.content || "",
      progress_date: node.progress_date,
    };
  } else {
    progressForm.value = {
      id: null, title: "", content: "",
      progress_date: dayjs().format("YYYY-MM-DDTHH:mm:ss"),
    };
  }
  showProgressDialog.value = true;
}

async function saveProgress() {
  if (!progressForm.value.title || !progressForm.value.progress_date) {
    ElMessage.warning("请填写进展标题与日期"); return;
  }
  progressSaving.value = true;
  try {
    if (progressForm.value.id) {
      await api.put(`/project-progress/${progressForm.value.id}`, {
        title: progressForm.value.title,
        content: progressForm.value.content,
        progress_date: progressForm.value.progress_date,
      });
    } else {
      await api.post(`/project-progress`, {
        project_id: projectId,
        title: progressForm.value.title,
        content: progressForm.value.content,
        progress_date: progressForm.value.progress_date,
      });
    }
    ElMessage.success("已保存");
    showProgressDialog.value = false;
    loadProgress();
  } catch { /* 拦截器处理 */ }
  finally { progressSaving.value = false; }
}

async function deleteProgress(node: any) {
  try {
    await ElMessageBox.confirm(`确定删除进展「${node.title}」？`, "删除", { type: "warning" });
  } catch { return; }
  try {
    await api.delete(`/project-progress/${node.id}`);
    ElMessage.success("已删除");
    loadProgress();
  } catch { /* 拦截器处理 */ }
}

// 项目概况: 清洗噪音行 → 段落级全局去重 → 小节标题/表格/正文 结构化渲染
//  (修复: 原实现只去相邻重复, 公告正文重复块(一/二/三...节)整体重复时无法去除,
//   表格(tab分隔)原样堆叠不美观。现按块签名去重 + 真实表格解析)
const overviewBlocks = computed(() => {
  const raw = project.value?.description || "";
  if (!raw) return [];
  const noise = /【(信息发布主体|发布时间|字号|打印|关闭|扫一扫|编辑|来源)|\b大中小\b|信息发布主体/;
  const lines = raw.split(/\r?\n/).map((l: string) => l.trim()).filter((l: string) => l && !noise.test(l));
  const seen = new Set<string>();
  const out: Array<{ kind: "title" | "table" | "text"; text: string; headers?: string[]; rows?: string[][] }> = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const isTitle = /^[一二三四五六七八九十]+、/.test(line);
    if (isTitle) {
      if (seen.has(line)) { i++; continue; }        // 重复小节标题(正文重复块)跳过
      seen.add(line);
      out.push({ kind: "title", text: line });
      i++;
      continue;
    }
    // 表格块: 连续含 tab 的行(表头+数据), 合并为真实表格
    if (line.includes("\t")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("\t")) {
        rows.push(lines[i].split("\t").map((c: string) => c.trim()));
        i++;
      }
      const sig = JSON.stringify(rows);
      if (seen.has(sig)) continue;                    // 重复表格块跳过
      seen.add(sig);
      out.push({ kind: "table", text: "", headers: rows[0] || [], rows: rows.slice(1) });
      continue;
    }
    if (seen.has(line)) { i++; continue; }            // 重复段落跳过
    seen.add(line);
    out.push({ kind: "text", text: line });
    i++;
  }
  return out;
});

// 项目介绍展示项（内置 + 动态字段合并）
const displayItems = computed(() => {
  const items: Array<{
    label: string;
    value: any;
    wide?: boolean;
    isTag?: boolean;
    tagType?: string;
    tagColor?: string;
    isMultiTag?: boolean;
    multiLabels?: string[];
    multiColors?: string[];
    isMoney?: boolean;
    isSwitch?: boolean;
  }> = [];

  // 内置字段
  items.push(
    { label: "项目编号", value: project.value.code },
    { label: "项目名称", value: project.value.name },
    { label: "项目状态", value: statusLabel(project.value.status), isTag: true, tagType: statusTagType(project.value.status) },
    {
      label: "联系人",
      // 优先 project_member 中 role=manager; 其次 manager_id 快照; 兜底 ext_attrs.contact(导入数据)
      value: managers.value.map((m: any) => m.person_name).join("、")
        || manager.value?.name
        || project.value.ext_attrs?.contact
        || "-",
      isTag: managers.value.length === 1,
      tagType: "danger",
      isMultiTag: managers.value.length > 1,
      multiLabels: managers.value.map((m: any) => m.person_name),
      multiColors: managers.value.map(() => ""),
    },
    { label: "启动日期", value: project.value.start_date },
    { label: "预计结束", value: project.value.end_date },
    {
      label: "省份城市",
      value: [project.value.ext_attrs?.province, project.value.ext_attrs?.city, project.value.ext_attrs?.county]
        .filter(Boolean).join("·") || "-",
      wide: true,
    },
  );

  // 动态字段
  const dynamicKeys = new Set<string>();
  for (const f of dynamicFields.value) {
    const raw = project.value.ext_attrs?.[f.field_key];
    const labelMap = new Map<string, string>((f.options || []).map((o: any) => [String(o.value), String(o.label ?? "")]));
    // 选项项配置的颜色标记(与选项集管理一致)
    const colorMap = new Map<string, string>((f.options || []).map((o: any) => [String(o.value), String(o.color ?? "")]));
    // 单选/多选: 将值(value)映射为中文名(label), 并携带选项颜色
    if (f.data_type === "select") {
      items.push({
        label: f.display_name,
        value: labelMap.get(raw) ?? raw ?? "-",
        isTag: true,
        tagType: "",
        tagColor: colorMap.get(raw) || "",
      });
    } else if (f.data_type === "multi_select") {
      const labels = (Array.isArray(raw) ? raw : []).map((x: any) => String(labelMap.get(x) ?? x ?? ""));
      const colors = (Array.isArray(raw) ? raw : []).map((x: any) => String(colorMap.get(x) ?? ""));
      items.push({
        label: f.display_name,
        value: labels.length ? labels.join("、") : "-",
        isTag: labels.length > 0,
        tagType: "",
        tagColor: colors.length ? colors[0] : "",
        isMultiTag: labels.length > 1,
        multiLabels: labels,
        multiColors: colors,
      });
    } else {
      items.push({
        label: f.display_name,
        value: raw,
        wide: f.data_type === "textarea",
        isMoney: f.data_type === "money",
        isSwitch: f.data_type === "switch",
      });
    }
    dynamicKeys.add(f.field_key);
  }

  // 兜底: ext_attrs 中存在但 form-config 未配置的常见业务字段(金额/联系), 保证详情页可见
  const ext = project.value.ext_attrs || {};
  const fallbacks: Array<{ label: string; key: string; isMoney?: boolean }> = [
    { label: "金额", key: "amount", isMoney: true },
    { label: "联系", key: "contact" },
  ];
  for (const fb of fallbacks) {
    if (!dynamicKeys.has(fb.key) && ext[fb.key] !== undefined && ext[fb.key] !== null && ext[fb.key] !== "") {
      items.push({
        label: fb.label,
        value: ext[fb.key],
        isMoney: fb.isMoney,
      });
    }
  }

  return items;
});

async function loadProject() {
  // 非法/缺失的项目 id: 不发起 /projects/NaN 请求, 提示后回退列表
  if (!projectId) {
    ElMessage.error("无效的项目 ID");
    router.push("/workspace/projects");
    return;
  }
  try {
    const res: any = await api.get(`/projects/${projectId}`);
    project.value = res;
    if (res.manager_id) await loadManager(res.manager_id);
  } catch { /* 跳回列表 */ }
}

async function loadManager(managerId: number) {
  try {
    manager.value = await api.get(`/persons/${managerId}`);
  } catch { manager.value = {}; }
}

// 由参与成员反推参与公司 + 成员分组（仅统计在途成员；已退出人员单独展示）
const derivedCompanies = computed(() => {
  const map = new Map<number | string, any>();
  for (const m of members.value) {
    if (!m.is_active) continue;
    const cid = m.company_id ?? "none";
    if (!map.has(cid)) {
      map.set(cid, {
        company_id: m.company_id ?? null,
        company_name: m.company_name || (m.company_id ? "未命名单位" : ""),
        members: [] as any[],
      });
    }
    map.get(cid).members.push(m);
  }
  // 有单位的排前面，未归属排最后
  const arr = Array.from(map.values());
  arr.sort((a, b) => {
    if (!a.company_id && b.company_id) return 1;
    if (a.company_id && !b.company_id) return -1;
    return (a.company_name || "").localeCompare(b.company_name || "", "zh");
  });
  return arr;
});

/** 已退出人员（is_active=false），单独折叠卡片展示 */
const exitedMembers = computed(() => members.value.filter((m: any) => !m.is_active));

/** 已退出折叠卡是否展开 */
const showExited = ref(false);

async function loadMembers() {
  try {
    const res: any = await api.get(`/project-members/timeline/${projectId}`, {
      params: { include_inactive: true },
    });
    members.value = res.items || [];
  } catch { members.value = []; }
}

// 项目-单位直接关联(project_company): 含法人单位/业主等, 独立展示项目参与主体
const projectCompanies = ref<any[]>([]);

async function loadProjectCompanies() {
  try {
    const res: any = await api.get(`/project-companies/timeline/${projectId}`, {
      params: { include_inactive: true },
    });
    projectCompanies.value = (res.items || []).filter((it: any) => it.is_active);
  } catch { projectCompanies.value = []; }
}

// 项目单位角色中文名
const COMPANY_ROLE_LABEL: Record<string, string> = {
  owner: "业主", designer: "设计", supervisor: "监理",
  constructor: "施工", partner: "合作伙伴",
};
function companyRoleLabel(role?: string) {
  if (!role) return "";
  return COMPANY_ROLE_LABEL[role] || role;
}

// 某参与单位下的项目成员（按成员所属单位匹配）— 已由 derivedCompanies 取代

async function loadDynamicFields() {
  try {
    const res: any = await api.get(`/dynamic/project/form-config?mode=view`);
    dynamicFields.value = res.fields || [];
  } catch { dynamicFields.value = []; }
}

function startEdit() {
  editForm.value = { ...project.value };
  // 负责人多选: 基于参与成员中 role=manager 的人员
  editForm.value.manager_ids = managers.value
    .map((m: any) => m.person_id)
    .filter((id: any) => id != null);
  editFormDynamic.value = { ext_attrs: { ...(project.value.ext_attrs || {}) } };
  editProvince.value = project.value.ext_attrs?.province || "";
  editCity.value = project.value.ext_attrs?.city || "";
  editCounty.value = project.value.ext_attrs?.county || "";
  editing.value = true;
}

function cancelEdit() {
  editing.value = false;
}

async function saveEdit() {
  // 校验内置必填 + 动态字段必填，不通过则中断保存
  try {
    await editFormRef.value.validate();
  } catch { return; }
  if (dynamicFormRef.value) {
    const ok = await dynamicFormRef.value.validate();
    if (!ok) return;
  }
  saving.value = true;
  try {
    let dynamic = { ...(editFormDynamic.value.ext_attrs || {}) };
    // 省份/城市: 项目自身维护, 写进 ext_attrs(列表优先取项目自身值)
    if (editProvince.value.trim()) dynamic.province = editProvince.value.trim();
    else delete dynamic.province;
    if (editCity.value.trim()) dynamic.city = editCity.value.trim();
    else delete dynamic.city;
    if (editCounty.value.trim()) dynamic.county = editCounty.value.trim();
    else delete dynamic.county;
    if (dynamicFields.value.length > 0) {
      for (const f of dynamicFields.value) {
        const v = editFormDynamic.value[f.field_key];
        if (v !== undefined && v !== null && v !== "") dynamic[f.field_key] = v;
      }
    } else {
      const builtin = ["code","name","description","status","manager_id","ext_attrs","id","created_at","updated_at","is_deleted"];
      for (const [k, v] of Object.entries(editFormDynamic.value)) {
        if (!builtin.includes(k) && v !== undefined && v !== null && v !== "") dynamic[k] = v;
      }
    }

    if (dynamicFormRef.value) {
      const ok = await dynamicFormRef.value.validate();
      if (!ok) return;
    }

    await api.put(`/projects/${projectId}`, {
      name: editForm.value.name,
      description: editForm.value.description,
      status: editForm.value.status,
      manager_id: editForm.value.manager_ids?.[0] ?? null,
      start_date: editForm.value.start_date,
      end_date: editForm.value.end_date,
      ext_attrs: dynamic,
    });

    // 负责人多选联动: 选中的成员 role=manager, 取消的原负责人改回 member
    const want = new Set<number>((editForm.value.manager_ids || []).map(Number));
    for (const m of members.value) {
      if (!m.person_id || !m.is_active) continue;
      const isManager = want.has(Number(m.person_id));
      const curIsManager = isManagerRole(m.role);
      if (isManager && !curIsManager) {
        await api.put(`/project-members/${m.id}`, { role: "manager" });
      } else if (!isManager && curIsManager) {
        await api.put(`/project-members/${m.id}`, { role: "member" });
      }
    }
    ElMessage.success("保存成功");
    editing.value = false;
    // 负责人变更会同时影响顶部负责人卡片与成员列表角色 tag, 两者都需重载
    await Promise.all([loadProject(), loadMembers()]);
  } catch { /* 错误由拦截器处理 */ }
  finally { saving.value = false; }
}

async function searchPersons(query: string) {
  if (!query) { personOptions.value = []; return; }
  try {
    const res: any = await api.get("/persons", { params: { keyword: query, page_size: 20 } });
    personOptions.value = res.items || [];
  } catch { personOptions.value = []; }
}

async function handleAddMember() {
  if (!addMemberForm.value.person_id) {
    ElMessage.warning("请选择人员"); return;
  }
  // 负责人是项目级角色(全程参与), 不绑定单一阶段, 避免负责人只出现在某个阶段分组
  const stage = addMemberForm.value.role === "manager" ? "" : addMemberForm.value.stage || "";
  if (addMemberForm.value.role === "manager" && addMemberForm.value.stage) {
    ElMessage.info("项目联系人默认全程参与, 不绑定具体阶段");
  }
  try {
    await api.post("/project-members", {
      project_id: projectId,
      person_id: addMemberForm.value.person_id,
      role: addMemberForm.value.role,
      stage,
      responsibility: addMemberForm.value.responsibility,
    });
    ElMessage.success("成员已添加");
    showAddMember.value = false;
    addMemberForm.value.person_id = null;
    addMemberForm.value.stage = "";
    addMemberForm.value.responsibility = "";
    loadMembers();
  } catch { /* error handled by interceptor */ }
}

onMounted(() => {
  loadProject();
  loadMembers();
  loadProjectCompanies();
  loadDynamicFields();
  loadProgress();
  loadStageOptions();
  loadProjectContext();
  loadTracked();
});
</script>

<style scoped>
.project-detail {
  max-width: 1400px;
}
.header-card {
  margin-top: 16px;
  background: linear-gradient(135deg, #f0f7ff 0%, #ffffff 100%);
  border-top: 4px solid #2979ff;
}
.header-main {
  padding: 8px 4px;
}
.header-sub {
  display: flex;
  align-items: center;
  gap: 24px;
  color: #606266;
  font-size: 14px;
  margin-bottom: 12px;
}
.location {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #2979ff;
}
.header-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.section-card {
  margin-bottom: 16px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  font-weight: 600;
  font-size: 16px;
  color: #303133;
  position: relative;
  padding-left: 12px;
}
.section-title::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 16px;
  background: #2979ff;
  border-radius: 2px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.progress-node {
  background: #f5f7fa;
  padding: 10px 14px;
  border-radius: 6px;
}
.progress-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.progress-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.progress-ops {
  flex-shrink: 0;
}
.progress-desc {
  font-size: 13px;
  color: #606266;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: #ebeef5;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}
.info-cell {
  background: #fff;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.info-cell-wide {
  grid-column: span 3;
}
.info-label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}
.info-value {
  font-size: 14px;
  color: #303133;
  line-height: 1.5;
  word-break: break-all;
}
.info-value-pre {
  font-size: 14px;
  color: #303133;
  line-height: 1.7;
  white-space: pre-wrap;       /* 保留 description 中的换行 */
  word-break: break-word;
}
.overview-section {
  margin-top: 14px;
  padding: 16px 18px;
  background: linear-gradient(180deg, #fbfcff 0%, #f6f8fc 100%);
  border: 1px solid #e8ecf5;
  border-radius: 12px;
}
.overview-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14.5px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 12px;
}
.overview-title-icon {
  color: #4f6ef7;
  width: 16px;
  height: 16px;
}
.overview-content { font-size: 13.5px; color: #4b5264; line-height: 1.85; word-break: break-word; }
.overview-para { margin: 5px 0; }
.overview-para-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 6px;
  font-weight: 600;
  color: #1f2d3d;
  font-size: 13.5px;
}
.overview-para-title:first-child { margin-top: 0; }
.ov-title-mark {
  width: 4px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, #4f6ef7, #7c9bf7);
  flex-shrink: 0;
}
.ov-table {
  width: 100%;
  margin: 8px 0 10px;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid #e4e9f2;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  font-size: 12.5px;
}
.ov-table thead th {
  background: #eef2fb;
  color: #303a52;
  font-weight: 600;
  padding: 8px 12px;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid #dfe6f3;
}
.ov-table tbody td {
  padding: 7px 12px;
  color: #4b5264;
  border-bottom: 1px solid #f0f3f9;
}
.ov-table tbody tr:last-child td { border-bottom: none; }
.ov-table tbody tr:nth-child(even) { background: #fafbfe; }
.ov-table tbody tr:hover { background: #f3f6fd; }
.ov-table tbody td:first-child { font-weight: 500; color: #3a4150; }
.edit-form {
  padding-top: 8px;
}
.member-item {
  display: flex;
  align-items: flex-start;
}
.member-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.person-link {
  color: #2979ff;
  cursor: pointer;
}
.person-link:hover {
  text-decoration: underline;
}
.company-link {
  color: #2979ff;
  cursor: pointer;
}
.company-link:hover {
  text-decoration: underline;
}
.member-company {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 3px;
  color: #909399;
  font-size: 12px;
}
.company-icon {
  color: #909399;
}
.member-dates {
  font-size: 12px;
  color: #909399;
}
.exited-card {
  margin-top: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
}
.exited-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  background: #f5f7fa;
}
.exited-card-header:hover {
  background: #eef1f6;
}
.exited-card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}
.exited-arrow {
  transition: transform 0.25s;
  color: #909399;
}
.exited-arrow.is-open {
  transform: rotate(180deg);
}
.exited-card-body {
  padding: 8px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.exited-card-body .member-item {
  padding: 6px 8px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #f0f2f5;
}
.member-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.member-position {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}
/* 公司分组卡片: 以公司为主体, 阶段作为人员属性 tag */
.company-group-card {
  background: #fafbfd;
  border: 1px solid #eceff5;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}
.company-group-card:last-child { margin-bottom: 0; }
.company-group-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  background: #f3f6fb;
  border-bottom: 1px solid #eceff5;
}
.company-group-icon { color: #2979ff; font-size: 14px; flex-shrink: 0; }
.company-group-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.company-group-name:hover { color: #2979ff; text-decoration: underline; }
.company-group-count {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
  flex-shrink: 0;
}
.company-group-body { padding: 8px 12px 10px; }
/* 项目参与单位(直接关联)区块 */
.project-companies-block { display: flex; flex-direction: column; gap: 6px; }
.project-companies-title {
  font-size: 12px; font-weight: 600; color: #909399;
  display: flex; align-items: center; gap: 6px; margin-bottom: 2px;
}
.project-company-row {
  display: flex; align-items: center; gap: 6px;
  background: #fff; border: 1px solid #f0f2f6; border-radius: 6px;
  padding: 7px 10px;
}
.project-company-name {
  font-size: 13px; font-weight: 600; color: #303133; cursor: pointer;
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.project-company-name:hover { color: #2979ff; text-decoration: underline; }
.member-card {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #f0f2f6;
  border-radius: 6px;
  padding: 7px 9px;
  margin-top: 6px;
  transition: border-color 0.18s ease;
}
.member-card:hover { border-color: #b9d4ff; }
.member-card-info { flex: 1; min-width: 0; }
.member-card-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.member-card-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}
.member-card-company {
  font-size: 12px;
  color: #4b5264;
}
.member-card-date { color: #b0b3bd; }
.company-members {
  margin-top: 8px;
  margin-left: 12px;
  padding-left: 10px;
  border-left: 2px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.no-member {
  margin-top: 6px;
  margin-left: 12px;
  font-size: 12px;
  color: #c0c4cc;
}
.unassigned-block {
  margin-top: 12px;
}
.unassigned-block .member-item {
  margin-top: 10px;
}
.member-item { align-items: center; }
/* 成员头像统一品牌蓝渐变 */
.member-avatar-pic {
  background: linear-gradient(135deg, #4f8df9 0%, #2979ff 55%, #1d63e0 100%) !important;
  color: #fff !important;
  font-weight: 600;
}
/* 成员操作(编辑/查看人脉) */
.member-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 8px;
}
/* 查看人脉(与商业信息/人员/单位详情页一致的浅蓝链接样式) */
.member-relation-link {
  flex-shrink: 0;
  margin-left: 8px;
  font-size: 12px !important;
  padding: 0 8px;
  height: 22px;
  line-height: 20px;
  border: 1px solid #d9ecff;
  background: #ecf5ff;
  color: #2979ff !important;
  border-radius: 4px;
}
.member-relation-link:hover {
  background: #2979ff;
  color: #fff !important;
}

/* ─── 360° 看板: 顶部主信息卡 ─── */
.fgbs-header {
  margin-top: 16px;
  background: #fff;
  border-top: 3px solid #2979ff;
  border-radius: 4px;
  padding: 18px 22px 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.fgbs-head-main {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.fgbs-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1f2d3d;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.fgbs-head-spacer { flex: 1; }
.fgbs-print { border-radius: 14px; }
.fgbs-print :deep(.el-icon) { margin-right: 3px; }

/* 三张信息小卡 */
.fgbs-info-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.fgbs-info-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f5f8fc;
  border-radius: 6px;
  padding: 12px 14px;
  min-height: 56px;
}
.fgbs-info-icon {
  width: 32px; height: 32px;
  background: #fff;
  border: 1px solid #e6ebf5;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  color: #2979ff;
  font-size: 16px;
  flex-shrink: 0;
}
.fgbs-info-body { flex: 1; min-width: 0; }
.fgbs-info-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.fgbs-info-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 负责人多标签 */
.fgbs-managers { display: flex; gap: 4px; flex-wrap: wrap; white-space: normal; }
.fgbs-manager-tag { max-width: 120px; overflow: hidden; text-overflow: ellipsis; }

/* AI分析能力横幅 */
.ai-banner {
  margin-top: 14px;
  background: linear-gradient(90deg, #eef4ff 0%, #f7faff 100%);
  border: 1px solid #dde7fa;
  border-radius: 6px;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ai-banner-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.ai-banner-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #2979ff;
  font-size: 14px;
  flex-shrink: 0;
  margin-right: 4px;
}
.ai-banner-label :deep(.el-icon) { font-size: 14px; }
.ai-banner-label b { font-weight: 700; }
.ai-chip {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #dde7fa;
  color: #4b6cb7;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.18s ease;
  user-select: none;
}
.ai-chip:hover {
  background: #2979ff;
  color: #fff;
  border-color: #2979ff;
}
.ai-more { flex-shrink: 0; }

/* 统计卡片条 */
.fgbs-stats {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.fgbs-stat {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.fgbs-stat .stat-num {
  font-size: 26px;
  font-weight: 700;
  color: #2979ff;
  line-height: 1;
}
.fgbs-stat .stat-label {
  font-size: 13px;
  color: #909399;
}

@media (max-width: 900px) {
  .fgbs-info-cards { grid-template-columns: 1fr; }
  .fgbs-stats { grid-template-columns: 1fr 1fr; }
}

/* ─── 项目情报与人脉 ─── */
.header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rel-more { font-size: 12px; display: inline-flex; align-items: center; gap: 2px; }
.ctx-tabs :deep(.el-tabs__header) { margin-bottom: 10px; }
.ctx-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.ctx-region-tag { margin-left: 4px; }
.ctx-hint { font-size: 12px; color: #c0c4cc; }
.intel-empty { color: #c0c4cc; font-size: 12.5px; padding: 14px 4px; }
.tracked-group { margin-bottom: 16px; }
.tracked-group-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.tracked-group-count { font-size: 12.5px; color: #909399; }
.time-cell { display: flex; flex-direction: column; line-height: 1.4; }
.time-pub { color: #303133; font-size: 12.5px; }
.time-fetch { color: #c0c4cc; font-size: 11px; }
.clickable-table :deep(.el-table__row) { cursor: pointer; }
.clickable-table :deep(.el-table__row:hover > td.el-table__cell) { background-color: #eef5ff !important; }

.net-summary { display: flex; gap: 40px; margin-bottom: 14px; }
.net-summary :deep(.el-statistic__number) { color: #2979ff; font-size: 22px; }
.net-block { margin-bottom: 14px; }
.net-block-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13.5px; font-weight: 600; color: #1f2d3d; margin-bottom: 8px;
}
.net-block-title :deep(.el-icon) { color: #2979ff; }
.net-proj-list { display: flex; flex-direction: column; gap: 6px; }
.net-proj-item {
  display: flex; align-items: center; gap: 10px;
  background: #f8fbff; border: 1px solid #eef2f9; border-radius: 6px; padding: 8px 12px;
  cursor: pointer; font-size: 12.5px;
}
.net-proj-item:hover { background: #eef5ff; }
.net-proj-name { color: #2979ff; font-weight: 500; min-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.net-proj-loc { color: #909399; font-size: 12px; }
.net-person-list { display: flex; flex-direction: column; gap: 10px; }
.net-person-card {
  background: #f8fbff; border: 1px solid #eef2f9; border-radius: 8px; padding: 10px 14px;
}
.net-person-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.net-person-name { color: #2979ff; font-weight: 600; font-size: 14px; cursor: pointer; }
.net-person-name:hover { text-decoration: underline; }
.net-person-company { color: #606266; font-size: 12.5px; }
.net-person-projects { margin-top: 6px; font-size: 12.5px; color: #606266; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.net-paths { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.net-path-item { display: flex; align-items: flex-start; gap: 6px; font-size: 12.5px; color: #4b6cb7; }
.net-path-item :deep(.el-icon) { color: #2979ff; margin-top: 2px; }
.expand-link { display: inline-flex; align-items: center; gap: 2px; margin-top: 8px; font-size: 12.5px; }
.pager { display: flex; justify-content: flex-end; margin-top: 10px; }
</style>
