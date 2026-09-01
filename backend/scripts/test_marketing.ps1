# 营销智能体端到端验证脚本(开发用) — 用法: pwsh -File backend/scripts/test_marketing.ps1 [baseUrl]
param(
    [string]$BaseUrl = "http://127.0.0.1:8101"
)
$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")

function PostJson($path, $obj, $token) {
    $headers = @{ Authorization = "Bearer $token" }
    $body = $obj | ConvertTo-Json -Depth 8
    Invoke-RestMethod -Uri "$base$path" -Method Post -ContentType "application/json" -Headers $headers -Body $body -TimeoutSec 600
}
function GetApi($path, $token) {
    $headers = @{ Authorization = "Bearer $token" }
    Invoke-RestMethod -Uri "$base$path" -Method Get -Headers $headers -TimeoutSec 60
}
function PutApi($path, $obj, $token) {
    $headers = @{ Authorization = "Bearer $token" }
    $body = $obj | ConvertTo-Json -Depth 8
    Invoke-RestMethod -Uri "$base$path" -Method Put -ContentType "application/json" -Headers $headers -Body $body -TimeoutSec 60
}

Write-Host "== 登录 ==" -ForegroundColor Cyan
$login = Invoke-RestMethod -Uri "$base/api/v1/auth/login" -Method Post -ContentType "application/json" -Body (@{username="admin";password="admin123"} | ConvertTo-Json) -TimeoutSec 10
$token = $login.access_token
Write-Host "OK"

Write-Host "`n== 1. GEO 引擎/关键词种子 ==" -ForegroundColor Cyan
$engines = GetApi "/api/v1/geo/engines" $token
Write-Host "引擎数: $($engines.total): $((($engines.items | ForEach-Object { $_.name }) -join ', '))"
$kws = GetApi "/api/v1/geo/keywords" $token
Write-Host "关键词数: $($kws.total): $((($kws.items | ForEach-Object { $_.keyword }) -join ' | '))"

Write-Host "`n== 2. 配置品牌词 ==" -ForegroundColor Cyan
$cfg = PutApi "/api/v1/geo/config" @{ brand_names = @("四川某地质勘查有限公司", "中地生态"); industry_keywords = @("生态修复","地质勘查","地质灾害","矿山治理","水土保持") } $token
Write-Host "brand_names: $($cfg.brand_names -join ', ')"

Write-Host "`n== 3. 手动粘贴 AI 回答 → LLM 解析 ==" -ForegroundColor Cyan
$sampleAnswer = @"
关于"生态修复工程招标公司推荐"：
在四川地区开展生态修复工程的招标，通常由当地自然资源局或生态环境局作为采购人。具备相关资质的单位包括：
1. 四川某地质勘查有限公司 - 具备地质灾害治理工程勘查、设计、施工甲级资质，长期参与四川省矿山生态修复项目。
2. 中地生态 - 专注于水土保持与生态修复。
3. 四川省自然资源勘察设计集团有限公司 - 综合性勘察设计单位。
4. 成都理工大学工程技术研究院 - 高校背景研究机构。
建议业主在选择时重点关注单位资质等级、类似业绩与本地服务能力。相关招标信息可参考中国政府采购网(https://www.ccgp.gov.cn)与四川省公共资源交易网。
"@
$manual = PostJson "/api/v1/geo/mentions/manual" @{ keyword = "生态修复工程 招标 公司 推荐"; answer_text = $sampleAnswer } $token
$m = $manual.item
Write-Host "mention id=$($m.id) status=$($m.status)"
Write-Host "self_visible=$($m.self_visible) brand_hits=$($m.brand_hits | ConvertTo-Json -Compress -Depth 4)"
Write-Host "entities: $((($m.mentioned_entities | ForEach-Object { $_.name }) -join ', '))"
Write-Host "sources: $((($m.cited_sources | ForEach-Object { $_.title }) -join ', '))"
Write-Host "summary: $($m.summary)"

Write-Host "`n== 4. GEO 看板 ==" -ForegroundColor Cyan
$dash = GetApi "/api/v1/geo/dashboard?days=30" $token
Write-Host "mentions=$($dash.total_mentions) visible=$($dash.visible_count) ratio=$($dash.visible_ratio)"
Write-Host "engines: $($dash.engines | ConvertTo-Json -Compress -Depth 3)"
Write-Host "cited_top: $((($dash.cited_sources | Select-Object -First 3 | ForEach-Object { $_.domain }) -join ', '))"

Write-Host "`n== 5. 内容生成: 行业报告 ==" -ForegroundColor Cyan
$rep = PostJson "/api/v1/content/generate" @{ kind = "industry_report"; params = @{ days = 365; channel = "official_site" } } $token
Write-Host "industry_report id=$($rep.item.id) title=$($rep.item.title) status=$($rep.item.status) len=$($rep.item.content.Length)"
Write-Host "--- 报告开头 ---"
Write-Host ($rep.item.content.Substring(0, [Math]::Min(600, $rep.item.content.Length)))

Write-Host "`n== 6. 内容生成: FAQ ==" -ForegroundColor Cyan
$faq = PostJson "/api/v1/content/generate" @{ kind = "faq"; params = @{ topic = "生态修复项目招标" } } $token
Write-Host "faq id=$($faq.item.id) title=$($faq.item.title) len=$($faq.item.content.Length)"

Write-Host "`n== 7. 审核流转: submit → approve ==" -ForegroundColor Cyan
$sub = PostJson "/api/v1/content/assets/$($rep.item.id)/submit" @{} $token
Write-Host "submit: $($sub.status)"
$appr = PostJson "/api/v1/content/assets/$($rep.item.id)/approve" @{ published_url = "https://example.com/report/$($rep.item.id)" } $token
Write-Host "approve: $($appr.status) url=$($appr.published_url)"

Write-Host "`n== 8. 内容统计 ==" -ForegroundColor Cyan
$stats = GetApi "/api/v1/content/stats" $token
Write-Host "total=$($stats.total) by_status=$($stats.by_status | ConvertTo-Json -Compress) by_kind=$($stats.by_kind | ConvertTo-Json -Compress)"

Write-Host "`n== 9. 营销智能体闭环看板 ==" -ForegroundColor Cyan
$mk = GetApi "/api/v1/marketing/dashboard?days=30" $token
Write-Host "cycle: $($mk.cycle | ConvertTo-Json -Compress -Depth 4)"
Write-Host "opportunities: $($mk.opportunities.Count) 个"
Write-Host "topics: $($mk.topics.Count) 个"
if ($mk.opportunities.Count -gt 0) {
    Write-Host "TOP1 商机: [$($mk.opportunities[0].source)] $($mk.opportunities[0].title) score=$($mk.opportunities[0].score)"
    Write-Host "  理由: $($mk.opportunities[0].reason)"
}
if ($mk.topics.Count -gt 0) {
    Write-Host "TOP1 选题: [$($mk.topics[0].source)] $($mk.topics[0].title) priority=$($mk.topics[0].priority)"
}

Write-Host "`n== 10. 商机列表 ==" -ForegroundColor Cyan
$opp = GetApi '/api/v1/marketing/opportunities?days=60&limit=10' $token
Write-Host "商机总数: $($opp.total), 展示: $($opp.items.Count)"

Write-Host "`n✅ 端到端验证完成" -ForegroundColor Green
