# 导入样例与数据

用于**批量导入**功能测试与真实数据入库的样例文件。这些文件不是运行时依赖，仅在使用「导入」功能时作为输入。

---

## 一、文件清单

### A. 样例生成脚本（源头）

| 脚本 | 用途 | 运行 |
|---|---|---|
| `gen_sample.py` | 生成**项目**导入样例 Excel（→ `project_import_sample.xlsx`） | `python gen_sample.py` |
| `gen_person_sample.py` | 生成**人员**导入样例 Excel（→ `person_import_sample.xlsx`） | `python gen_person_sample.py` |

> 需要 `openpyxl`。改字段模板请改脚本，不要手改生成物。

### B. 生成的样例文件（可直接上传测试）

| 文件 | 用途 |
|---|---|
| `project_import_sample.xlsx` | 项目导入样例（由 `gen_sample.py` 生成） |
| `person_import_sample.xlsx` | 人员导入样例（由 `gen_person_sample.py` 生成） |

### C. 真实数据（已脱敏/真实业务数据）

| 文件 | 用途 |
|---|---|
| `real_project_info.xlsx` | 真实项目信息，由 `import_real_project.py` 导入 |
| `real_person_info.xlsx` | 真实人员信息 |
| `项目合同信息.xlsx` | 项目合同数据（真实业务导出） |
| `人员列表_system.xls` | 系统导出的人员列表（旧版 `.xls`） |
| `companies.xlsx` | 单位/企业名录 |

### D. 导入脚本

| 脚本 | 用途 |
|---|---|
| `import_real_project.py` | 把 `real_project_info.xlsx` 的真实项目导入系统：**读全字段 → 自动创建/复用公司、人员 → 建立「项目-单位」「项目-成员」关联 → 同步 Neo4j 图谱**。全部走后端 API，自动触发 MySQL 落库 + Neo4j 实时同步 + 动态字段校验 |

### E. 其它

| 文件 | 用途 |
|---|---|
| `image.png` | 截图（辅助说明用） |
| `~$real_person_info.xlsx`、`~$real_project_info.xlsx` | ⚠️ **Office 临时锁文件**（Excel 打开时生成），已在 `.gitignore` 中忽略，可随时删除 |

---

## 二、导入流程

1. 在前端进入对应列表页（项目 / 人员 / 单位），点「导入」；
2. 上传样例或真实数据 Excel；
3. 后端走 `dynamic_field_engine` 做**动态字段校验**，列头需与系统字段元数据匹配；
4. 导入为异步任务（`services/import_task.py`），可在页面查看进度与结果。

> 字段不匹配会导入失败。先用 `project_import_sample.xlsx` 试跑，确认列头格式后再上真实数据。

---

## 三、注意

- 真实数据文件含业务信息，**不要改动 `.gitignore` 把它们纳入版本库**；若确需入库请先确认脱敏。
- `import_real_project.py` 会写库并同步 Neo4j，**执行前建议先备份**（`scripts/backup.ps1`）。
