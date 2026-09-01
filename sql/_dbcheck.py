import pymysql, json

conn = pymysql.connect(host='mysql', user='ssm_user', password='ssm_pass', db='ssm', charset='utf8mb4')
cur = conn.cursor()
out = {}
for col in ['company_type', 'industry', 'credit_level']:
    cur.execute("SELECT `%s`, COUNT(*) c FROM company WHERE `%s` LIKE '%%建筑%%' GROUP BY `%s` ORDER BY c DESC" % (col, col, col))
    out[col] = [list(r) for r in cur.fetchall()]
cur.execute("SELECT DISTINCT company_type FROM company LIMIT 80")
out['company_type_all'] = [r[0] for r in cur.fetchall()]
cur.execute("SELECT COUNT(*) FROM company")
out['total'] = cur.fetchone()[0]
with open('/tmp/dbcheck.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('DONE')
