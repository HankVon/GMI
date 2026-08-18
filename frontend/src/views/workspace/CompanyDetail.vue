<!-- 公司/单位 360° 商情详情页 -->
<template>
  <div class="company-detail">
    <!-- 返回列表(与项目详情页一致) -->
    <el-page-header @back="router.back()" title="返回列表">
      <template #content>
        <span>{{ company.name || "加载中..." }}</span>
      </template>
    </el-page-header>

    <!-- 顶部主信息卡(白底 + 蓝色顶边, 名称 + 标记合作 + 打印) -->
    <div class="fgbs-header">
      <div class="fgbs-head-main">
        <h2 class="fgbs-title">{{ company.name || "加载中..." }}</h2>
        <el-tag type="primary" effect="plain" round size="small" class="fgbs-mark">
          <el-icon><Star /></el-icon><span>标记合作</span>
        </el-tag>
        <el-tooltip content="如何标记？" placement="top">
          <el-icon class="fgbs-help"><QuestionFilled /></el-icon>
        </el-tooltip>
        <div class="fgbs-head-spacer" />
        <el-button type="primary" size="small" class="fgbs-print" @click="onPrint">
          <el-icon><Printer /></el-icon><span>点击打印</span>
        </el-button>
      </div>

      <!-- 三张信息小卡: fgbs编号 / 详细地址 / 公司座机 -->
      <div class="fgbs-info-cards">
        <div class="fgbs-info-card">
          <div class="fgbs-info-icon"><el-icon><Document /></el-icon></div>
          <div class="fgbs-info-body">
            <div class="fgbs-info-label">fgbs公司编号</div>
            <div class="fgbs-info-value">{{ company.code || company.credit_code || "-" }}</div>
          </div>
        </div>
        <div class="fgbs-info-card">
          <div class="fgbs-info-icon"><el-icon><Location /></el-icon></div>
          <div class="fgbs-info-body">
            <div class="fgbs-info-label">详细地址</div>
            <div
              class="fgbs-info-value is-link"
              :title="fullAddress ? fullAddress + '（点击打开地图）' : ''"
              @click="openAddressMap"
            >
              {{ fullAddress }}
              <el-icon v-if="fullAddress && fullAddress !== '-'" class="map-go"><Right /></el-icon>
            </div>
          </div>
        </div>
        <div class="fgbs-info-card">
          <div class="fgbs-info-icon"><el-icon><Phone /></el-icon></div>
          <div class="fgbs-info-body">
            <div class="fgbs-info-label">公司座机</div>
            <div class="fgbs-info-value">{{ companyLandline || "-" }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI分析能力横幅: 标签条 + 更多分析入口 -->
    <div class="ai-banner">
      <div class="ai-banner-left">
        <span class="ai-banner-label">
          <el-icon><MagicStick /></el-icon><b>AI分析:</b>
        </span>
        <span
          v-for="(c, i) in AI_CHIPS"
          :key="i"
          class="ai-chip"
          @click="openAiChat(c)"
        >{{ c }}</span>
      </div>
      <el-link type="primary" :underline="false" class="ai-more" @click="openAiChat()">
        更多分析 <el-icon><ArrowRight /></el-icon>
      </el-link>
    </div>

    <!-- 主选项卡: 商情分析报告 / fgbs大数据 -->
    <div class="fgbs-tabs">
      <div
        class="fgbs-tab"
        :class="{ 'is-active': mainTab === 'analysis' }"
        @click="mainTab = 'analysis'"
      >商情分析报告</div>
      <div
        class="fgbs-tab"
        :class="{ 'is-active': mainTab === 'fgbs' }"
        @click="mainTab = 'fgbs'"
      >单位信息</div>
    </div>

    <!-- 商情分析报告视图 -->
    <div v-show="mainTab === 'analysis'" class="fgbs-panel">
      <!-- 子选项卡: 潜在商机 / 公司背景 / 公关路径 / 情报关联 -->
      <div class="fgbs-subtabs">
        <div
          class="fgbs-subtab"
          :class="{ 'is-active': subTab === 'biz' }"
          @click="subTab = 'biz'"
        >潜在商机</div>
        <div
          class="fgbs-subtab"
          :class="{ 'is-active': subTab === 'bg' }"
          @click="subTab = 'bg'"
        >公司背景</div>
        <div
          class="fgbs-subtab"
          :class="{ 'is-active': subTab === 'pr' }"
          @click="subTab = 'pr'"
        >公关路径</div>
        <div
          class="fgbs-subtab"
          :class="{ 'is-active': subTab === 'rel' }"
          @click="subTab = 'rel'"
        >情报关联</div>
      </div>

      <!-- 潜在商机 -->
      <div v-show="subTab === 'biz'" class="biz-section">
        <div class="biz-head">
          <div class="biz-head-text">
            <span class="biz-key">潜在商机</span>
            <span class="biz-desc">助您挖掘客户公司更多项目机会, 投入相同沟通成本, 实现业绩翻倍</span>
          </div>
          <el-button type="primary" size="small" @click="openAiChat('分析此公司的项目采购机会与潜在商机')">
            <el-icon><MagicStick /></el-icon>点AI分析项目机会
          </el-button>
        </div>
        <div class="biz-foot">
          <span class="biz-note">* 以下为当前账号可阅内容数据, 不代表当前企业全部数据</span>
        </div>
        <div class="biz-stat-cards">
          <div class="biz-stat-card">
            <div class="biz-stat-icon"><el-icon><Briefcase /></el-icon></div>
            <div class="biz-stat-info">
              <div class="biz-stat-title">项目商机</div>
              <div class="biz-stat-meta">
                <a class="biz-stat-strong biz-link" @click="openProjects(false)">{{ projects.length }}</a> 个相关项目
                <span class="biz-stat-divider">|</span>
                <a class="biz-stat-strong biz-link" @click="openRelatedPersons">{{ stats.related_persons?.length ?? relatedContactCount }}</a> 位关联联系人
              </div>
              <div class="biz-stat-meta">
                <a class="biz-stat-strong biz-link" @click="openProjects(true)">{{ unfinishedCount }}</a> 个未竣工项目
                <span class="biz-stat-divider">|</span>
                <a class="biz-stat-strong biz-link" @click="openUnfinishedPersons">{{ stats.unfinished_persons?.length ?? unfinishedContactCount }}</a> 位未竣工项目联系人
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 公司背景 -->
      <div v-show="subTab === 'bg'" class="biz-section">
        <div class="biz-head">
          <div class="biz-head-text">
            <span class="biz-key">公司背景</span>
            <span class="biz-desc">深度剖析客户公司背景, 助您快速了解客户情况, 判断合作风险</span>
          </div>
          <el-button type="primary" size="small" @click="openAiChat('分析此公司的背景与信用情况')">
            <el-icon><MagicStick /></el-icon>点AI分析公司背景及信用情况
          </el-button>
        </div>
        <div class="biz-foot">
          <span class="biz-note">* 以下为当前账号可阅内容数据, 不代表当前企业全部数据</span>
        </div>
        <div class="bg-grid">
          <div class="bg-row" v-for="it in baseInfoItems" :key="it.label">
            <span class="bg-label">{{ it.label }}:</span>
            <span class="bg-value">{{ it.value || "-" }}</span>
            <div v-if="it.note" class="bg-note" :title="`原因：${it.note.reason}\n建议：${it.note.suggest}`">
              <el-icon><InfoFilled /></el-icon>
              <span>{{ it.note.reason }}（{{ it.note.suggest }}）</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 公关路径 -->
      <div v-show="subTab === 'pr'" class="biz-section">
        <div class="biz-head">
          <div class="biz-head-text">
            <span class="biz-key">公关路径</span>
            <span class="biz-desc">基于单位人员关系, 梳理最有效的触达与公关建议</span>
          </div>
          <el-button type="primary" size="small" plain @click="toggleGraph">
            <el-icon><MagicStick /></el-icon>{{ graphVisible ? "收起人脉图谱" : "展开人脉图谱" }}
          </el-button>
        </div>
        <div class="biz-foot">
          <span class="biz-note">* 以下为当前账号可阅内容数据, 不代表当前企业全部数据</span>
        </div>

        <!-- 从「我」到本公司的真实人脉路径(Neo4j) -->
        <div class="pr-path">
          <div class="pr-path-title">
            <el-icon><Share /></el-icon>
            <span>从「我」到「{{ company.name }}」的触达路径</span>
            <el-tag v-if="companyPath.found && companyPath.steps.length > 1" size="small" type="primary" effect="dark">
              {{ companyPath.steps.length - 1 }} 跳
            </el-tag>
          </div>
          <div v-loading="pathLoading" class="pr-path-chain">
            <template v-if="companyPath.found && companyPath.steps.length">
              <template v-for="(s, idx) in companyPath.steps" :key="idx">
                <div
                  class="pr-node"
                  :class="{ 'is-me': idx === 0, 'is-target': idx === companyPath.steps.length - 1 }"
                  :title="s.name"
                >
                  <el-icon v-if="s.type === 'Company'"><OfficeBuilding /></el-icon>
                  <el-icon v-else-if="s.type === 'Project'"><FolderOpened /></el-icon>
                  <span v-else class="pr-node-avatar">{{ s.name?.[0] || "?" }}</span>
                  <span class="pr-node-name">{{ s.name }}</span>
                  <el-tag v-if="idx === companyPath.steps.length - 1" size="small" type="primary">目标</el-tag>
                  <span v-else-if="idx > 0" class="pr-node-type">{{ prNodeTypeLabel(s.type) }}</span>
                </div>
                <span v-if="idx < companyPath.steps.length - 1" class="pr-node-rel">
                  <el-icon><Right /></el-icon>
                  <span class="pr-node-rel-text">{{ companyPath.steps[idx + 1].relation_label || "" }}</span>
                </span>
              </template>
            </template>
            <div v-else-if="!pathLoading" class="pr-path-empty">
              {{ companyPath.message || "未找到从你到本公司的触达路径" }}
            </div>
          </div>
        </div>

        <!-- 单位人脉图谱(中心单位 + 内部联系人 / 合作方, 参考图风格) -->
        <CompanyGraph v-if="graphVisible" :company-id="companyId" :company-name="company.name || ''" />

      </div>

      <!-- 情报关联: 中标网络 / 知识图谱关系 / 人脉边 -->
      <div v-show="subTab === 'rel'" class="biz-section">
        <div class="biz-head">
          <div class="biz-head-text">
            <span class="biz-key">情报关联</span>
            <span class="biz-desc">中标市场四象限 + 开放域知识关系 + 人脉边，洞察本单位的市场位势与关系网络</span>
          </div>
          <el-button type="primary" size="small" plain @click="loadRelData">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
        <div class="biz-foot">
          <span class="biz-note">* 中标网络基于公告解析，知识关系来自 LLM 开放域抽取，人脉边来自项目/人员聚合</span>
        </div>

        <!-- 1. 中标网络四象限 -->
        <div class="rel-block">
          <div class="rel-block-title">
            <el-icon><Trophy /></el-icon>
            <span>中标网络</span>
            <el-tag v-if="bidNet" size="small" type="info">{{ bidNet.stats?.bids_won ?? 0 }} 次中标 / {{ bidNet.stats?.bids_purchased ?? 0 }} 次发标</el-tag>
          </div>
          <div v-loading="bidNetLoading" class="rel-grid">
            <div class="rel-cell">
              <div class="rel-cell-title">潜在业主(中标对象)</div>
              <div v-if="bidNet?.potential_owners?.length" class="rel-list">
                <div class="rel-item" v-for="o in bidNet.potential_owners" :key="o.company_id">
                  <span class="rel-name" @click="goCompany(o.company_id)">{{ o.name }}</span>
                  <el-tag size="small" type="success">{{ o.bid_count }}次</el-tag>
                </div>
              </div>
              <div v-else class="rel-empty">暂无同名中标记录</div>
            </div>
            <div class="rel-cell">
              <div class="rel-cell-title">同地域潜在业主</div>
              <div v-if="bidNet?.region_owners?.length" class="rel-list">
                <div class="rel-item" v-for="(o, i) in bidNet.region_owners" :key="i">
                  <span class="rel-name" :class="{ 'is-link': o.company_id }" @click="o.company_id && goCompany(o.company_id)">{{ o.purchaser }}</span>
                  <el-tag size="small" type="warning">{{ o.count }}次</el-tag>
                </div>
              </div>
              <div v-else class="rel-empty">暂无同地域业主线索</div>
            </div>
            <div class="rel-cell">
              <div class="rel-cell-title">竞对(同场竞标)</div>
              <div v-if="bidNet?.competitors?.length" class="rel-list">
                <div class="rel-item" v-for="o in bidNet.competitors" :key="o.company_id">
                  <span class="rel-name" @click="goCompany(o.company_id)">{{ o.name }}</span>
                  <el-tag size="small" type="danger">{{ o.bid_count }}次</el-tag>
                </div>
              </div>
              <div v-else class="rel-empty">暂无竞对数据</div>
            </div>
            <div class="rel-cell">
              <div class="rel-cell-title">潜在合作方(供应商)</div>
              <div v-if="bidNet?.potential_suppliers?.length" class="rel-list">
                <div class="rel-item" v-for="o in bidNet.potential_suppliers" :key="o.company_id">
                  <span class="rel-name" @click="goCompany(o.company_id)">{{ o.name }}</span>
                  <el-tag size="small" type="primary">{{ o.bid_count }}次</el-tag>
                </div>
              </div>
              <div v-else class="rel-empty">暂无合作方数据</div>
            </div>
          </div>
        </div>

        <!-- 2. 知识图谱关系 -->
        <div class="rel-block">
          <div class="rel-block-title">
            <el-icon><Share /></el-icon>
            <span>知识图谱关系</span>
          </div>
          <el-table v-if="kgRels.length" :data="kgRels" size="small" v-loading="kgRelLoading" max-height="280">
            <el-table-column label="方向" width="60">
              <template #default="{ row }">
                <el-tag size="small" :type="row.direction === 'out' ? 'primary' : 'success'">
                  {{ row.direction === 'out' ? '出' : '入' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关系" width="140">
              <template #default="{ row }"><el-tag size="small" type="warning">{{ row.relation_zh || row.relation }}</el-tag></template>
            </el-table-column>
            <el-table-column label="对方实体" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.direction === 'out' ? (row.target?.name ?? '-') : (row.source?.name ?? '-') }}</template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" width="90" />
            <el-table-column prop="evidence" label="证据" min-width="220" show-overflow-tooltip />
          </el-table>
          <div v-else-if="!kgRelLoading" class="rel-empty">暂无开放域关系 — 可在知识图谱页粘贴文本抽取入库</div>
        </div>

        <!-- 3. 人脉边 -->
        <div class="rel-block">
          <div class="rel-block-title">
            <el-icon><Connection /></el-icon>
            <span>人脉边</span>
          </div>
          <el-table v-if="netEdges.length" :data="netEdges" size="small" v-loading="netEdgeLoading" max-height="280">
            <el-table-column label="方向" width="60">
              <template #default="{ row }">
                <el-tag size="small" :type="row.direction === 'out' ? 'primary' : 'success'">
                  {{ row.direction === 'out' ? '出' : '入' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关系" width="140">
              <template #default="{ row }"><el-tag size="small" type="warning">{{ row.rel_zh || row.rel }}</el-tag></template>
            </el-table-column>
            <el-table-column label="对方实体" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.other?.type }}·{{ row.other?.name }}</template>
            </el-table-column>
            <el-table-column prop="weight" label="权重" width="70" />
            <el-table-column prop="evidence" label="证据(项目/来源)" min-width="240" show-overflow-tooltip />
          </el-table>
          <div v-else-if="!netEdgeLoading" class="rel-empty">暂无聚合人脉边 — 可在人脉库页点击「初始化/重建人脉库」</div>
        </div>
      </div>
    </div>

    <!-- fgbs大数据视图: 参与项目 / 基础信息 / 编辑 -->
    <div v-show="mainTab === 'fgbs'" class="fgbs-panel">
      <el-row :gutter="16">
        <el-col :span="16">
          <!-- 基础信息 / 编辑 -->
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title">基础信息</span>
                <div v-if="editing" class="header-actions">
                  <el-button size="small" @click="cancelEdit">取消</el-button>
                  <el-button type="primary" size="small" :loading="saving" @click="saveEdit">保存</el-button>
                </div>
                <div v-else class="header-actions">
                  <el-button :loading="enrichingFree" size="small" @click="enrichFree">免费补全</el-button>
                  <el-button :loading="enriching" type="warning" size="small" @click="enrich">企查查补全</el-button>
                  <el-button type="primary" size="small" @click="startEdit">编辑</el-button>
                </div>
              </div>
            </template>

            <div v-if="!editing" class="info-grid">
              <div class="info-cell" v-for="item in displayItems" :key="item.label">
                <div class="info-label">{{ item.label }}</div>
                <div class="info-value">{{ item.value ?? "-" }}</div>
                <div v-if="item.note" class="info-note" :title="`原因：${item.note.reason}\n建议：${item.note.suggest}`">
                  <el-icon><InfoFilled /></el-icon>
                  <span>不可探查：{{ item.note.reason }}</span>
                </div>
              </div>
            </div>

            <!-- 全部联系方式(可选主要) -->
            <div v-if="!editing && extraContacts.length" class="extra-contacts">
              <div class="extra-contacts-title">
                全部联系方式
                <span class="extra-sub">点击「设为主」可将某条电话/地址设为主要联系方式</span>
              </div>
              <div class="extra-contact-item" v-for="(c, i) in extraContacts" :key="i">
                <el-tag size="small" :type="c.kind === 'phone' ? 'primary' : 'warning'" class="extra-kind">
                  {{ c.kind === 'phone' ? '电话' : '地址' }}
                </el-tag>
                <span class="extra-value">{{ c.value }}</span>
                <span v-if="c.isPrimary" class="extra-primary-tag">主要</span>
                <el-button v-else link type="primary" size="small" @click="setPrimary(c)">设为主</el-button>
              </div>
            </div>

            <el-form v-if="editing" ref="editFormRef" :model="editForm" label-width="120px" class="edit-form" :rules="builtinRules">
              <el-row :gutter="16">
                <el-col :span="12"><el-form-item label="单位名称" prop="name"><el-input v-model="editForm.name" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="信用代码"><el-input v-model="editForm.credit_code" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="单位类型"><el-input v-model="editForm.company_type" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="行业"><el-input v-model="editForm.industry" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="简称"><el-input v-model="editForm.short_name" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="省份"><el-input v-model="editForm.province" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="城市"><el-input v-model="editForm.city" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="信用等级"><el-input v-model="editForm.credit_level" /></el-form-item></el-col>
                <el-col :span="12"><el-form-item label="官网"><el-input v-model="editForm.website" /></el-form-item></el-col>
              </el-row>
              <el-form-item label="地址"><el-input v-model="editForm.address" /></el-form-item>
              <el-divider content-position="left">扩展字段（法定代表人 / 注册资本 / 联系方式等）</el-divider>
              <DynamicForm ref="dynamicFormRef" entity-type="company" v-model="editFormDynamic" mode="edit" />
            </el-form>
          </el-card>

          <!-- 参与项目 -->
          <el-card class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title">参与项目 ({{ projects.length }})</span>
              </div>
            </template>
            <el-table v-if="projects.length > 0" :data="projects" size="small" class="clickable-table"
              @row-click="(r:any)=>goProject(r.id)">
              <el-table-column prop="code" label="编号" width="140" />
              <el-table-column prop="name" label="项目名称" min-width="200">
                <template #default="{ row }">
                  <span class="link-name">{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="role" label="角色" width="120">
                <template #default="{ row }">{{ companyRoleLabel[row.role] || row.role }}</template>
              </el-table-column>
              <el-table-column width="36" align="right">
                <template #default>
                  <el-icon class="row-arrow"><ArrowRight /></el-icon>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无参与项目" :image-size="60" />
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title">单位人员 ({{ persons.length }})</span>
              </div>
            </template>
            <el-table v-if="persons.length > 0" :data="persons" size="small" class="clickable-table"
              @row-click="(r:any)=>goPerson(r.id)">
              <el-table-column prop="name" label="姓名" width="100">
                <template #default="{ row }">
                  <span class="link-name">{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="position" label="职位" min-width="100" />
              <el-table-column label="操作" min-width="90">
                <template #default="{ row }">
                  <el-link
                    type="primary" :underline="false" class="member-relation-link"
                    @click.stop="viewNetwork(row.id)"
                  >查看人脉</el-link>
                </template>
              </el-table-column>
              <el-table-column width="36" align="right">
                <template #default>
                  <el-icon class="row-arrow"><ArrowRight /></el-icon>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无人员" :image-size="60" />
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- AI 分析师抽屉(复用网络路径组件; 传入当前公司作为目标) -->
    <AiAnalystChat
      :key="aiChatKey"
      v-model="aiChatVisible"
      :me-name="aiIsPath ? '我' : ''"
      :target-name="company.name || '目标单位'"
      :steps="aiSteps"
      :is-path="aiIsPath"
      :fallback-result="aiFallback"
      :preset-question="aiPresetQuestion"
    />

    <!-- 项目商机 / 未竣工项目 列表抽屉 -->
    <el-drawer
      v-model="drawerProjects"
      :size="680"
      direction="rtl"
      :title="`${projectDrawerTitle}（${projectDrawerList.length}）`"
    >
      <div v-if="projectDrawerList.length" class="drawer-list">
        <ProjectCard
          v-for="p in projectDrawerList"
          :key="p.id"
          :project="p"
          :role-label-map="companyRoleLabel"
          :category-label-map="categoryLabelMap"
          @open="goProject(p.id)"
        />
      </div>
      <el-empty v-else :description="`暂无${projectDrawerTitle}`" :image-size="80" />
    </el-drawer>

    <!-- 关联联系人列表抽屉 -->
    <el-drawer
      v-model="drawerRelatedPersons"
      :size="620"
      direction="rtl"
      :title="`关联联系人（${stats.related_persons?.length ?? persons.length}）`"
    >
      <div v-if="(stats.related_persons?.length ?? persons.length)" class="drawer-list">
        <PersonCard
          v-for="p in (stats.related_persons?.length ? stats.related_persons : persons)"
          :key="p.id"
          :person="p"
          :company-name="company.name"
          @open="goPerson(p.id)"
          @network="viewNetwork(p.id)"
        />
      </div>
      <el-empty v-else description="暂无关联联系人" :image-size="80" />
    </el-drawer>

    <!-- 未竣工项目联系人列表抽屉 -->
    <el-drawer
      v-model="drawerUnfinishedPersons"
      :size="620"
      direction="rtl"
      :title="`未竣工项目联系人（${stats.unfinished_persons?.length ?? unfinishedContactCount}）`"
    >
      <div v-if="stats.unfinished_persons?.length" class="drawer-list">
        <PersonCard
          v-for="p in stats.unfinished_persons"
          :key="p.id"
          :person="p"
          :company-name="company.name"
          @open="goPerson(p.id)"
          @network="viewNetwork(p.id)"
        />
      </div>
      <el-empty v-else description="暂无未竣工项目联系人" :image-size="80" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Star, QuestionFilled, Printer, Document, Location, Phone,
  MagicStick, ArrowRight, Briefcase, Refresh, Trophy, Share, Connection,
  Right, OfficeBuilding, FolderOpened, InfoFilled,
} from "@element-plus/icons-vue";
import dayjs from "dayjs";
import api from "@/api";
import DynamicForm from "@/components/DynamicForm.vue";
import AiAnalystChat from "@/components/AiAnalystChat.vue";
import PersonCard from "@/components/PersonCard.vue";
import ProjectCard from "@/components/ProjectCard.vue";
import CompanyGraph from "@/components/CompanyGraph.vue";

const route = useRoute();
const router = useRouter();
const companyId = Number(route.params.id);

const company = ref<any>({});
const persons = ref<any[]>([]);
const projects = ref<any[]>([]);
const dynamicFields = ref<any[]>([]);
const editing = ref(false);
const saving = ref(false);
const enriching = ref(false);
const enrichingFree = ref(false);
const editForm = ref<any>({});
const editFormDynamic = ref<any>({ ext_attrs: {} });

/* ─────────── 商情统计(后端 /stats) ─────────── */
const stats = ref<any>({});
const drawerProjects = ref(false);
const drawerRelatedPersons = ref(false);
const drawerUnfinishedPersons = ref(false);

/* ─────────── 到公司的真实人脉路径(Neo4j) ─────────── */
interface CompanyPathStep {
  type: string;
  name: string;
  relation?: string;
  relation_label?: string;
  company_name?: string;
  position?: string;
}
interface CompanyPathData {
  found: boolean;
  steps: CompanyPathStep[];
  message: string;
}
const companyPath = ref<CompanyPathData>({ found: false, steps: [], message: "" });
const pathLoading = ref(false);

/* ─────────── 选项卡 ─────────── */
const mainTab = ref<"analysis" | "fgbs">("analysis");
const subTab = ref<"biz" | "bg" | "pr" | "rel">("biz");

/* ─────────── 情报关联(中标网络 / 知识关系 / 人脉边) ─────────── */
const bidNet = ref<any>(null);
const bidNetLoading = ref(false);
const kgRels = ref<any[]>([]);
const kgRelLoading = ref(false);
const netEdges = ref<any[]>([]);
const netEdgeLoading = ref(false);

async function loadBidNet() {
  bidNetLoading.value = true;
  try {
    const res: any = await api.get(`/bids/network/company/${companyId}`);
    bidNet.value = res || null;
  } catch { bidNet.value = null; }
  finally { bidNetLoading.value = false; }
}
async function loadKgRels() {
  kgRelLoading.value = true;
  try {
    const res: any = await api.get(`/knowledge/relations/company/${companyId}`);
    kgRels.value = res?.items || [];
  } catch { kgRels.value = []; }
  finally { kgRelLoading.value = false; }
}
async function loadNetEdges() {
  netEdgeLoading.value = true;
  try {
    const res: any = await api.get(`/biz-network/edges/company/${companyId}`);
    netEdges.value = res?.items || [];
  } catch { netEdges.value = []; }
  finally { netEdgeLoading.value = false; }
}
function loadRelData() {
  loadBidNet();
  loadKgRels();
  loadNetEdges();
}

/** 跳转其他单位详情 */
function goCompany(id?: number | null) {
  if (!id) return;
  router.push(`/workspace/companies/${id}`);
}

/* ─────────── AI 入口 ─────────── */
const AI_CHIPS = [
  "分析此公司决策链",
  "公关路径建议",
  "分析项目采购机会",
  "公司背景及信用情况",
  "总结此公司合作偏好",
];
const aiChatVisible = ref(false);
const aiFallback = ref<any>(null);
/** 每次点击 AI 分析 +1, 作为 :key 强制重建抽屉组件, 保证每次都触发新的首轮分析 */
const aiChatKey = ref(0);
/** 打开抽屉时的预设分析问题(点哪个按钮就分析什么) */
const aiPresetQuestion = ref<string | undefined>(undefined);
/** 是否为「我→本公司」真实人脉路径模式(首节点为我); 回退为参与项目列表时不是路径 */
const aiIsPath = computed<boolean>(
  () =>
    companyPath.value.found &&
    !!companyPath.value.steps?.length &&
    companyPath.value.steps[0]?.type === "Person" &&
    companyPath.value.steps[0]?.name === "我"
);
const aiSteps = computed(() => {
  // 优先用从「我」到本公司的真实人脉路径(Neo4j), 让 AI 能识别真实中间桥接人/单位;
  // 找不到真实路径时回退为参与项目列表(实体上下文, 非人脉路径)。
  if (companyPath.value.found && companyPath.value.steps?.length) {
    return companyPath.value.steps.map((s: any) => ({
      type: s.type,
      name: s.name,
      relation: s.relation,
      relation_label: s.relation_label,
      position: s.position,
      company_name: s.company_name,
      rel_via_project: s.rel_via_project,
      rel_company: s.rel_company,
      status: s.status,
      category: s.category,
    }));
  }
  return projects.value.map((p) => ({
    type: "Project",
    name: p.name,
    role: companyRoleLabel[p.role] || p.role,
    status: p.status,
  }));
});
async function openAiChat(preset?: string) {
  // 确保「我→本公司」真实路径已加载: 若仍在加载或未加载, 先等它完成,
  // 避免 AI 分析拿参与项目列表误判路径(老问题: 分析显示"通过某项目"而非真实桥接人)。
  if (!companyPath.value.found && pathLoading.value) {
    await loadCompanyPath();
  }
  if (!companyPath.value.found && !pathLoading.value) {
    await loadCompanyPath();
  }
  aiPresetQuestion.value = preset || undefined;
  // 清除该目标会话的历史记录(两种模式 key 都清), 重建组件, 确保每次点击都触发全新的首轮分析
  const cnm = company.value.name || "目标单位";
  try {
    sessionStorage.removeItem(`ssm_ai_chat_我_${cnm}`);
    sessionStorage.removeItem(`ssm_ai_chat__${cnm}`);
  } catch { /* ignore */ }
  aiChatKey.value++;
  // 预设一个简明的内置规则结果, 让 drawer 即便未配置 AI 模型也能直接展示
  aiFallback.value = buildAiFallback(preset);
  aiChatVisible.value = true;
}

/** 内置规则结果: 优先基于「我→本公司」真实路径生成(真实桥接人), 而非参与项目列表 */
function buildAiFallback(preset?: string): any {
  const cname = company.value.name || "目标单位";
  const pathSteps = companyPath.value.found ? companyPath.value.steps || [] : [];
  const target = pathSteps[pathSteps.length - 1];
  // 路径中间节点(不含源/目标)
  const midPersons = pathSteps.filter((s, i) => i > 0 && i < pathSteps.length - 1 && s.type === "Person");
  const midOthers = pathSteps.filter((s, i) => i > 0 && i < pathSteps.length - 1 && s.type !== "Person");

  let summary: string;
  if (pathSteps.length >= 2) {
    const hops = pathSteps.length - 1;
    const via =
      midPersons.length
        ? midPersons.map((p) => `「${p.name}」${p.company_name ? `(${p.company_name}任职)` : ""}`).join("、")
        : midOthers.map((s) => `「${s.name}」`).join("、") || "直接参与的关系";
    summary = `从你到「${target?.name || cname}」共 ${hops} 跳${via ? `，经由 ${via}` : ""}，这是知识图谱中的真实人脉路径。`;
  } else {
    summary = preset
      ? `正在分析「${cname}」的${preset.replace(/^分析此公司|分析|情况$/g, "").trim() || "整体"}情况…`
      : `正在分析「${cname}」的合作偏好…`;
  }

  return {
    summary,
    bridges: midPersons.map((p) => ({
      name: p.name,
      position: p.position,
      company_name: p.company_name,
      tip: p.company_name
        ? `在「${p.company_name}」任职，是连接你与目标公司的关键桥接人，建议先联系建立引荐`
        : "是连接你与目标公司的关键人物，建议直接沟通请求引荐",
    })),
    companies: [
      {
        name: target?.name || cname,
        tip: "目标公司，可结合主营业务与近期招投标动态寻找合作切入点",
      },
      ...pathSteps
        .filter((s, i) => i > 0 && i < pathSteps.length - 1 && s.type === "Company")
        .map((c) => ({ name: c.name, tip: "路径上的关联单位" })),
    ],
    projects: projects.value.slice(0, 5).map((p) => ({
      name: p.name,
      tip: `角色：${companyRoleLabel[p.role] || p.role || "-"}；状态：${statusLabel(p.status) || "-"}`,
    })),
    advice: [
      "从已参与的工程项目切入, 跟进最新进展寻找追加合作机会",
      "通过单位人员关系图谱锁定决策人, 缩短沟通链路",
      "关注单位的工商变更(法人/股东)与招投标动态, 把握入场时机",
    ],
    opportunities: [
      `当前共有 ${projects.value.length} 个参与项目, 其中 ${unfinishedCount.value} 个未竣工`,
      `可关联的内部联系人 ${relatedContactCount.value} 位, 建议优先触达决策岗位`,
    ],
  };
}

const companyRoleLabel: Record<string, string> = {
  builder: "建设单位", design: "设计单位", construction: "施工单位",
  supervisor: "监理单位", investor: "投资方", other: "其他",
};

const editFormRef = ref<any>(null);
const dynamicFormRef = ref<any>(null);
const builtinRules = {
  name: [{ required: true, message: "单位名称为必填项", trigger: "blur" }],
};

function statusLabel(s: string): string {
  return { active: "进行中", suspended: "挂起", completed: "已完成", cancelled: "已取消" }[s] || s;
}
function prNodeTypeLabel(t: string): string {
  return { Person: "人员", Company: "单位", Project: "项目" }[t] || t || "";
}
function statusTagType(s: string): string {
  return { active: "primary", suspended: "warning", completed: "success", cancelled: "danger" }[s] || "info";
}
function goProject(id: number) { router.push(`/workspace/projects/${id}`); }
function goPerson(id: number) { router.push(`/workspace/persons/${id}`); }
function viewNetwork(id: number) { router.push(`/workspace/network/${id}`); }

/** 公关路径内嵌人脉图谱的展开/收起 */
const graphVisible = ref(true);
function toggleGraph() { graphVisible.value = !graphVisible.value; }

const fullAddress = computed(() => {
  const c = company.value;
  const parts = ["中国内地", c.province, c.city, c.address].filter(Boolean);
  return parts.join(",") || "-";
});

/** 点击详细地址 → 高德地图网页版搜索定位 */
function openAddressMap() {
  const c = company.value || {};
  const q = [c.address, c.city, c.province, c.name].filter(Boolean).join(" ").trim();
  if (!q) {
    ElMessage.info("暂无地址信息");
    return;
  }
  window.open(`https://uri.amap.com/search?keyword=${encodeURIComponent(q)}`, "_blank", "noopener");
}
const companyLandline = computed(() => {
  const ext = company.value.ext_attrs || {};
  return ext.company_phone || ext.phone || ext.landline || ext.contact_phone || "";
});

const baseInfoItems = computed(() => {
  const ext = company.value.ext_attrs || {};
  const notes = company.value.field_notes || {};
  const items: any[] = [
    ["法定代表人", ext.legal_rep || ext.legal_person, "legal_rep"],
    ["成立日期", ext.establish_date ? dayjs(ext.establish_date).format("YYYY-MM-DD") : (ext.founded_at || ""), "establish_date"],
    ["注册资本", ext.registered_capital ? `${ext.registered_capital} 万元` : "", "registered_capital"],
    ["经营状态", ext.oper_status || ext.business_status || "", "oper_status"],
    ["统一社会信用代码", company.value.credit_code, "credit_code"],
  ];
  return items.map(([label, value, key]) => {
    const item: any = { label, value };
    const empty = value === undefined || value === null || String(value).trim() === "" ||
                  ["/", "-", "无"].includes(String(value).trim());
    if (empty && notes[key]) item.note = notes[key];
    // 空值且无说明 → 不返回(隐藏); 有值 或 空值但有"为什么查不到"提示 → 保留
    return empty && !item.note ? null : item;
  }).filter(Boolean);
});

const unfinishedCount = computed(() => projects.value.filter((p) => p.status === "active").length);
/** 未竣工项目列表(带 role/status) */
const unfinishedProjects = computed(() =>
  projects.value.filter((p) => p.status === "active")
);
/** 项目抽屉是否只显示未竣工(项目商机=false, 未竣工项目=true) */
const projectDrawerOnlyUnfinished = ref(false);
/** 项目抽屉标题 */
const projectDrawerTitle = computed(() =>
  projectDrawerOnlyUnfinished.value ? "未竣工项目" : "项目商机"
);
/** 项目抽屉数据: 未竣工用 stats.unfinished_projects(富字段), 项目商机用全部项目 */
const projectDrawerList = computed(() => {
  if (projectDrawerOnlyUnfinished.value) {
    const rich = stats.value.unfinished_projects;
    if (rich?.length) return rich;
    return unfinishedProjects.value;
  }
  return stats.value.all_projects?.length ? stats.value.all_projects : projects.value;
});
/** 项目类别标签映射(从 option-set 动态加载, 与字段管理/选项集配置一致) */
const categoryLabelMap = ref<Record<string, string>>({});
async function loadCategories() {
  try {
    const res: any = await api.get("/option-sets/project_category/items");
    const m: Record<string, string> = {};
    for (const i of (res.items || [])) m[i.value] = i.label;
    categoryLabelMap.value = m;
  } catch { categoryLabelMap.value = {}; }
}
/** 未竣工项目联系人: 优先取后端关联统计, 回退为公司人员 */
const unfinishedContactCount = computed(() =>
  stats.value.unfinished_persons?.length ?? persons.value.length
);
/** 关联联系人 = 本单位人员 */
const relatedContactCount = computed(() => stats.value.related_persons?.length ?? persons.value.length);

function onPrint() {
  window.print();
}

function openProjects(onlyUnfinished: boolean) {
  projectDrawerOnlyUnfinished.value = onlyUnfinished;
  drawerProjects.value = true;
}

/** 加载从「我」到本公司的真实 Neo4j 人脉路径(用于公关路径子面板与 AI 分析) */
async function loadCompanyPath() {
  pathLoading.value = true;
  try {
    const res: any = await api.get(`/network/path-to-company/${companyId}`);
    companyPath.value = res || { found: false, steps: [], message: "" };
  } catch {
    companyPath.value = { found: false, steps: [], message: "" };
  } finally {
    pathLoading.value = false;
  }
}
function openRelatedPersons() { drawerRelatedPersons.value = true; }
function openUnfinishedPersons() { drawerUnfinishedPersons.value = true; }

async function loadStats() {
  try {
    const res: any = await api.get(`/companies/${companyId}/stats`);
    stats.value = res?.data || {};
  } catch { stats.value = {}; }
}

/** 字段 key → displayItems 项 key 的映射(内置列/动态字段) */
function noteKeyFor(label: string): string {
  const notes = company.value.field_notes || {};
  // 直接命中 field_key
  const dyn = (dynamicFields.value || []).find((f: any) => f.display_name === label);
  if (dyn && notes[dyn.field_key]) return dyn.field_key;
  // 内置列: 用 label 反查 field_notes
  const builtinMap: Record<string, string> = {
    "统一社会信用代码": "credit_code", "单位类型": "company_type",
    "省份": "province", "城市": "city", "地址": "address",
  };
  const k = builtinMap[label];
  if (k && notes[k]) return k;
  return "";
}

/** 全部联系方式(多电话/多地址 + 当前主要) */
const extraContacts = computed(() => {
  const ext = company.value.ext_attrs || {};
  const mainPhone = ext.contact_phone || ext.contact || ext.company_phone || "";
  const mainAddr = company.value.address || "";
  const list = (ext.extra_contacts || []).slice();
  const out: any[] = [];
  const seen = new Set<string>();
  for (const v of list) {
    if (!v || seen.has(v)) continue;
    seen.add(v);
    const isPhone = /^\d[\d\- ]{5,}$/.test(String(v));
    out.push({ kind: isPhone ? "phone" : "address", value: String(v), isPrimary: false });
  }
  // 主要联系方式置顶标记
  if (mainPhone) {
    const found = out.find((o) => o.kind === "phone" && o.value === mainPhone);
    if (found) found.isPrimary = true;
  }
  if (mainAddr) {
    const found = out.find((o) => o.kind === "address" && o.value === mainAddr);
    if (found) found.isPrimary = true;
  }
  return out;
});

async function setPrimary(c: any) {
  try {
    const res: any = await api.put(`/companies/${companyId}/set-primary`, {
      kind: c.kind,
      value: c.value,
    });
    ElMessage.success(res.message || "已设为主要联系方式");
    loadCompany();
  } catch { /* 拦截器 */ }
}

const displayItems = computed(() => {
  const ext = company.value.ext_attrs || {};
  const builtin = [
    ["统一社会信用代码", company.value.credit_code],
    ["单位类型", company.value.company_type],
    ["行业", company.value.industry],
    ["省份", company.value.province],
    ["城市", company.value.city],
    ["地址", company.value.address],
  ];
  const dyn = (dynamicFields.value || [])
    .map((f: any) => [f.display_name, ext[f.field_key]]);
  return [...builtin, ...dyn].map(([label, value]) => {
    const item: any = { label, value };
    const empty = value === undefined || value === null || String(value).trim() === "" ||
                  ["/", "-", "无"].includes(String(value).trim());
    // 空值且配置了不可探查说明 → 附上说明
    if (empty) {
      const k = noteKeyFor(label);
      const note = company.value.field_notes?.[k];
      if (note) item.note = note;
    }
    // 空值且无说明 → 隐藏; 有值 或 空值但有"为什么查不到"提示 → 保留
    return empty && !item.note ? null : item;
  }).filter(Boolean);
});

async function loadCompany() {
  try {
    company.value = await api.get(`/companies/${companyId}`);
  } catch { router.back(); }
}
async function loadPersons() {
  try {
    const res: any = await api.get(`/companies/${companyId}/persons`);
    persons.value = res.data || [];
  } catch { persons.value = []; }
}
async function loadProjects() {
  try {
    const res: any = await api.get(`/companies/${companyId}/projects`, { params: { page_size: 100 } });
    projects.value = res.items || [];
  } catch { projects.value = []; }
}
async function loadDynamicFields() {
  try {
    const res: any = await api.get(`/dynamic/company/form-config?mode=view`);
    dynamicFields.value = res.fields || [];
  } catch { dynamicFields.value = []; }
}

function startEdit() {
  editForm.value = { ...company.value };
  editFormDynamic.value = { ext_attrs: { ...(company.value.ext_attrs || {}) } };
  editing.value = true;
}
function cancelEdit() { editing.value = false; }

async function saveEdit() {
  try {
    await editFormRef.value.validate();
  } catch { return; }
  if (dynamicFormRef.value) {
    const ok = await dynamicFormRef.value.validate();
    if (!ok) return;
  }
  saving.value = true;
  try {
    const dynamic = { ...(company.value.ext_attrs || {}), ...(editFormDynamic.value.ext_attrs || {}) };
    await api.put(`/companies/${companyId}`, {
      name: editForm.value.name,
      credit_code: editForm.value.credit_code,
      company_type: editForm.value.company_type,
      industry: editForm.value.industry,
      short_name: editForm.value.short_name,
      province: editForm.value.province,
      city: editForm.value.city,
      credit_level: editForm.value.credit_level,
      website: editForm.value.website,
      address: editForm.value.address,
      ext_attrs: dynamic,
    });
    ElMessage.success("保存成功");
    editing.value = false;
    loadCompany();
    loadDynamicFields();
  } catch { /* 拦截器处理 */ }
  finally { saving.value = false; }
}

async function enrichFree() {
  enrichingFree.value = true;
  try {
    const res: any = await api.post(`/companies/${companyId}/enrich-free`, null, { timeout: 180000 });
    if (res && (res.success || res.data)) {
      const updated: string[] = res?.data?.updated || [];
      const createdFields: string[] = res?.data?.created_fields || [];
      let detail = "免费补全成功";
      if (updated.length) {
        const labels: Record<string, string> = {
          "address": "地址",
          "ext:contact": "联系电话",
          "ext:contact_phone": "联系电话",
          "ext:contact_person": "联系人",
          // "ext:fax": "传真",
          // "ext:postal_code": "邮政编码",
          // "ext:office_hours": "办公时间",
          "ext:website": "官网",
          "ext:contact_email": "邮箱",
          "ext:legal_rep": "法定代表人",
          "ext:registered_capital": "注册资本",
          "ext:belong_org": "登记机关",
          "ext:business_scope": "经营范围",
          "ext:establish_date": "成立日期",
          "ext:oper_status": "经营状态",
          // "ext:reg_no": "注册号",
          "ext:extra_contacts": "多联系方式",
        };
        const shown = updated.map((k: string) => labels[k] || k);
        detail += `：${shown.join("、")}`;
        if (createdFields.length) {
          const cfLabels: Record<string, string> = { fax: "传真", postal_code: "邮政编码", office_hours: "办公时间" };
          detail += `（已自动新建字段：${createdFields.map((f: string) => cfLabels[f] || f).join("、")}）`;
        }
      } else if (res?.message) {
        detail = res.message;
      }
      ElMessage.success(detail);
      loadCompany();
      loadDynamicFields();
    } else {
      ElMessage.warning(res?.message || "免费补全未命中(公告库/政府采购网无该单位公开信息)");
    }
  } catch { /* 拦截器处理 */ }
  finally { enrichingFree.value = false; }
}

async function enrich() {
  enriching.value = true;
  try {
    const res: any = await api.post(`/companies/${companyId}/enrich`);
    if (res && (res.success || res.data)) {
      ElMessage.success("企查查数据补全成功");
      loadCompany();
      loadDynamicFields();
    } else {
      ElMessage.warning(res?.message || "未返回补全数据");
    }
  } catch { /* 拦截器处理 */ }
  finally { enriching.value = false; }
}

onMounted(() => {
  loadCompany();
  loadPersons();
  loadProjects();
  loadDynamicFields();
  loadCategories();
  loadStats();
  loadCompanyPath();
  loadRelData();
});
</script>

<style scoped>
.company-detail { max-width: 1400px; padding-bottom: 32px; }
.company-detail :deep(.el-page-header) {
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eef1f6;
}

/* ─── 顶部主信息卡 ─── */
.fgbs-header {
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
}
.fgbs-mark {
  background: #e8f1ff !important;
  border-color: #b9d4ff !important;
  color: #2979ff !important;
  font-weight: 500;
}
.fgbs-mark :deep(.el-icon) { margin-right: 3px; }
.fgbs-help { color: #c0c4cc; cursor: help; font-size: 15px; }
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
.fgbs-info-value.is-link {
  cursor: pointer;
  transition: color 0.15s;
}
.fgbs-info-value.is-link:hover {
  color: #2979ff;
  text-decoration: underline;
}
.fgbs-info-value .map-go {
  font-size: 12px;
  vertical-align: -1px;
  margin-left: 2px;
  color: #2979ff;
}

/* ─── AI分析能力横幅 ─── */
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
  border-color: #2979ff;
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(41, 121, 255, 0.2);
}
.ai-more {
  font-size: 13px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

/* ─── 主选项卡(商情分析报告 / fgbs大数据) ─── */
.fgbs-tabs {
  display: flex;
  gap: 4px;
  margin-top: 14px;
  background: #fff;
  border-radius: 6px 6px 0 0;
  border-bottom: 1px solid #ebeef5;
  padding: 0 16px;
}
.fgbs-tab {
  padding: 12px 18px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  margin-bottom: -1px;
  transition: all 0.18s ease;
}
.fgbs-tab:hover { color: #2979ff; }
.fgbs-tab.is-active {
  color: #fff;
  background: #2979ff;
  font-weight: 500;
}

.fgbs-panel {
  background: #fff;
  padding: 18px 22px 22px;
  border-radius: 0 0 6px 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

/* ─── 子选项卡(潜在商机 / 公司背景 / 公关路径) ─── */
.fgbs-subtabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 18px;
}
.fgbs-subtab {
  position: relative;
  padding: 8px 2px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  transition: color 0.18s ease;
}
.fgbs-subtab:hover { color: #2979ff; }
.fgbs-subtab.is-active {
  color: #2979ff;
  font-weight: 600;
}
.fgbs-subtab.is-active::after {
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: -1px;
  height: 2px;
  background: #2979ff;
  border-radius: 2px;
}

/* ─── 商机 / 背景 / 公关 三段共享 ─── */
.biz-section {
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  border-radius: 6px;
  padding: 18px 20px 22px;
  border: 1px solid #eef2f9;
}
.biz-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}
.biz-head-text { display: flex; align-items: baseline; gap: 10px; flex: 1; min-width: 0; }
.biz-key { font-size: 16px; font-weight: 600; color: #1f2d3d; flex-shrink: 0; }
.biz-desc { font-size: 13px; color: #909399; line-height: 1.5; }
.biz-foot {
  text-align: right;
  margin-bottom: 14px;
}
.biz-note { font-size: 12px; color: #c0c4cc; }

/* 商机统计卡 */
.biz-stat-cards { display: flex; flex-direction: column; gap: 10px; }
.biz-stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 16px 20px;
  transition: all 0.18s ease;
}
.biz-stat-card:hover {
  border-color: #b9d4ff;
  box-shadow: 0 2px 8px rgba(41, 121, 255, 0.08);
}
.biz-stat-icon {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, #2979ff 0%, #4f8aff 100%);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  font-size: 22px;
  flex-shrink: 0;
}
.biz-stat-info { flex: 1; min-width: 0; }
.biz-stat-title { font-size: 15px; font-weight: 600; color: #1f2d3d; margin-bottom: 4px; }
.biz-stat-meta {
  font-size: 13px;
  color: #606266;
  line-height: 1.7;
}
.biz-stat-strong {
  color: #2979ff;
  font-weight: 700;
  font-size: 14px;
  margin: 0 2px;
}
.biz-link {
  cursor: pointer;
  text-decoration: none;
  transition: color 0.18s ease, transform 0.18s ease;
  display: inline-block;
}
.biz-link:hover {
  color: #1d6fe0;
  transform: scale(1.12);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.biz-stat-divider {
  display: inline-block;
  margin: 0 8px;
  color: #dcdfe6;
}

/* ─── 抽屉列表 ─── */
.drawer-list { display: flex; flex-direction: column; gap: 10px; }
.drawer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.drawer-item:hover {
  border-color: #b9d4ff;
  box-shadow: 0 2px 8px rgba(41, 121, 255, 0.08);
  transform: translateX(2px);
}
.drawer-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.drawer-item-name { font-size: 14px; font-weight: 600; color: #1f2d3d; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.drawer-item-sub { font-size: 12.5px; color: #909399; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 公司背景 */
.bg-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px 24px;
  background: #fff;
  border-radius: 6px;
  padding: 16px 20px;
  border: 1px solid #e9edf6;
}
.bg-row { font-size: 13.5px; color: #303133; padding: 4px 0; }
.bg-label { color: #909399; margin-right: 6px; }
.bg-value { color: #303133; font-weight: 500; }

/* ─── 到公司的真实人脉路径链 ─── */
.pr-path {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.pr-path-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 10px;
}
.pr-path-title :deep(.el-icon) { color: #2979ff; }
.pr-path-chain {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 40px;
}
.pr-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 16px;
  border: 1px solid #e4e7ed;
  background: #fafcff;
  color: #4b5264;
  font-size: 13px;
  max-width: 180px;
  overflow: hidden;
  white-space: nowrap;
}
.pr-node :deep(.el-icon) { color: #909399; }
.pr-node.is-me { border-color: #f56c6c; background: #fff5f5; }
.pr-node.is-target { border-color: #2979ff; background: #ecf5ff; color: #1d63e0; font-weight: 600; }
.pr-node-avatar {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2979ff, #4f8aff);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  flex-shrink: 0;
}
.pr-node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pr-node-type { font-size: 11px; color: #909399; }
.pr-node-rel {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11.5px;
  color: #2979ff;
}
.pr-node-rel-text { max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-path-empty { color: #909399; font-size: 12.5px; }

/* ─── 情报关联区块 ─── */
.rel-block {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.rel-block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 10px;
}
.rel-block-title :deep(.el-icon) { color: #2979ff; }
.rel-block-title .el-tag { margin-left: auto; }
.rel-more {
  font-size: 12px;
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.rel-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
@media (max-width: 1100px) { .rel-grid { grid-template-columns: repeat(2, 1fr); } }
.rel-cell {
  background: #f8fbff;
  border: 1px solid #eef2f9;
  border-radius: 8px;
  padding: 10px 12px;
}
.rel-cell-title { font-size: 12.5px; font-weight: 600; color: #1f2d3d; margin-bottom: 8px; }
.rel-list { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto; }
.rel-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 12.5px; }
.rel-name { color: #2979ff; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rel-name.is-link:hover { text-decoration: underline; }
.rel-empty { color: #c0c4cc; font-size: 12px; padding: 4px 0; }



/* ─── fgbs 大数据视图(原有卡片表格) ─── */
.section-card { margin-bottom: 16px; border: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.section-header { display: flex; justify-content: space-between; align-items: center; }
.section-title { font-weight: 600; font-size: 16px; color: #303133; position: relative; padding-left: 12px; }
.section-title::before { content: ""; position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 4px; height: 16px; background: #2979ff; border-radius: 2px; }
.info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: #ebeef5; border: 1px solid #ebeef5; border-radius: 4px; overflow: hidden; }
.extra-contacts { margin-top: 16px; border: 1px dashed #d6e4ff; border-radius: 8px; padding: 12px 14px; background: #f8fbff; }
.extra-contacts-title { font-size: 13px; font-weight: 600; color: #1f2d3d; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.extra-sub { font-size: 11px; color: #c0c4cc; font-weight: normal; }
.extra-contact-item { display: flex; align-items: center; gap: 10px; padding: 5px 0; border-bottom: 1px dashed #eef2f9; font-size: 12.5px; }
.extra-contact-item:last-child { border-bottom: none; }
.extra-kind { width: 42px; text-align: center; }
.extra-value { flex: 1; color: #303133; }
.extra-primary-tag { color: #2979ff; font-size: 12px; font-weight: 600; }
.info-cell { background: #fff; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; }
.info-label { font-size: 13px; color: #909399; font-weight: 500; }
.info-value { font-size: 14px; color: #303133; line-height: 1.5; word-break: break-all; }
.info-note {
  display: inline-flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 12px;
  color: #b8860b;
  background: #fffbe6;
  border: 1px solid #f5d78e;
  border-radius: 4px;
  padding: 4px 8px;
  line-height: 1.4;
  cursor: help;
}
.info-note :deep(.el-icon) { font-size: 13px; margin-top: 1px; flex-shrink: 0; }
.bg-note {
  display: inline-flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 11.5px;
  color: #b8860b;
  margin-top: 3px;
  line-height: 1.4;
  cursor: help;
}
.bg-note :deep(.el-icon) { font-size: 12px; margin-top: 1px; flex-shrink: 0; }
.edit-form { padding-top: 8px; }

.clickable-table :deep(.el-table__row) { cursor: pointer; transition: background-color 0.2s ease; }
.clickable-table :deep(.el-table__row td.el-table__cell) { transition: background-color 0.2s ease; }
.clickable-table :deep(.el-table__row:hover > td.el-table__cell) { background-color: #eef5ff !important; }
.clickable-table :deep(.el-table__row:hover td.el-table__cell:first-child) { box-shadow: inset 3px 0 0 #2979ff; }
.link-name { color: #2979ff; font-weight: 500; transition: color 0.2s ease; }
.clickable-table :deep(.el-table__row:hover) .link-name { color: #1d6fe0; text-decoration: underline; text-underline-offset: 3px; }
.row-arrow { color: #c0c4cc; transition: transform 0.2s ease, color 0.2s ease; }
.clickable-table :deep(.el-table__row:hover) .row-arrow { color: #2979ff; transform: translateX(5px); }
.member-relation-link {
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
  border-color: #2979ff;
}

/* 响应式: 屏幕窄时三张信息卡改为单列 */
@media (max-width: 900px) {
  .fgbs-info-cards { grid-template-columns: 1fr; }
  .bg-grid { grid-template-columns: 1fr; }
}
</style>