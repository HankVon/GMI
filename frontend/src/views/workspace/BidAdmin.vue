<template>
  <div class="bid-admin-page">
    <!-- 统计卡 -->
    <div class="admin-stats" v-if="stats">
      <div class="stat-card"><span>标讯总数</span><b>{{ stats.total }}</b></div>
      <div class="stat-card"><span>已发布</span><b class="ok">{{ stats.by_status?.published ?? 0 }}</b></div>
      <div class="stat-card"><span>待审核</span><b class="warn">{{ stats.by_status?.pending ?? 0 }}</b></div>
      <div class="stat-card"><span>草稿</span><b>{{ stats.by_status?.draft ?? 0 }}</b></div>
      <div class="stat-card"><span>今日新增</span><b>{{ stats.today }}</b></div>
      <div class="stat-card"><span>近 7 天</span><b>{{ stats.last_7d }}</b></div>
    </div>

    <!-- 分布概览(类型/地区/行业, 可折叠) -->
    <el-card v-if="stats && hasDist" shadow="never" class="dist-card">
      <div class="dist-row" v-if="stats.type_dist?.length">
        <span class="dist-label">公告类型</span>
        <span v-for="(d, i) in stats.type_dist" :key="i" class="dist-chip">
          {{ d.name }}<b>{{ d.count }}</b>
        </span>
      </div>
      <div class="dist-row" v-if="stats.region_dist?.length">
        <span class="dist-label">地区分布</span>
        <span v-for="(d, i) in stats.region_dist" :key="i" class="dist-chip">
          {{ d.name }}<b>{{ d.count }}</b>
        </span>
      </div>
      <div class="dist-row" v-if="stats.industry_dist?.length">
        <span class="dist-label">行业分布</span>
        <span v-for="(d, i) in stats.industry_dist" :key="i" class="dist-chip">
          {{ d.name }}<b>{{ d.count }}</b>
        </span>
      </div>
    </el-card>

    <el-card shadow="never">
      <!-- 筛选栏 -->
      <div class="admin-filters">
        <el-input
          v-model="filters.keyword" placeholder="标题关键词" clearable style="width: 190px"
          @keyup.enter="load(1)" @clear="load(1)"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input
          v-model="filters.purchaser_keyword" placeholder="采购人" clearable style="width: 150px"
          @keyup.enter="load(1)" @clear="load(1)"
        />
        <el-input
          v-model="filters.notice_type" placeholder="公告类型" clearable style="width: 130px"
          @keyup.enter="load(1)" @clear="load(1)"
        />
        <el-select v-model="filters.category" placeholder="分类" clearable style="width: 120px" @change="load(1)">
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px" @change="load(1)">
          <el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" />
        </el-select>
        <el-select v-model="filters.matched" placeholder="单位匹配" clearable style="width: 130px" @change="load(1)">
          <el-option label="仅已匹配" :value="true" />
          <el-option label="仅未匹配" :value="false" />
        </el-select>
        <el-date-picker
          v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
          start-placeholder="发布开始" end-placeholder="发布结束" style="width: 250px"
          @change="load(1)"
        />
        <el-button type="primary" @click="load(1)">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <div class="admin-filters-right">
          <el-button type="primary" @click="openCreate">
            <el-icon style="margin-right:4px"><Plus /></el-icon>录入标讯
          </el-button>
          <el-button plain @click="openImport">
            <el-icon style="margin-right:4px"><Upload /></el-icon>线索导入
          </el-button>
          <el-button plain @click="openSubs">
            <el-icon style="margin-right:4px"><Bell /></el-icon>订阅管理
          </el-button>
          <el-button plain @click="openTagMgt">
            <el-icon style="margin-right:4px"><CollectionTag /></el-icon>标签管理
          </el-button>
          <el-button plain @click="openMatchMgt">
            <el-icon style="margin-right:4px"><Link /></el-icon>实体匹配
          </el-button>
          <el-button plain @click="openInteractions">
            <el-icon style="margin-right:4px"><User /></el-icon>互动明细
          </el-button>
          <el-button plain :loading="exporting" @click="doExport">
            <el-icon style="margin-right:4px"><Download /></el-icon>导出
          </el-button>
          <el-dropdown v-if="selectedIds.length" trigger="click" @command="(c:string)=>batchAction(c)">
            <el-button type="primary" plain>批量操作({{ selectedIds.length }})<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="submit">批量提交审核</el-dropdown-item>
                <el-dropdown-item command="publish">批量发布</el-dropdown-item>
                <el-dropdown-item command="offline">批量下架</el-dropdown-item>
                <el-dropdown-item divided command="delete">批量删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 表格 -->
      <el-table :data="items" stripe v-loading="loading" @selection-change="onSelectionChange" size="default">
        <el-table-column type="selection" width="42" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip>
          <template #default="{row}">
            <a class="row-title" @click="openDetail(row)">{{ row.title }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="notice_type" label="类型" width="100">
          <template #default="{row}">
            <el-tag v-if="row.notice_type" size="small" effect="plain">{{ row.notice_type }}</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="purchaser" label="招标单位" width="170" show-overflow-tooltip />
        <el-table-column prop="region" label="地区" width="140" show-overflow-tooltip />
        <el-table-column label="预算(万)" width="100">
          <template #default="{row}">
            <span v-if="row.budget_min != null || row.budget_max != null">
              {{ row.budget_min ?? '' }}{{ row.budget_min != null && row.budget_max != null ? '-' : '' }}{{ row.budget_max ?? '' }}
            </span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="published_at" label="发布时间" width="140" />
        <el-table-column label="状态" width="90">
          <template #default="{row}">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="互动" width="90">
          <template #default="{row}">
            <span class="muted">监{{ row.monitored ?? 0 }} / 收{{ row.collected ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="['draft','rejected'].includes(row.status)" link type="warning" size="small" @click="submitOne(row)">提交</el-button>
            <el-button v-if="row.status === 'pending'" link type="warning" size="small" @click="openReview(row)">审核</el-button>
            <el-button v-if="['draft','pending','approved'].includes(row.status)" link type="success" size="small" @click="publishOne(row)">发布</el-button>
            <el-button v-if="row.status === 'published'" link type="info" size="small" @click="offlineOne(row)">下架</el-button>
            <el-button v-if="row.status === 'offline'" link type="success" size="small" @click="restoreOne(row)">恢复</el-button>
            <el-dropdown trigger="click" @command="(c:string)=>onMore(c,row)">
              <el-button link type="info" size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="history">审核记录</el-dropdown-item>
                  <el-dropdown-item v-if="row.url" command="source">打开来源</el-dropdown-item>
                  <el-dropdown-item divided command="delete">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top:14px;justify-content:flex-end"
        v-model:current-page="page" :page-size="pageSize" :total="total"
        layout="total,prev,pager,next" @current-change="load"
      />
    </el-card>

    <!-- 录入/编辑弹窗 -->
    <el-dialog v-model="editVisible" :title="editingId ? '编辑标讯' : '录入标讯'" width="760px" top="6vh" destroy-on-close>
      <div class="form-grid" v-loading="editLoading">
        <div class="form-group">
          <span class="fg-label">标题 <em>*</em></span>
          <el-input v-model="form.title" maxlength="512" show-word-limit />
        </div>
        <div class="form-group">
          <span class="fg-label">原文链接</span>
          <el-input v-model="form.url" placeholder="https://" />
        </div>
        <div class="form-group">
          <span class="fg-label">公告类型 <em>*</em></span>
          <el-input v-model="form.notice_type" placeholder="招标公告/中标公告…" />
        </div>
        <div class="form-group">
          <span class="fg-label">分类</span>
          <el-select v-model="form.category" clearable filterable allow-create placeholder="工程/服务/货物" style="width:100%">
            <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div class="form-group">
          <span class="fg-label">行业</span>
          <el-input v-model="form.industry" placeholder="如：港航" />
        </div>
        <div class="form-group">
          <span class="fg-label">地区</span>
          <el-input v-model="form.region" placeholder="如：广东省-江门市-开平市" />
        </div>
        <div class="form-group">
          <span class="fg-label">招标单位</span>
          <el-input v-model="form.purchaser" placeholder="采购人/业主名称" />
        </div>
        <div class="form-group">
          <span class="fg-label">招标代理</span>
          <el-input v-model="form.agency" />
        </div>
        <div class="form-group">
          <span class="fg-label">发布时间</span>
          <el-date-picker v-model="form.published_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="选择时间" style="width:100%" />
        </div>
        <div class="form-group">
          <span class="fg-label">采购方式</span>
          <el-select v-model="form.purchase_way" clearable filterable allow-create placeholder="公开招标/邀请招标…" style="width:100%">
            <el-option v-for="w in ['公开招标','邀请招标','竞争性谈判','单一来源','询价']" :key="w" :label="w" :value="w" />
          </el-select>
        </div>
        <div class="form-group">
          <span class="fg-label">预算下限(万)</span>
          <el-input-number v-model="form.budget_min" :min="0" :precision="2" style="width:100%" />
        </div>
        <div class="form-group">
          <span class="fg-label">预算上限(万)</span>
          <el-input-number v-model="form.budget_max" :min="0" :precision="2" style="width:100%" />
        </div>
        <div class="form-group">
          <span class="fg-label">项目编号</span>
          <el-input v-model="form.project_code" />
        </div>
        <div class="form-group">
          <span class="fg-label">项目类型</span>
          <el-input v-model="form.project.type" placeholder="如：设计 施工" />
        </div>
        <div class="form-group">
          <span class="fg-label">建设工期</span>
          <el-input v-model="form.project.duration" placeholder="如：420天" />
        </div>
        <div class="form-group">
          <span class="fg-label">招标方式</span>
          <el-input v-model="form.project.method" />
        </div>
        <div class="form-group">
          <span class="fg-label">报名截止</span>
          <el-input v-model="form.project.registration_deadline" placeholder="YYYY-MM-DD HH:mm" />
        </div>
        <div class="form-group">
          <span class="fg-label">文件获取截止</span>
          <el-input v-model="form.project.document_deadline" />
        </div>
        <div class="form-group">
          <span class="fg-label">投标截止</span>
          <el-input v-model="form.project.bid_deadline" />
        </div>
        <div class="form-group">
          <span class="fg-label">开标时间</span>
          <el-input v-model="form.project.opening_time" />
        </div>
        <div class="form-group">
          <span class="fg-label">预算金额(文本)</span>
          <el-input v-model="form.finance.budget" placeholder="如：10495.93万" />
        </div>
        <div class="form-group">
          <span class="fg-label">资金来源</span>
          <el-input v-model="form.finance.source" />
        </div>
        <div class="form-group">
          <span class="fg-label">评标办法</span>
          <el-input v-model="form.evaluation.method" />
        </div>
        <div class="form-group full">
          <span class="fg-label">建设规模</span>
          <el-input v-model="form.project.scale" type="textarea" :rows="2" />
        </div>
        <div class="form-group full">
          <span class="fg-label">招标范围</span>
          <el-input v-model="form.project.scope" type="textarea" :rows="2" />
        </div>
        <div class="form-group full">
          <span class="fg-label">资格审查</span>
          <el-input v-model="form.requirements.qualification" type="textarea" :rows="2" />
        </div>
        <div class="form-group full">
          <span class="fg-label">联合体要求</span>
          <el-input v-model="form.requirements.consortium" type="textarea" :rows="2" />
        </div>
        <div class="form-group full">
          <span class="fg-label">关键词</span>
          <el-select v-model="form.keywords" multiple filterable allow-create default-first-option placeholder="回车添加" style="width:100%">
            <el-option v-for="k in form.keywords" :key="k" :label="k" :value="k" />
          </el-select>
        </div>
        <div class="form-group full">
          <span class="fg-label">标签</span>
          <el-select
            v-model="form.tag_ids" multiple filterable placeholder="选择运营标签(前台头部展示)" style="width:100%"
          >
            <el-option
              v-for="t in tagDefs" :key="t.id" :label="t.label" :value="t.id"
            >
              <span>{{ t.label }}</span>
              <span class="muted" style="margin-left:8px;font-size:12px">{{ t.kind }}</span>
            </el-option>
          </el-select>
        </div>
        <div class="form-group full">
          <span class="fg-label">公告正文</span>
          <el-input v-model="form.body" type="textarea" :rows="8" />
        </div>

        <!-- 招标进度时间线 -->
        <div class="form-group full">
          <span class="fg-label">招标进度事件</span>
          <div class="timeline-editor">
            <div v-for="(ev, i) in form.timeline" :key="i" class="tl-row">
              <el-input v-model="ev.label" placeholder="事件名(如：招标公告)" style="width:200px" />
              <el-input v-model="ev.date" placeholder="日期(YYYY-MM-DD)" style="width:180px" />
              <el-input v-model="ev.summary" placeholder="摘要(可选)" style="width:240px" />
              <el-button link type="danger" size="small" @click="removeTimeline(i)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button type="primary" plain size="small" @click="addTimeline">
              <el-icon style="margin-right:3px"><Plus /></el-icon>添加事件
            </el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">{{ editingId ? '保存' : '创建草稿' }}</el-button>
      </template>
    </el-dialog>

    <!-- 审核弹窗 -->
    <el-dialog v-model="reviewVisible" title="标讯审核" width="480px" destroy-on-close>
      <div class="review-head">
        <h3>{{ reviewTarget?.title }}</h3>
        <div class="muted">
          <span v-if="reviewTarget?.purchaser" style="margin-right:12px">招标单位：{{ reviewTarget.purchaser }}</span>
          <span v-if="reviewTarget?.region">{{ reviewTarget.region }}</span>
        </div>
      </div>
      <el-input
        v-model="reviewComment" type="textarea" :rows="3"
        placeholder="审核意见(驳回时必填，通过时可留空)"
      />
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="danger" plain :disabled="!reviewComment.trim()" :loading="reviewing" @click="doReview(false)">驳回</el-button>
        <el-button type="success" :loading="reviewing" @click="doReview(true)">通过</el-button>
      </template>
    </el-dialog>

    <!-- 审核记录 -->
    <el-dialog v-model="historyVisible" title="审核记录" width="620px" destroy-on-close>
      <el-timeline>
        <el-timeline-item
          v-for="(h, i) in historyList" :key="i" :timestamp="h.created_at"
          :type="historyTagType(h.action)"
        >
          <b>{{ actionLabel[h.action] || h.action }}</b>
          <span class="muted" style="margin-left:8px">操作人：{{ h.reviewer_name || '-' }}</span>
          <span v-if="h.from_status || h.to_status" class="muted" style="margin-left:8px">
            {{ statusLabels[h.from_status] || h.from_status }} → {{ statusLabels[h.to_status] || h.to_status }}
          </span>
          <div v-if="h.comment" class="history-comment">{{ h.comment }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!historyList.length" description="暂无操作记录" :image-size="60" />
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="标讯详情" size="620px">
      <div v-if="detail" class="detail-drawer">
        <div class="dd-title">{{ detail.title }}</div>
        <div class="dd-meta">
          <el-tag size="small" effect="plain">{{ detail.notice_type || '未分类' }}</el-tag>
          <el-tag v-if="detail.industry" size="small" type="primary" effect="plain">{{ detail.industry }}</el-tag>
          <el-tag :type="statusTagType(detail.status)" size="small">{{ statusLabels[detail.status] || detail.status }}</el-tag>
          <el-tag v-for="t in detailTags" :key="t.id" size="small" effect="dark">{{ t.label }}</el-tag>
        </div>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="招标单位">{{ detail.purchaser || '-' }}</el-descriptions-item>
          <el-descriptions-item label="招标代理">{{ detail.agency || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ detail.region || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ detail.published_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目编号">{{ detail.project_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购方式">{{ detail.purchase_way || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预算区间">
            {{ detail.budget_min ?? '-' }}{{ detail.budget_min != null && detail.budget_max != null ? ' ~ ' : '' }}{{ detail.budget_max ?? '' }} 万
          </el-descriptions-item>
          <el-descriptions-item label="预算(文本)">{{ detail.budget_display || '-' }}</el-descriptions-item>
          <el-descriptions-item label="报名截止">{{ detail.project?.registration_deadline || '-' }}</el-descriptions-item>
          <el-descriptions-item label="投标截止">{{ detail.project?.bid_deadline || '-' }}</el-descriptions-item>
          <el-descriptions-item label="开标时间">{{ detail.project?.opening_time || '-' }}</el-descriptions-item>
          <el-descriptions-item label="评标办法">{{ detail.evaluation?.method || '-' }}</el-descriptions-item>
          <el-descriptions-item label="建设工期">{{ detail.project?.duration || '-' }}</el-descriptions-item>
          <el-descriptions-item label="供应商数">{{ detail.suppliers?.length || 0 }} 家</el-descriptions-item>
          <el-descriptions-item :span="2" label="建设规模">{{ detail.project?.scale || '-' }}</el-descriptions-item>
          <el-descriptions-item :span="2" label="招标范围">{{ detail.project?.scope || '-' }}</el-descriptions-item>
          <el-descriptions-item :span="2" label="资金来源">{{ detail.finance?.source || '-' }}</el-descriptions-item>
          <el-descriptions-item :span="2" label="正文">
            <div class="dd-body">{{ detail.body || '暂无正文' }}</div>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 附件管理 -->
        <div class="dd-section">
          <div class="dd-section-head">
            <b>附件</b>
            <div>
              <input
                ref="fileInput" type="file" hidden
                @change="onFileSelected($event, detail.id)"
              />
              <el-button type="primary" plain size="small" @click="fileInput?.click()">
                <el-icon style="margin-right:3px"><Upload /></el-icon>上传附件
              </el-button>
            </div>
          </div>
          <el-table :data="attachments" size="small" v-loading="attLoading" empty-text="暂无附件">
            <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
            <el-table-column prop="file_size" label="大小" width="90">
              <template #default="{row}">{{ formatSize(row.file_size) }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="上传时间" width="150" />
            <el-table-column label="操作" width="110">
              <template #default="{row}">
                <el-button link type="primary" size="small" @click="downloadAtt(row, detail.id)">下载</el-button>
                <el-button link type="danger" size="small" @click="deleteAtt(row, detail.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-drawer>

    <!-- 订阅管理弹窗 -->
    <el-dialog v-model="subsVisible" title="订阅任务管理" width="780px" top="6vh" destroy-on-close>
      <el-table :data="subs" stripe v-loading="subsLoading" size="default">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="订阅名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column label="匹配数" width="90">
          <template #default="{row}"><b>{{ row.last_match_count ?? 0 }}</b></template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="上次运行" width="160">
          <template #default="{row}">
            <span v-if="row.last_run_at">{{ row.last_run_at }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{row}">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170">
          <template #default="{row}">
            <el-button link type="primary" size="small" :loading="subRunId === row.id" @click="runSub(row)">立即匹配</el-button>
            <el-button link :type="row.enabled ? 'warning' : 'success'" size="small" @click="toggleSub(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:12px;justify-content:flex-end"
        v-model:current-page="subsPage" :page-size="subsPageSize" :total="subsTotal"
        layout="total,prev,pager,next" @current-change="loadSubs"
      />
    </el-dialog>

    <!-- 互动明细弹窗 -->
    <el-dialog v-model="interVisible" title="用户互动明细(监控/收藏)" width="820px" top="6vh" destroy-on-close>
      <div class="match-head" style="margin-bottom:12px">
        <el-radio-group v-model="interAction" @change="loadInteractions">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="monitor">监控</el-radio-button>
          <el-radio-button value="collect">收藏</el-radio-button>
        </el-radio-group>
        <div class="match-head-right">
          <el-button size="small" @click="loadInteractions">刷新</el-button>
        </div>
      </div>
      <el-table :data="interItems" v-loading="interLoading" size="small" max-height="480">
        <el-table-column prop="bid_id" label="标讯ID" width="80" />
        <el-table-column prop="title" label="标讯标题" min-width="280" show-overflow-tooltip />
        <el-table-column prop="user_id" label="用户ID" width="80" />
        <el-table-column prop="published_at" label="发布时间" width="110" />
        <el-table-column label="动作" width="100">
          <template #default="{row}">
            <el-tag v-if="row.monitored" type="warning" size="small">监控</el-tag>
            <el-tag v-if="row.collected" type="success" size="small" style="margin-left:4px">收藏</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="140" />
      </el-table>
      <el-pagination
        style="margin-top:12px;justify-content:flex-end"
        v-model:current-page="interPage" :page-size="interPageSize" :total="interTotal"
        layout="total,prev,pager,next" @current-change="loadInteractions"
      />
    </el-dialog>

    <!-- 标签管理弹窗 -->
    <el-dialog v-model="tagMgtVisible" title="标签管理(前台头部展示)" width="720px" top="8vh" destroy-on-close>
      <div class="tag-mgt-head">
        <div>
          <el-input v-model="tagForm.label" placeholder="标签文本" style="width:180px" />
          <el-select v-model="tagForm.kind" style="width:130px;margin-left:8px">
            <el-option v-for="(k, label) in tagKinds" :key="k" :label="label" :value="k" />
          </el-select>
          <el-input v-model="tagForm.rule_keyword" placeholder="自动打标关键字(逗号分隔)" style="width:220px;margin-left:8px" />
          <el-button type="primary" style="margin-left:8px" @click="saveTagDef">新增</el-button>
        </div>
        <el-button :loading="tagAutoLoading" @click="autoApplyTags">
          <el-icon style="margin-right:3px"><MagicStick /></el-icon>按规则自动打标
        </el-button>
      </div>
      <el-table :data="tagDefs" size="small" v-loading="tagLoading" style="margin-top:12px">
        <el-table-column prop="label" label="标签" min-width="140" />
        <el-table-column prop="kind" label="样式" width="100" />
        <el-table-column prop="rule_keyword" label="规则关键字" min-width="200" show-overflow-tooltip />
        <el-table-column prop="sort_order" label="排序" width="70" />
        <el-table-column label="启用" width="80">
          <template #default="{row}">
            <el-switch :model-value="row.enabled" @change="(v:boolean)=>toggleTagDef(row,v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{row}">
            <el-button link type="danger" size="small" @click="deleteTagDef(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 实体匹配弹窗 -->
    <el-dialog v-model="matchMgtVisible" title="实体匹配(采购人/供应商 → 公司库)" width="860px" top="6vh" destroy-on-close>
      <div class="match-head">
        <el-input v-model="matchKeyword" placeholder="名称模糊搜索" clearable style="width:220px" @keyup.enter="loadUnmatched" @clear="loadUnmatched">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="loadUnmatched">查询</el-button>
        <div class="match-head-right">
          <el-button :loading="autoMatchLoading" @click="autoMatchAll">
            <el-icon style="margin-right:3px"><MagicStick /></el-icon>全量自动匹配
          </el-button>
        </div>
      </div>
      <el-table :data="unmatchedItems" v-loading="matchLoading" size="small" style="margin-top:12px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column label="采购人" min-width="170">
          <template #default="{row}">
            <div class="match-cell">
              <span>{{ row.purchaser || '-' }}</span>
              <el-tag v-if="row.purchaser_unmatched" type="danger" size="small">未匹配</el-tag>
              <el-button v-else link type="success" size="small">已匹配</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="未匹配供应商" min-width="160" show-overflow-tooltip>
          <template #default="{row}">
            <span v-if="row.unmatched_suppliers?.length">{{ row.unmatched_suppliers.join('、') }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="130" show-overflow-tooltip />
        <el-table-column label="操作" width="90">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="openBidMatch(row)">匹配</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 单条匹配弹窗 -->
    <el-dialog v-model="bidMatchVisible" title="确认匹配" width="520px" destroy-on-close>
      <div v-if="matchTarget" class="match-form">
        <div class="match-form-title">{{ matchTarget.title }}</div>
        <div class="match-field">
          <span class="mf-label">采购人</span>
          <el-select v-model="matchPurchaserId" filterable clearable placeholder="选择公司库单位(留空=不匹配)" style="width:100%">
            <el-option v-for="c in companyOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </div>
        <div v-if="matchTarget.unmatched_suppliers?.length" class="match-field">
          <span class="mf-label">供应商</span>
          <div v-for="(s, i) in matchSuppliers" :key="i" class="match-supplier">
            <el-input :model-value="s.name" disabled style="width:200px" />
            <el-select v-model="s.company_id" filterable clearable placeholder="选择公司" style="flex:1">
              <el-option v-for="c in companyOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="bidMatchVisible = false">取消</el-button>
        <el-button type="primary" :loading="matchSaving" @click="saveBidMatch">保存匹配</el-button>
      </template>
    </el-dialog>

    <!-- 线索导入弹窗 -->
    <el-dialog v-model="importVisible" title="从已接受线索导入标讯" width="480px" top="20vh" destroy-on-close>
      <el-alert
        type="info" :closable="false" show-icon
        title="将把 web_clue 中「已接受」状态的线索批量生成为标讯草稿(按标题去重)。"
        style="margin-bottom:12px"
      />
      <el-form label-width="80px">
        <el-form-item label="导入范围">
          <el-radio-group v-model="importScope">
            <el-radio value="all">全部已接受</el-radio>
            <el-radio value="source">指定来源</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="importScope === 'source'" label="来源ID">
          <el-input-number v-model="importSourceId" :min="1" style="width:100%" placeholder="web_source.id" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "BidAdmin" });
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Search, Plus, ArrowDown, Delete, Upload, Bell, CollectionTag, Link, MagicStick, User, Download,
} from "@element-plus/icons-vue";
import api from "@/api";

interface TimelineEvent { label: string; date: string; summary: string }

const loading = ref(false);
const saving = ref(false);
const reviewing = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const selectedIds = ref<number[]>([]);
const stats = ref<any>(null);
const dateRange = ref<[string, string] | null>(null);
const hasDist = computed(() =>
  !!(stats.value?.type_dist?.length || stats.value?.region_dist?.length || stats.value?.industry_dist?.length)
);

const statusLabels: Record<string, string> = {
  draft: "草稿", pending: "待审核", approved: "已通过",
  rejected: "已驳回", published: "已发布", offline: "已下架",
};
const actionLabel: Record<string, string> = {
  submit: "提交审核", approve: "审核通过", reject: "审核驳回",
  publish: "发布", offline: "下架", restore: "恢复上线", delete: "删除",
};
const categoryOptions = ["工程", "服务", "货物"];

const filters = reactive<Record<string, any>>({
  keyword: "", purchaser_keyword: "", notice_type: "",
  category: "", status: "", matched: null,
});

function statusTagType(s: string): string {
  return (
    { published: "success", pending: "warning", approved: "primary", rejected: "danger", offline: "info", draft: "info" }[s] || "info"
  );
}
function historyTagType(action: string): string {
  return (
    { approve: "success", publish: "success", restore: "success", reject: "danger", delete: "danger", offline: "warning", submit: "primary" }[action] || "primary"
  );
}

function buildParams() {
  const params: Record<string, any> = { page: page.value, page_size: pageSize.value };
  if (filters.keyword) params.keyword = filters.keyword;
  if (filters.purchaser_keyword) params.purchaser_keyword = filters.purchaser_keyword;
  if (filters.notice_type) params.notice_type = filters.notice_type;
  if (filters.category) params.category = filters.category;
  if (filters.status) params.status = filters.status;
  if (filters.matched !== null && filters.matched !== undefined && filters.matched !== "") params.matched = filters.matched;
  if (dateRange.value?.length === 2) {
    params.date_from = dateRange.value[0];
    params.date_to = dateRange.value[1];
  }
  return params;
}

async function load(p?: number) {
  if (p) page.value = p;
  loading.value = true;
  try {
    const res: any = await api.get("/admin/bids", { params: buildParams() });
    items.value = res?.items || [];
    total.value = res?.total || 0;
  } finally {
    loading.value = false;
  }
}
async function loadStats() {
  try {
    const res: any = await api.get("/admin/bids/stats");
    stats.value = res?.data || null;
  } catch { /* 无权限等忽略 */ }
}
function resetFilters() {
  Object.assign(filters, { keyword: "", purchaser_keyword: "", notice_type: "", category: "", status: "", matched: null });
  dateRange.value = null;
  load(1);
}
function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((r) => r.id);
}
async function batchAction(action: string) {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确认对 ${selectedIds.value.length} 条标讯执行「${actionLabel[action] || action}」?`, "批量操作", { type: "warning" });
  const res: any = await api.post("/admin/bids/batch", { ids: selectedIds.value, action });
  ElMessage.success(`已处理 ${res?.data?.affected ?? 0} 条`);
  load();
  loadStats();
}

// ── 表单 ──
const editVisible = ref(false);
const editLoading = ref(false);
const editingId = ref<number | null>(null);
const form = reactive<Record<string, any>>({
  title: "", url: "", notice_type: "", category: "", industry: "",
  region: "", purchaser: "", agency: "", published_at: "",
  purchase_way: "", budget_min: null, budget_max: null,
  project_code: "",
  project: { type: "", scale: "", scope: "", duration: "", method: "", registration_deadline: "", document_deadline: "", bid_deadline: "", opening_time: "" },
  finance: { budget: "", source: "" },
  evaluation: { method: "" },
  requirements: { qualification: "", consortium: "" },
  keywords: [], timeline: [] as TimelineEvent[], body: "", tag_ids: [] as number[],
});

function freshForm() {
  Object.assign(form, {
    title: "", url: "", notice_type: "", category: "", industry: "",
    region: "", purchaser: "", agency: "", published_at: "",
    purchase_way: "", budget_min: null, budget_max: null, project_code: "",
    project: { type: "", scale: "", scope: "", duration: "", method: "", registration_deadline: "", document_deadline: "", bid_deadline: "", opening_time: "" },
    finance: { budget: "", source: "" },
    evaluation: { method: "" },
    requirements: { qualification: "", consortium: "" },
    keywords: [], timeline: [] as TimelineEvent[], body: "", tag_ids: [] as number[],
  });
}
function addTimeline() {
  form.timeline.push({ label: "", date: "", summary: "" });
}
function removeTimeline(i: number) {
  form.timeline.splice(i, 1);
}
function openCreate() {
  editingId.value = null;
  freshForm();
  editVisible.value = true;
}
async function openEdit(row: any) {
  editingId.value = row.id;
  editVisible.value = true;
  editLoading.value = true;
  try {
    const res: any = await api.get(`/admin/bids/${row.id}`);
    const d = res?.data || {};
    freshForm();
    Object.assign(form, {
      title: d.title || "", url: d.url || "", notice_type: d.notice_type || "",
      category: d.category || "", industry: d.industry || "", region: d.region || "",
      purchaser: d.purchaser || "", agency: d.agency || "", published_at: d.published_at || "",
      purchase_way: d.purchase_way || "", budget_min: d.budget_min, budget_max: d.budget_max,
      project_code: d.project_code || "",
      project: { ...form.project, ...(d.project || {}) },
      finance: { ...form.finance, ...(d.finance || {}) },
      evaluation: { ...form.evaluation, ...(d.evaluation || {}) },
      requirements: { ...form.requirements, ...(d.requirements || {}) },
      keywords: d.keywords || [],
      timeline: d.timeline?.length ? d.timeline : [],
      body: d.body || "",
      tag_ids: [] as number[],
    });
    // 加载已打标签
    try {
      const tagRes: any = await api.get(`/admin/bids/${row.id}/tags`);
      form.tag_ids = (tagRes?.items || []).map((t: any) => t.id);
    } catch { /* 忽略 */ }
  } finally {
    editLoading.value = false;
  }
}
async function saveEdit() {
  if (!form.title.trim() || !form.notice_type.trim()) {
    ElMessage.warning("标题与公告类型为必填");
    return;
  }
  saving.value = true;
  try {
    const payload = {
      title: form.title, url: form.url || null, notice_type: form.notice_type,
      category: form.category || null, industry: form.industry || null,
      region: form.region || null, purchaser: form.purchaser || null,
      agency: form.agency || null, published_at: form.published_at || null,
      purchase_way: form.purchase_way || null, budget_min: form.budget_min,
      budget_max: form.budget_max, project: { ...form.project, code: form.project_code || null },
      finance: form.finance, evaluation: form.evaluation,
      requirements: form.requirements, keywords: form.keywords,
      timeline: form.timeline, body: form.body || null,
    };
    let bidId = editingId.value;
    if (bidId) {
      await api.put(`/admin/bids/${bidId}`, payload);
      ElMessage.success("已保存(已发布/下架标讯将回草稿重新审核)");
    } else {
      const createRes: any = await api.post("/admin/bids", payload);
      bidId = createRes?.data?.id;
      ElMessage.success("草稿已创建");
    }
    // 保存标签(编辑场景)
    if (bidId) {
      try {
        await api.post(`/admin/bids/${bidId}/tags`, { tag_ids: form.tag_ids });
      } catch { /* 标签保存失败不阻塞 */ }
    }
    editVisible.value = false;
    load();
    loadStats();
  } finally {
    saving.value = false;
  }
}

// ── 状态机操作 ──
async function submitOne(row: any) {
  await api.post(`/admin/bids/${row.id}/submit`);
  ElMessage.success("已提交审核");
  load();
}
function openReview(row: any) {
  reviewTarget.value = row;
  reviewComment.value = "";
  reviewVisible.value = true;
}
async function doReview(approve: boolean) {
  if (!approve && !reviewComment.value.trim()) {
    ElMessage.warning("驳回时请填写审核意见");
    return;
  }
  reviewing.value = true;
  try {
    await api.post(`/admin/bids/${reviewTarget.value.id}/review`, {
      approve, comment: reviewComment.value.trim() || null,
    });
    ElMessage.success(approve ? "审核通过" : "已驳回");
    reviewVisible.value = false;
    load();
  } finally {
    reviewing.value = false;
  }
}
async function publishOne(row: any) {
  await api.post(`/admin/bids/${row.id}/publish`);
  ElMessage.success("已发布，前台可见");
  load();
  loadStats();
}
async function offlineOne(row: any) {
  await ElMessageBox.confirm("确认下架该标讯?前台将不可见。", "下架确认", { type: "warning" });
  await api.post(`/admin/bids/${row.id}/offline`, { reason: "后台下架" });
  ElMessage.success("已下架");
  load();
  loadStats();
}
async function restoreOne(row: any) {
  await api.post(`/admin/bids/${row.id}/restore`);
  ElMessage.success("已恢复上线");
  load();
  loadStats();
}
async function onMore(command: string, row: any) {
  if (command === "delete") {
    await ElMessageBox.confirm(`确认删除「${row.title}」?删除后不可恢复。`, "删除确认", { type: "error" });
    await api.delete(`/admin/bids/${row.id}`);
    ElMessage.success("已删除");
    load();
    loadStats();
  } else if (command === "history") {
    openHistory(row.id);
  } else if (command === "source") {
    window.open(row.url, "_blank", "noopener");
  }
}

// ── 审核记录 / 详情 ──
const reviewVisible = ref(false);
const reviewTarget = ref<any>(null);
const reviewComment = ref("");
const historyVisible = ref(false);
const historyList = ref<any[]>([]);
async function openHistory(id: number) {
  const res: any = await api.get(`/admin/bids/${id}/review-history`);
  historyList.value = res?.items || [];
  historyVisible.value = true;
}
const detailVisible = ref(false);
const detail = ref<any>(null);
const detailTags = ref<any[]>([]);
const attachments = ref<any[]>([]);
const attLoading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

async function openDetail(row: any) {
  const res: any = await api.get(`/admin/bids/${row.id}`);
  detail.value = res?.data || null;
  detailVisible.value = true;
  // 标签 + 附件
  detailTags.value = [];
  attachments.value = [];
  try {
    const tagRes: any = await api.get(`/admin/bids/${row.id}/tags`);
    detailTags.value = tagRes?.items || [];
  } catch { /* 忽略 */ }
  loadAttachments(row.id);
}
async function loadAttachments(bidId: number) {
  attLoading.value = true;
  try {
    const res: any = await api.get(`/admin/bids/${bidId}/attachments`);
    attachments.value = res?.items || [];
  } finally {
    attLoading.value = false;
  }
}
function formatSize(bytes: number): string {
  if (!bytes) return "-";
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}
async function onFileSelected(event: Event, bidId: number) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res: any = await api.post(`/admin/bids/${bidId}/attachments`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    ElMessage.success(`已上传 ${res?.data?.file_name || ""}`);
    loadAttachments(bidId);
  } finally {
    input.value = "";
  }
}
async function downloadAtt(row: any, bidId: number) {
  // ★ P1-3: 受 Bearer 保护的下载接口不能用 window.open(会丢鉴权头→401), 改用带拦截器的 api + blob 下载
  try {
    const resp = await api.get(`/admin/bids/${bidId}/attachments/${row.id}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(resp.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = row.file_name || "attachment";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch { /* 拦截器统一处理 401/失败 */ }
}
async function deleteAtt(row: any, bidId: number) {
  await ElMessageBox.confirm(`确认删除附件「${row.file_name}」?`, "删除附件", { type: "warning" });
  await api.delete(`/admin/bids/${bidId}/attachments/${row.id}`);
  ElMessage.success("已删除");
  loadAttachments(bidId);
}

// ── 订阅管理 ──
const subsVisible = ref(false);
const subsLoading = ref(false);
const subs = ref<any[]>([]);
const subsTotal = ref(0);
const subsPage = ref(1);
const subsPageSize = ref(10);
const subRunId = ref<number | null>(null);

async function loadSubs() {
  subsLoading.value = true;
  try {
    const res: any = await api.get("/admin/bids/subscriptions", {
      params: { page: subsPage.value, page_size: subsPageSize.value },
    });
    subs.value = res?.items || [];
    subsTotal.value = res?.total || 0;
  } finally {
    subsLoading.value = false;
  }
}
function openSubs() {
  subsPage.value = 1;
  subsVisible.value = true;
  loadSubs();
}
async function toggleSub(row: any) {
  await api.post(`/admin/bids/subscriptions/${row.id}/toggle`);
  ElMessage.success(row.enabled ? "已停用" : "已启用");
  loadSubs();
}
async function runSub(row: any) {
  subRunId.value = row.id;
  try {
    const res: any = await api.post(`/admin/bids/subscriptions/${row.id}/run`);
    ElMessage.success(`匹配到 ${res?.data?.matched ?? 0} 条已发布标讯`);
    loadSubs();
  } finally {
    subRunId.value = null;
  }
}

// ── 线索导入 ──
const importVisible = ref(false);
const importing = ref(false);
const importScope = ref<'all' | 'source'>('all');
const importSourceId = ref<number | null>(null);

function openImport() {
  importScope.value = 'all';
  importSourceId.value = null;
  importVisible.value = true;
}
async function doImport() {
  if (importScope.value === 'source' && !importSourceId.value) {
    ElMessage.warning("请填写来源ID");
    return;
  }
  importing.value = true;
  try {
    const res: any = await api.post("/admin/bids/import-from-clues", {
      source_id: importScope.value === 'source' ? importSourceId.value : undefined,
    });
    ElMessage.success(`已导入 ${res?.data?.imported ?? 0} 条草稿，跳过 ${res?.data?.skipped ?? 0} 条重复`);
    importVisible.value = false;
    load();
    loadStats();
  } finally {
    importing.value = false;
  }
}

// ── 标签管理 ──
const tagMgtVisible = ref(false);
const tagLoading = ref(false);
const tagAutoLoading = ref(false);
const tagDefs = ref<any[]>([]);
const tagKinds: Record<string, string> = {
  status: "状态", category: "分类", warning: "提醒", danger: "紧急", plain: "普通",
};
const tagForm = reactive({ label: "", kind: "category", rule_keyword: "" });

async function loadTagDefs() {
  tagLoading.value = true;
  try {
    const res: any = await api.get("/admin/bid-tags/defs");
    tagDefs.value = res?.items || [];
  } finally {
    tagLoading.value = false;
  }
}
function openTagMgt() {
  tagForm.label = "";
  tagForm.kind = "category";
  tagForm.rule_keyword = "";
  tagMgtVisible.value = true;
  loadTagDefs();
}
async function saveTagDef() {
  if (!tagForm.label.trim()) {
    ElMessage.warning("请输入标签文本");
    return;
  }
  const res: any = await api.post("/admin/bid-tags/defs", { ...tagForm });
  ElMessage.success(`已创建标签「${res?.data?.label || tagForm.label}」`);
  tagForm.label = "";
  tagForm.rule_keyword = "";
  loadTagDefs();
}
async function toggleTagDef(row: any, enabled: boolean) {
  await api.put(`/admin/bid-tags/defs/${row.id}`, { enabled });
  row.enabled = enabled;
}
async function deleteTagDef(row: any) {
  await ElMessageBox.confirm(`确认删除标签「${row.label}」?`, "删除标签", { type: "warning" });
  await api.delete(`/admin/bid-tags/defs/${row.id}`);
  ElMessage.success("已删除");
  loadTagDefs();
}
async function autoApplyTags() {
  tagAutoLoading.value = true;
  try {
    const res: any = await api.post("/admin/bid-tags/auto-apply");
    ElMessage.success(`已按规则打标 ${res?.data?.applied ?? 0} 处`);
    loadTagDefs();
  } finally {
    tagAutoLoading.value = false;
  }
}

// ── 实体匹配 ──
const matchMgtVisible = ref(false);
const matchLoading = ref(false);
const autoMatchLoading = ref(false);
const matchKeyword = ref("");
const unmatchedItems = ref<any[]>([]);
const bidMatchVisible = ref(false);
const matchTarget = ref<any>(null);
const matchPurchaserId = ref<number | null>(null);
const matchSuppliers = ref<{ name: string; company_id: number | null }[]>([]);
const matchSaving = ref(false);
const companyOptions = ref<any[]>([]);

async function loadUnmatched() {
  matchLoading.value = true;
  try {
    const res: any = await api.get("/admin/bids/unmatched", {
      params: { keyword: matchKeyword.value || undefined, page_size: 100 },
    });
    unmatchedItems.value = res?.items || [];
  } finally {
    matchLoading.value = false;
  }
}
function openMatchMgt() {
  matchKeyword.value = "";
  matchMgtVisible.value = true;
  loadUnmatched();
}
async function autoMatchAll() {
  await ElMessageBox.confirm("将对所有未匹配采购人的标讯执行全量自动名称匹配(精确匹配公司库)，确认继续?", "全量自动匹配", { type: "warning" });
  autoMatchLoading.value = true;
  try {
    const res: any = await api.post("/admin/bids/match/auto", undefined, { timeout: 60000 });
    ElMessage.success(`扫描 ${res?.data?.scanned ?? 0} 条，自动匹配 ${res?.data?.matched ?? 0} 条`);
    loadUnmatched();
  } finally {
    autoMatchLoading.value = false;
  }
}
async function openBidMatch(row: any) {
  matchTarget.value = row;
  matchPurchaserId.value = row.purchaser_company_id || null;
  matchSuppliers.value = (row.unmatched_suppliers || []).map((name: string) => ({ name, company_id: null }));
  bidMatchVisible.value = true;
  if (!companyOptions.value.length) {
    try {
      const res: any = await api.get("/companies", { params: { page_size: 200 } });
      companyOptions.value = (res?.items || res?.data || []).map((c: any) => ({ id: c.id, name: c.name }));
    } catch { /* 忽略 */ }
  }
}
async function saveBidMatch() {
  if (!matchTarget.value) return;
  matchSaving.value = true;
  try {
    const suppliers = matchSuppliers.value
      .filter((s) => s.company_id)
      .map((s) => ({ supplier: s.name, company_id: s.company_id }));
    await api.post(`/admin/bids/${matchTarget.value.id}/match`, {
      purchaser_company_id: matchPurchaserId.value,
      suppliers,
    });
    ElMessage.success("匹配已保存");
    bidMatchVisible.value = false;
    loadUnmatched();
    load();
  } finally {
    matchSaving.value = false;
  }
}

// ── 互动明细 ──
const interVisible = ref(false);
const interLoading = ref(false);
const interItems = ref<any[]>([]);
const interTotal = ref(0);
const interPage = ref(1);
const interPageSize = ref(20);
const interAction = ref("");

async function loadInteractions() {
  interLoading.value = true;
  try {
    const res: any = await api.get("/admin/bids/interactions", {
      params: { action: interAction.value || undefined, page: interPage.value, page_size: interPageSize.value },
    });
    interItems.value = res?.items || [];
    interTotal.value = res?.total || 0;
  } finally {
    interLoading.value = false;
  }
}
function openInteractions() {
  interPage.value = 1;
  interAction.value = "";
  interVisible.value = true;
  loadInteractions();
}

// ── CSV 导出 ──
const exporting = ref(false);
async function doExport() {
  exporting.value = true;
  try {
    const params = buildParams();
    delete params.page;
    delete params.page_size;
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    const res: any = await api.get(`/admin/bids/export?${qs}`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res as Blob]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `bid_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    ElMessage.success("已导出 CSV");
  } catch {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

onMounted(() => {
  load(1);
  loadStats();
});
</script>

<style scoped>
.bid-admin-page { padding: 16px 0; }
.admin-stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e3eaf3;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-card span { color: #909399; font-size: 12px; }
.stat-card b { font-size: 22px; color: #1f2d3d; font-weight: 600; }
.stat-card b.ok { color: #20a04b; }
.stat-card b.warn { color: #c98a16; }

.admin-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
  align-items: center;
}

.dist-card {
  margin-bottom: 14px;
  border: 1px solid #e3eaf3;
  border-radius: 8px;
}
.dist-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}
.dist-row + .dist-row { border-top: 1px dashed #eef1f6; padding-top: 10px; }
.dist-label {
  flex: none;
  width: 60px;
  font-size: 12px;
  color: #909399;
}
.dist-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #5a6678;
}
.dist-chip b {
  color: #a51c30;
  font-weight: 600;
  font-size: 12px;
}
.admin-filters-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.muted { color: #909399; font-size: 12px; }
.row-title { color: #3b6fb6; cursor: pointer; text-decoration: none; }
.row-title:hover { text-decoration: underline; }

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px 16px;
}
.form-group { display: flex; flex-direction: column; gap: 5px; }
.form-group.full { grid-column: 1 / -1; }
.fg-label { font-size: 12.5px; color: #5a6678; font-weight: 500; }
.fg-label em { color: #c0392b; font-style: normal; }

.timeline-editor { display: flex; flex-direction: column; gap: 8px; }
.tl-row { display: flex; gap: 8px; align-items: center; }

.dd-section { margin-top: 16px; }
.dd-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.dd-section-head b { font-size: 14px; color: #1f2d3d; }

.tag-mgt-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.match-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.match-head-right { margin-left: auto; }
.match-cell { display: flex; align-items: center; gap: 8px; }
.match-cell span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.match-form-title {
  font-size: 14px; font-weight: 600; color: #1f2d3d;
  margin-bottom: 12px; line-height: 1.5;
}
.match-field { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
.mf-label { font-size: 12.5px; color: #5a6678; font-weight: 500; }
.match-supplier { display: flex; gap: 8px; margin-bottom: 6px; }

.review-head { margin-bottom: 12px; }
.review-head h3 { margin: 0 0 6px; font-size: 15px; color: #1f2d3d; }
.history-comment {
  margin-top: 4px; padding: 6px 10px;
  background: #f5f7fa; border-radius: 4px;
  font-size: 12.5px; color: #5a6678;
}

.detail-drawer { display: flex; flex-direction: column; gap: 14px; }
.dd-title { font-size: 17px; font-weight: 600; color: #1f2d3d; line-height: 1.5; }
.dd-meta { display: flex; gap: 6px; }
.dd-body {
  white-space: pre-wrap; max-height: 260px; overflow: auto;
  line-height: 1.8; font-size: 13px; color: #4a5566;
}

@media (max-width: 820px) {
  .admin-stats { grid-template-columns: repeat(3, 1fr); }
  .form-grid { grid-template-columns: 1fr; }
  .admin-filters-right { margin-left: 0; }
}
</style>
