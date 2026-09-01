<!-- 公司/单位 360° 商情详情页 -->
<template>
  <div class="company-detail">
    <!-- 返回列表(与项目详情页一致): 前台数据中心返回对应列表 tab, 后台保持历史回退 -->
    <el-page-header @back="goBack" title="返回列表">
      <template #content>
        <span>{{ company.name || "加载中..." }}</span>
      </template>
    </el-page-header>

    <!-- 顶部主信息卡(白底 + 蓝色顶边, 名称 + 标记合作 + 打印) -->
    <div class="fgbs-header">
      <div class="fgbs-head-main">
        <h2 class="fgbs-title">{{ company.name || "加载中..." }}</h2>
        <el-tag v-if="!isPortal" type="primary" effect="plain" round size="small" class="fgbs-mark">
          <el-icon><Star /></el-icon><span>标记合作</span>
        </el-tag>
        <el-tooltip content="如何标记？" placement="top">
          <el-icon class="fgbs-help"><QuestionFilled /></el-icon>
        </el-tooltip>
        <div class="fgbs-head-spacer" />
        <el-button type="primary" size="small" class="fgbs-print" @click="onPrint">
          <el-icon><Printer /></el-icon><span>点击打印</span>
        </el-button>
        <FavoriteButton entity-type="company" :entity-id="companyId" />
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

      <!-- 工商速览(对标建设通业主详情头部) -->
      <div class="fgbs-ic-bar">
        <div class="ic-cell">
          <span class="ic-label">法定代表人</span>
          <span class="ic-value">{{ icData?.legal_rep || "-" }}</span>
        </div>
        <div class="ic-cell">
          <span class="ic-label">注册资本</span>
          <span class="ic-value">{{ icData?.registered_capital || "-" }}</span>
        </div>
        <div class="ic-cell">
          <span class="ic-label">成立日期</span>
          <span class="ic-value">{{ fmtDate(icData?.est_date) }}</span>
        </div>
        <div class="ic-cell">
          <span class="ic-label">统一信用代码</span>
          <span class="ic-value">{{ company.credit_code || "-" }}</span>
        </div>
        <div class="ic-cell">
          <span class="ic-label">行业</span>
          <span class="ic-value">{{ company.industry || "-" }}</span>
        </div>
        <div class="ic-cell">
          <span class="ic-label">企业类型</span>
          <span class="ic-value">{{ company.company_type || "-" }}</span>
        </div>
      </div>
    </div>

    <!-- 单位经营概况(对标业主详情页: 项目数据/维度概览) -->
    <div class="fgbs-ov-stats">
      <div class="ov-stat" @click="mainTab='fgbs'">
        <div class="ov-num">{{ projects.length }}</div>
        <div class="ov-label">参与项目</div>
      </div>
      <div class="ov-stat" @click="mainTab='fgbs'">
        <div class="ov-num">{{ persons.length }}</div>
        <div class="ov-label">关联人员</div>
      </div>
      <div class="ov-stat" @click="indTab='qual'; mainTab='industry'">
        <div class="ov-num">{{ qualifications.length }}</div>
        <div class="ov-label">资质台账</div>
      </div>
      <div class="ov-stat" @click="indTab='honor'; mainTab='industry'">
        <div class="ov-num">{{ honors.length }}</div>
        <div class="ov-label">荣誉</div>
      </div>
      <div class="ov-stat" @click="indTab='bidopen'; mainTab='industry'">
        <div class="ov-num">{{ bidOpenRecords.length }}</div>
        <div class="ov-label">开标记录</div>
      </div>
      <div class="ov-stat" @click="indTab='credit'; mainTab='industry'">
        <div class="ov-num">{{ creditRecords.length }}</div>
        <div class="ov-label">诚信记录</div>
      </div>
    </div>

    <!-- AI分析能力横幅: 标签条 + 更多分析入口 -->
    <AiBanner :chips="AI_CHIPS" @select-chip="openAiChat" @more="openAiChat()" />

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
      <div
        class="fgbs-tab"
        :class="{ 'is-active': mainTab === 'industry' }"
        @click="mainTab = 'industry'"
      >行业数据</div>
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
        <entity-kv-grid
          :items="baseInfoKvItems"
          :columns="1"
          variant="grid"
          fallback="-"
          class="bg-kv"
        />
      </div>

      <!-- 公关路径 -->
      <div v-show="subTab === 'pr'" class="biz-section">
        <div class="biz-head">
          <div class="biz-head-text">
            <span class="biz-key">公关路径</span>
            <span class="biz-desc">基于单位人员关系, 梳理最有效的触达与公关建议</span>
          </div>
          <el-button type="primary" size="small" @click="toggleGraph">
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

      <!-- 情报关联: 可争取意向 -->
      <div v-if="subTab === 'rel'" class="biz-section">
        <div class="biz-head">
          <div class="biz-head-text">
            <span class="biz-key">情报关联</span>
            <span class="biz-desc">围绕本单位业务 / 地域能力，系统定期匹配的可争取意向</span>
          </div>
          <el-button type="primary" size="small" @click="loadWatchedIntents">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>

        <!-- 0. 有望争取的意向（机会视角） -->
        <div class="rel-block intent-watch-block">
          <div class="rel-block-title">
            <el-icon><Aim /></el-icon>
            <span>有望争取的意向</span>
            <el-tag v-if="watchedIntents.length" size="small" type="danger" effect="dark">{{ watchedIntents.length }} 条</el-tag>
          </div>
          <div v-loading="watchedLoading" class="watched-list">
            <div v-if="!watchedIntents.length && !watchedLoading" class="watched-empty">
              暂无可争取的意向。系统会定期扫意向公告，匹配本单位业务/地域能力。
            </div>
            <div v-for="it in watchedIntents" :key="it.id" class="watched-item" @click="openIntentDetail(it.id)">
              <div class="watched-head">
                <el-tag size="small" :type="viaType(it.matched_via)" effect="plain">{{ viaLabel(it.matched_via) }}</el-tag>
                <span class="watched-title">{{ it.title }}</span>
                <span class="watched-date">{{ (it.published_at || '').slice(0, 10) }}</span>
              </div>
              <div class="watched-reason">
                <el-icon><InfoFilled /></el-icon>
                <span>{{ it.match_reason }}</span>
              </div>
            </div>
          </div>
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
                <div v-else-if="!isPortal" class="header-actions">
                  <el-button :loading="enrichingFree" size="small" @click="enrichFree">免费补全</el-button>
                  <el-button :loading="enriching" type="warning" size="small" @click="enrich">企查查补全</el-button>
                  <el-button type="primary" size="small" @click="startEdit">编辑</el-button>
                </div>
              </div>
            </template>

            <entity-kv-grid
              v-if="!editing"
              :items="displayKvItems"
              :columns="2"
              variant="grid"
              fallback="-"
            />

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
                <el-button v-else-if="!isPortal" link type="primary" size="small" @click="setPrimary(c)">设为主</el-button>
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

          <!-- 经营范围(对标业主详情页) -->
          <el-card v-if="businessScope" class="section-card" shadow="never">
            <template #header>
              <div class="section-header">
                <span class="section-title">经营范围</span>
                <span class="section-sub">工商登记的经营范围（可据此判断业务能力边界）</span>
              </div>
            </template>
            <div class="biz-scope-text">{{ businessScope }}</div>
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
              <el-table-column prop="evidence" label="证据来源" width="100">
                <template #default="{ row }">
                  <el-tag :type="evidenceTagType(row.evidence)" size="small">{{ row.evidence || '-' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column width="36" align="right">
                <template #default>
                  <el-icon class="row-arrow"><ArrowRight /></el-icon>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无参与/中标项目" :image-size="60" />
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

    <!-- 行业数据视图: 资质/荣誉/诚信/工商风险/开标记录(对标建设通分项查询) -->
    <div v-show="mainTab === 'industry'" class="fgbs-panel">
      <div class="fgbs-subtabs">
        <div class="fgbs-subtab" :class="{ 'is-active': indTab === 'qual' }" @click="indTab = 'qual'">资质台账</div>
        <div class="fgbs-subtab" :class="{ 'is-active': indTab === 'honor' }" @click="indTab = 'honor'">荣誉</div>
        <div class="fgbs-subtab" :class="{ 'is-active': indTab === 'credit' }" @click="indTab = 'credit'">诚信记录</div>
        <div class="fgbs-subtab" :class="{ 'is-active': indTab === 'ic' }" @click="indTab = 'ic'">工商与风险</div>
        <div class="fgbs-subtab" :class="{ 'is-active': indTab === 'bidopen' }" @click="indTab = 'bidopen'">开标记录</div>
      </div>

      <!-- 资质台账 -->
      <div v-show="indTab === 'qual'" class="ind-section">
        <div class="ind-head">
          <div class="ind-head-text">
            <span class="ind-key">资质台账</span>
            <span class="ind-desc">单位资质等级、发证机关与有效期，含失效预警</span>
          </div>
          <el-select v-model="qualFilter.category" size="small" clearable placeholder="按大类筛选" style="width: 180px" @change="loadQualifications">
            <el-option v-for="c in qualCategories" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div class="ind-stat-cards" v-if="Object.keys(qualStatusCount).length">
          <div class="ind-stat-card" v-for="(cnt, st) in qualStatusCount" :key="st">
            <div class="ind-stat-num">{{ cnt }}</div>
            <div class="ind-stat-label">{{ statusZh(st) }}</div>
          </div>
        </div>
        <el-table v-if="qualifications.length" :data="qualifications" size="small" border>
          <el-table-column prop="category" label="资质大类" width="110" />
          <el-table-column prop="professional" label="专业" min-width="130" />
          <el-table-column prop="level" label="等级" width="90" />
          <el-table-column prop="cert_no" label="证书编号" width="140" />
          <el-table-column prop="issue_org" label="发证机关" min-width="130" />
          <el-table-column label="有效期" width="180">
            <template #default="{ row }">{{ fmtDate(row.valid_from) }} ~ {{ fmtDate(row.valid_to) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="indStatusTagType(row.status)" size="small">{{ statusZh(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="来源" min-width="110">
            <template #default="{ row }">
              <a v-if="row.source_url" :href="row.source_url" target="_blank" class="ind-src">{{ row.source }}</a>
              <span v-else class="ind-src-plain">{{ row.source }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无资质台账" :image-size="60" />
      </div>

      <!-- 荣誉 -->
      <div v-show="indTab === 'honor'" class="ind-section">
        <div class="ind-head">
          <div class="ind-head-text">
            <span class="ind-key">荣誉</span>
            <span class="ind-desc">获奖情况（奖项/等级/授予机关/日期）</span>
          </div>
        </div>
        <el-table v-if="honors.length" :data="honors" size="small" border>
          <el-table-column prop="title" label="荣誉标题" min-width="220" />
          <el-table-column prop="level" label="等级" width="100" />
          <el-table-column prop="org" label="授予机关" min-width="150" />
          <el-table-column label="获奖日期" width="110">
            <template #default="{ row }">{{ fmtDate(row.honored_at) }}</template>
          </el-table-column>
          <el-table-column label="来源" min-width="110">
            <template #default="{ row }">
              <a v-if="row.source_url" :href="row.source_url" target="_blank" class="ind-src">{{ row.source }}</a>
              <span v-else class="ind-src-plain">{{ row.source }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无荣誉记录" :image-size="60" />
      </div>

      <!-- 诚信记录 -->
      <div v-show="indTab === 'credit'" class="ind-section">
        <div class="ind-head">
          <div class="ind-head-text">
            <span class="ind-key">诚信记录</span>
            <span class="ind-desc">不良行为 / 双随机公示，来源为官方公开渠道</span>
          </div>
        </div>
        <el-table v-if="creditRecords.length" :data="creditRecords" size="small" border>
          <el-table-column prop="title" label="记录标题" min-width="240" />
          <el-table-column prop="org" label="公示机关" min-width="150" />
          <el-table-column label="公示日期" width="110">
            <template #default="{ row }">{{ fmtDate(row.published_at) }}</template>
          </el-table-column>
          <el-table-column label="来源" min-width="110">
            <template #default="{ row }">
              <a v-if="row.source_url" :href="row.source_url" target="_blank" class="ind-src">{{ row.source }}</a>
              <span v-else class="ind-src-plain">{{ row.source }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无诚信记录" :image-size="60" />
      </div>

      <!-- 工商与风险 -->
      <div v-show="indTab === 'ic'" class="ind-section">
        <div class="ind-head">
          <div class="ind-head-text">
            <span class="ind-key">工商与风险</span>
            <span class="ind-desc">工商基本信息、股东/投资/分支结构与司法风险</span>
          </div>
        </div>
        <template v-if="icData">
          <div class="ind-grid">
            <div class="ind-row"><span class="ind-label">法定代表人:</span><span class="ind-value">{{ icData.legal_rep || "-" }}</span></div>
            <div class="ind-row"><span class="ind-label">注册资本:</span><span class="ind-value">{{ icData.registered_capital || "-" }}</span></div>
            <div class="ind-row"><span class="ind-label">成立日期:</span><span class="ind-value">{{ fmtDate(icData.est_date) }}</span></div>
          </div>
          <div class="ind-blocks">
            <div v-if="icData.shareholders?.length" class="ind-block">
              <div class="ind-block-title">股东</div>
              <div v-for="(s, i) in icData.shareholders" :key="i" class="ind-item">{{ s.name }}（{{ s.ratio || "-" }}）</div>
            </div>
            <div v-if="icData.investments?.length" class="ind-block">
              <div class="ind-block-title">对外投资</div>
              <div v-for="(s, i) in icData.investments" :key="i" class="ind-item">{{ s.name }}（{{ s.ratio || "-" }}）</div>
            </div>
            <div v-if="icData.branches?.length" class="ind-block">
              <div class="ind-block-title">分支机构</div>
              <div v-for="(s, i) in icData.branches" :key="i" class="ind-item">{{ s.name }}</div>
            </div>
          </div>
        </template>
        <el-empty v-else description="暂无工商信息（可通过企查查补全）" :image-size="60" />
        <el-divider content-position="left">司法与经营风险</el-divider>
        <el-table v-if="legalRisks.length" :data="legalRisks" size="small" border>
          <el-table-column label="类型" width="100">
            <template #default="{ row }">{{ riskTypeZh(row.risk_type) }}</template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="200" />
          <el-table-column prop="court" label="法院/机关" min-width="130" />
          <el-table-column label="涉案金额" width="110">
            <template #default="{ row }">{{ row.amount != null ? Number(row.amount).toLocaleString() : "-" }}</template>
          </el-table-column>
          <el-table-column label="日期" width="110">
            <template #default="{ row }">{{ fmtDate(row.published_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无司法风险记录" :image-size="60" />
      </div>

      <!-- 开标记录 -->
      <div v-show="indTab === 'bidopen'" class="ind-section">
        <div class="ind-head">
          <div class="ind-head-text">
            <span class="ind-key">开标记录</span>
            <span class="ind-desc">本单位的投标场次（报价/下浮率/开标时间）</span>
          </div>
        </div>
        <el-table v-if="bidOpenRecords.length" :data="bidOpenRecords" size="small" border>
          <el-table-column prop="notice_title" label="公告标题" min-width="220">
            <template #default="{ row }">
              <a v-if="row.notice_url" :href="row.notice_url" target="_blank" class="ind-src">{{ row.notice_title || "-" }}</a>
              <span v-else>{{ row.notice_title || "-" }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="role" label="角色" width="90" />
          <el-table-column label="报价" width="120">
            <template #default="{ row }">{{ row.amount != null ? Number(row.amount).toLocaleString() : "-" }}</template>
          </el-table-column>
          <el-table-column label="下浮率" width="100">
            <template #default="{ row }">{{ row.discount_rate != null ? (Number(row.discount_rate) * 100).toFixed(2) + "%" : "-" }}</template>
          </el-table-column>
          <el-table-column label="开标时间" width="120">
            <template #default="{ row }">{{ fmtDate(row.opened_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无开标记录" :image-size="60" />
      </div>
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
defineOptions({ name: "CompanyDetail" });
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Star, QuestionFilled, Printer, Document, Location, Phone,
  MagicStick, ArrowRight, Briefcase, Refresh, Trophy, Share, Connection,
  Right, OfficeBuilding, FolderOpened, InfoFilled, Aim,
} from "@element-plus/icons-vue";
import dayjs from "dayjs";
import api from "@/api";
import FavoriteButton from "@/components/FavoriteButton.vue";
import DynamicForm from "@/components/DynamicForm.vue";
import AiAnalystChat from "@/components/AiAnalystChat.vue";
import PersonCard from "@/components/PersonCard.vue";
import ProjectCard from "@/components/ProjectCard.vue";
import CompanyGraph from "@/components/CompanyGraph.vue";
import AiBanner from "@/components/detail/AiBanner.vue";
import EntityKvGrid from "@/components/detail/EntityKvGrid.vue";
import { useNavBase } from "@/utils/navBase";
import { usePortalMode } from "@/utils/portalMode";

const route = useRoute();
const router = useRouter();
const { navTo } = useNavBase();
const { isPortal } = usePortalMode();
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
const mainTab = ref<"analysis" | "fgbs" | "industry">("analysis");
const subTab = ref<"biz" | "bg" | "pr" | "rel">("biz");

/* ─────────── 行业数据(资质/荣誉/诚信/工商风险/开标) ─────────── */
const indTab = ref<"qual" | "honor" | "credit" | "ic" | "bidopen">("qual");
const qualFilter = ref<{ category: string }>({ category: "" });
const qualifications = ref<any[]>([]);
const qualCategories = ref<string[]>([]);
const qualStatusCount = ref<Record<string, number>>({});
const honors = ref<any[]>([]);
const creditRecords = ref<any[]>([]);
const icData = ref<any>(null);
const legalRisks = ref<any[]>([]);
const bidOpenRecords = ref<any[]>([]);

function fmtDate(v: any): string {
  if (!v) return "-";
  return dayjs(v).format("YYYY-MM-DD");
}
function statusZh(s: string): string {
  return { active: "有效", expiring: "临期", expired: "已失效" }[s] || s || "-";
}
function indStatusTagType(s: string): string {
  return { active: "success", expiring: "warning", expired: "danger" }[s] || "info";
}
function riskTypeZh(t: string): string {
  const m: Record<string, string> = {
    lawsuit: "诉讼", judgment: "裁判文书", executed: "被执行", penalty: "行政处罚",
    abnormal: "经营异常", pledge: "股权出质", announcement: "法院公告",
  };
  return m[t] || t;
}

async function loadQualifications() {
  try {
    const res: any = await api.get(`/companies/${companyId}/qualifications`, {
      params: { category: qualFilter.value.category || undefined, page_size: 100 },
    });
    const d = res?.data || {};
    qualifications.value = d.items || [];
    qualStatusCount.value = d.status_count || {};
    qualCategories.value = d.categories || [];
  } catch { /* ignore */ }
}
async function loadHonors() {
  try {
    const res: any = await api.get(`/companies/${companyId}/honors`, { params: { page_size: 100 } });
    honors.value = res?.data?.items || [];
  } catch { /* ignore */ }
}
async function loadCreditRecords() {
  try {
    const res: any = await api.get(`/companies/${companyId}/credit-records`, { params: { page_size: 100 } });
    creditRecords.value = res?.data?.items || [];
  } catch { /* ignore */ }
}
async function loadIc() {
  try {
    const res: any = await api.get(`/companies/${companyId}/ic`);
    icData.value = res?.data || null;
  } catch { icData.value = null; }
}
async function loadLegalRisks() {
  try {
    const res: any = await api.get(`/companies/${companyId}/legal-risks`, { params: { page_size: 100 } });
    legalRisks.value = res?.data?.items || [];
  } catch { /* ignore */ }
}
async function loadBidOpenRecords() {
  try {
    const res: any = await api.get(`/companies/${companyId}/bid-open-records`, { params: { page_size: 100 } });
    bidOpenRecords.value = res?.data?.items || [];
  } catch { /* ignore */ }
}

/* ─────────── 情报关联: 可争取意向（定期扫意向公告，匹配本单位业务/地域能力） ─────────── */
const watchedIntents = ref<any[]>([]);
const watchedLoading = ref(false);
async function loadWatchedIntents() {
  watchedLoading.value = true;
  try {
    const res: any = await api.get(`/intent/related-by-company/${companyId}`);
    watchedIntents.value = res?.items || [];
  } catch { watchedIntents.value = []; }
  finally { watchedLoading.value = false; }
}
function openIntentDetail(id: number) {
  // 跳转意向信息页 + 打开详情（与 IntentList 详情弹窗交互保持一致）
  router.push({ path: navTo("/intents"), query: { open: String(id) } });
}
function viaLabel(v: string): string {
  if (v === "tender_match") return "业务匹配";
  if (v === "project_unit") return "业主相关";
  if (v === "publisher") return "采购主体";
  return v || "关联";
}
function viaType(v: string): string {
  if (v === "tender_match") return "warning";
  if (v === "project_unit") return "danger";
  if (v === "publisher") return "primary";
  return "info";
}

/** 返回: 优先回上一级浏览历史(用户刚看过的那一页), 无历史(如直接刷新)时兜底回数据中心列表 */
function goBack() {
  const back = window.history.state?.back;
  if (back) {
    router.back();
  } else {
    router.push("/site/data-center/companies");
  }
}

/** 跳转其他单位详情 */
function goCompany(id?: number | null) {
  if (!id) return;
  router.push(navTo(`/companies/${id}`));
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
  owner: "业主", constructor: "施工", partner: "合作伙伴", builder: "建设单位",
  design: "设计", designer: "设计", supervisor: "监理", construction: "施工",
  investor: "投资方", client: "业主", contractor: "施工", supplier: "供应商", other: "其他",
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
function evidenceTagType(e: string): string {
  return { "中标项目": "warning", "参与+中标": "danger", "成员项目": "info", "参与项目": "primary" }[e] || "info";
}
function goProject(id: number) { router.push(navTo(`/projects/${id}`)); }
function goPerson(id: number) { router.push(navTo(`/persons/${id}`)); }
function viewNetwork(id: number) { router.push(navTo(`/network/${id}`)); }

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
const businessScope = computed(() => {
  const ext = company.value.ext_attrs || {};
  return ext.business_scope || ext.scope || "";
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

/** displayItems → EntityKvGrid 契约(展示态与标讯详情页共用同一组件与样式) */
const displayKvItems = computed(() =>
  (displayItems.value as any[]).map((item) => ({
    label: item.label,
    field: { displayText: item.value ?? '', isGated: false },
    note: item.note || null,
  })),
);

/** baseInfoItems → EntityKvGrid 契约(商机面板基础信息) */
const baseInfoKvItems = computed(() =>
  (baseInfoItems.value as any[]).map((item) => ({
    label: item.label,
    field: { displayText: item.value ?? '', isGated: false },
    note: item.note || null,
  })),
);

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
    if (res && res.success === true) {
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
    if (res && res.success === true) {
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
  // 前台数据中心: 用户可能未关联本人节点, 自动调用人脉路径会 400 弹错, 改为按需加载
  if (!isPortal.value) loadCompanyPath();
  loadWatchedIntents();
  // 行业数据(资质/荣誉/诚信/工商风险/开标)
  loadQualifications();
  loadHonors();
  loadCreditRecords();
  loadIc();
  loadLegalRisks();
  loadBidOpenRecords();
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

/* 工商速览(对标建设通业主详情头部) */
.fgbs-ic-bar {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
  background: #f7f9fc;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px 16px;
}
.ic-cell { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.ic-label { font-size: 12px; color: #8a919f; }
.ic-value {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 单位经营概况统计条(对标业主详情页: 项目数据/维度概览) */
.fgbs-ov-stats {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}
.ov-stat {
  background: #fff;
  border: 1px solid #e9edf6;
  border-radius: 8px;
  padding: 12px 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.ov-stat:hover { border-color: #2979ff; box-shadow: 0 4px 12px rgba(41, 121, 255, 0.1); }
.ov-num { font-size: 22px; font-weight: 700; color: #2979ff; line-height: 1.2; }
.ov-label { margin-top: 4px; font-size: 12px; color: #8a919f; }

/* 经营范围 */
.biz-scope-text {
  font-size: 13px;
  line-height: 2;
  color: #303133;
  background: #f7f9fc;
  border-radius: 6px;
  padding: 14px 16px;
  max-height: 260px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

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

/* ─── 统一关系网络视图 ─── */
.rel-overview { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.overview-chip {
  display: flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 10px;
  background: #f4f8ff; border: 1px solid #e3ecff; cursor: pointer; transition: all .15s;
}
.overview-chip:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(41, 121, 255, 0.12); }
.overview-chip.is-empty { background: #fafbfc; border-color: #eef0f4; }
.overview-chip.is-empty .chip-num { color: #c0c4cc; }
.chip-num { font-size: 18px; font-weight: 700; color: #2979ff; min-width: 20px; text-align: center; }
.chip-label { font-size: 12px; color: #4b5264; }
.rel-group { margin-bottom: 20px; }
.rel-group-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.rel-group-title { font-size: 14px; font-weight: 600; color: #303133; }
.rel-group-desc { font-size: 12px; color: #a3adc0; }
.rel-empty-line { color: #c0c4cc; font-size: 12px; padding: 10px 0; border-bottom: 1px dashed #eef0f4; }
.rel-item-lg { padding: 8px 12px; margin-bottom: 6px; border-radius: 8px; transition: background .15s; }
.rel-item-lg:hover { background: #f8fafc; }
.rel-evidence { color: #909399; font-size: 12px; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rel-conf { color: #909399; font-size: 12px; }

/* ─── 被意向盯上（人脉网络反向标注） ─── */
.intent-watch-block {
  background: #fff;
  border: 1px solid #eef1f8;
  border-left: 3px solid #f56c6c;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(30, 60, 114, 0.04);
  padding: 14px 16px;
  margin-bottom: 16px;
}
.watched-list { display: flex; flex-direction: column; gap: 8px; }
.watched-empty { color: #a3adc0; font-size: 12px; padding: 8px 0; }
.watched-item {
  background: #ffffff; border: 1px solid #eef1f8; border-radius: 8px; padding: 10px 12px;
  cursor: pointer; transition: box-shadow .15s, border-color .15s;
}
.watched-item:hover { box-shadow: 0 3px 10px rgba(30, 60, 114, 0.07); border-color: #ffd9c2; }
.watched-head { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.watched-title { color: #1f2d3d; font-weight: 500; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.watched-date { color: #a3adc0; font-size: 12px; flex-shrink: 0; }
.watched-reason { display: flex; align-items: center; gap: 4px; color: #f56c6c; font-size: 12px; margin-top: 6px; }
.watched-reason .el-icon { font-size: 12px; }

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

/* ─────────── 行业数据(资质/荣誉/诚信/工商风险/开标) ─────────── */
.ind-section {
  padding-top: 14px;
}
.ind-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.ind-head-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.ind-key {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
}
.ind-desc {
  font-size: 12px;
  color: #8a919f;
}
.ind-stat-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.ind-stat-card {
  flex: 1;
  max-width: 150px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 14px;
  text-align: center;
}
.ind-stat-num {
  font-size: 22px;
  font-weight: 700;
  color: #2979ff;
}
.ind-stat-label {
  margin-top: 2px;
  font-size: 12px;
  color: #606266;
}
.ind-src {
  color: #2979ff;
  text-decoration: none;
  font-size: 12px;
}
.ind-src:hover { text-decoration: underline; }
.ind-src-plain {
  font-size: 12px;
  color: #8a919f;
}
.ind-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px 24px;
  padding: 12px 0;
}
.ind-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.ind-label {
  color: #8a919f;
  font-size: 13px;
  flex-shrink: 0;
}
.ind-value {
  color: #1f2329;
  font-size: 13px;
  font-weight: 500;
}
.ind-blocks {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 8px;
}
.ind-block {
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 12px;
}
.ind-block-title {
  font-size: 12px;
  color: #606266;
  font-weight: 600;
  margin-bottom: 6px;
}
.ind-item {
  font-size: 13px;
  color: #1f2329;
  line-height: 1.8;
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
.biz-key {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
  flex-shrink: 0;
  padding-left: 10px;
  border-left: 3px solid #2979ff;
  line-height: 1.4;
}
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

/* 公司背景: 基础信息已改用公共组件 EntityKvGrid(见 .bg-kv) */
.bg-kv { background: #fff; border-radius: 6px; padding: 16px 20px; border: 1px solid #e9edf6; }

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
.extra-contacts { margin-top: 16px; border: 1px dashed #d6e4ff; border-radius: 8px; padding: 12px 14px; background: #f8fbff; }
.extra-contacts-title { font-size: 13px; font-weight: 600; color: #1f2d3d; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.extra-sub { font-size: 11px; color: #c0c4cc; font-weight: normal; }
.extra-contact-item { display: flex; align-items: center; gap: 10px; padding: 5px 0; border-bottom: 1px dashed #eef2f9; font-size: 12.5px; }
.extra-contact-item:last-child { border-bottom: none; }
.extra-kind { width: 42px; text-align: center; }
.extra-value { flex: 1; color: #303133; }
.extra-primary-tag { color: #2979ff; font-size: 12px; font-weight: 600; }
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
  .fgbs-ov-stats { grid-template-columns: repeat(3, 1fr); }
  .bg-grid { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .fgbs-ov-stats { grid-template-columns: repeat(2, 1fr); }
}

/* ============================================================
   视觉提质 · 勃艮第红机构风(参考女娲人工智能学院官网)
   统一残留蓝色 hardcode → 红系, 章节标题改为杂志化竖条
   ============================================================ */
.company-detail {
  background: var(--ssm-bg);
  border-radius: 12px;
  padding: 4px 0 8px;
}

/* 顶部主信息卡 + 红色顶边 */
.fgbs-header {
  background: var(--ssm-card-bg);
  border: 1px solid var(--ssm-border);
  border-top: 3px solid var(--ssm-primary);
  border-radius: var(--ssm-radius);
  box-shadow: var(--ssm-shadow);
  padding: 20px 22px 18px;
  margin-bottom: 16px;
}
.fgbs-title { font-size: 24px; font-weight: 700; letter-spacing: 0.01em; color: var(--ssm-text-main); }
.fgbs-info-card {
  background: var(--ssm-bg);
  border: 1px solid var(--ssm-border);
  border-radius: var(--ssm-radius);
  padding: 14px 16px;
}
.fgbs-info-icon { color: var(--ssm-primary); }
.fgbs-info-label { color: var(--ssm-text-secondary); font-size: 12.5px; }
.fgbs-info-value { color: var(--ssm-text-main); font-size: 15px; font-weight: 600; }

/* 经营概况统计条 → 红系 */
.fgbs-ov-stats { gap: 10px; }
.ov-stat {
  background: var(--ssm-card-bg);
  border: 1px solid var(--ssm-border);
  border-radius: var(--ssm-radius);
  padding: 14px 8px;
}
.ov-stat:hover { border-color: var(--ssm-primary); box-shadow: var(--ssm-shadow-hover); }
.ov-num { color: var(--ssm-primary); font-family: Georgia, serif; }
.ov-label { color: var(--ssm-text-secondary); }
.biz-scope-text {
  background: var(--ssm-bg);
  border: 1px dashed var(--ssm-hairline);
  color: var(--ssm-text-main);
}

/* 章节标题: 红色竖条 + 深色字(杂志化) */
.section-title { color: var(--ssm-text-main) !important; }
.section-title::before { background: var(--ssm-primary) !important; width: 4px; height: 18px; border-radius: 2px; }

/* fgbs section-card 提质 */
.section-card {
  border: 1px solid var(--ssm-border) !important;
  border-radius: var(--ssm-radius) !important;
  box-shadow: var(--ssm-shadow) !important;
  overflow: hidden;
}
.section-card :deep(.el-card__header) {
  background: #fcfbfa;
  border-bottom: 1px solid var(--ssm-hairline);
  padding: 14px 18px;
}
.section-card :deep(.el-card__body) { padding: 16px 18px; }

/* 链接/表头悬停 → 红系 */
.link-name { color: var(--ssm-primary) !important; }
.clickable-table :deep(.el-table__row:hover > td.el-table__cell) { background-color: var(--ssm-primary-soft) !important; }
.clickable-table :deep(.el-table__row:hover td.el-table__cell:first-child) { box-shadow: inset 3px 0 0 var(--ssm-primary) !important; }
.clickable-table :deep(.el-table__row:hover) .link-name { color: var(--ssm-primary-dark) !important; text-decoration: underline; text-underline-offset: 3px; }
.row-arrow { color: #c8c2bc !important; }
.clickable-table :deep(.el-table__row:hover) .row-arrow { color: var(--ssm-primary) !important; transform: translateX(5px); }
.rel-name { color: var(--ssm-primary) !important; }
.member-relation-link {
  border: 1px solid var(--ssm-primary-soft) !important;
  background: var(--ssm-primary-soft) !important;
  color: var(--ssm-primary) !important;
}
.member-relation-link:hover { background: var(--ssm-primary) !important; color: #fff !important; border-color: var(--ssm-primary) !important; }

/* 有望争取的意向 卡片提质 */
.intent-watch-block {
  background: var(--ssm-card-bg) !important;
  border: 1px solid var(--ssm-border) !important;
  border-left: 3px solid var(--ssm-primary) !important;
  border-radius: var(--ssm-radius);
  box-shadow: var(--ssm-shadow);
  padding: 16px 18px;
  margin-bottom: 16px;
}
.rel-block-title { font-size: 16px; font-weight: 700; color: var(--ssm-text-main); display: flex; align-items: center; gap: 8px; }
.rel-block-title .el-icon { color: var(--ssm-primary); }
.watched-item {
  border: 1px solid var(--ssm-border);
  border-radius: var(--ssm-radius);
  padding: 12px 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.watched-item:hover {
  border-color: var(--ssm-primary-light);
  box-shadow: var(--ssm-shadow-hover);
  transform: translateY(-2px);
}
.watched-title { color: var(--ssm-text-main); font-weight: 600; }

/* 单元格提质 */
.extra-contacts { border: 1px dashed var(--ssm-primary-soft) !important; background: var(--ssm-primary-soft) !important; }
.extra-primary-tag { color: var(--ssm-primary) !important; }
.extra-contact-item { border-bottom: 1px dashed var(--ssm-hairline) !important; }
</style>