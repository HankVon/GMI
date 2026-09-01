import pymysql, json

conn = pymysql.connect(host='mysql', user='ssm_user', password='ssm_pass', db='ssm', charset='utf8mb4')
cur = conn.cursor()
out = {}

# 收集 ext_attrs 顶级 key 出现频次
cur.execute("SELECT ext_attrs FROM company WHERE ext_attrs IS NOT NULL LIMIT 400")
keys = {}
for (ea,) in cur.fetchall():
    if not ea:
        continue
    try:
        d = json.loads(ea) if isinstance(ea, str) else ea
        if isinstance(d, dict):
            for k in d:
                keys[k] = keys.get(k, 0) + 1
    except Exception:
        pass
out['ext_keys'] = keys

# 查找 ext_attrs 里 company_kind 键的值含"建筑"
try:
    cur.execute("SELECT ext_attrs->>'$.company_kind' AS ck, COUNT(*) c FROM company WHERE ext_attrs->>'$.company_kind' LIKE '%建筑%' GROUP BY ck ORDER BY c DESC")
    out['company_kind_in_ext'] = [list(r) for r in cur.fetchall()]
except Exception as e:
    out['company_kind_in_ext_err'] = str(e)

with open('/tmp/dbcheck2.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('DONE2')
