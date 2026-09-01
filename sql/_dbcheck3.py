import pymysql, json

conn = pymysql.connect(host='mysql', user='ssm_user', password='ssm_pass', db='ssm', charset='utf8mb4')
cur = conn.cursor()
cur.execute(
    "SELECT table_name, column_name, data_type FROM information_schema.columns "
    "WHERE table_schema='ssm' AND data_type IN ('varchar','text','char','json','longtext','mediumtext')"
)
cols = [(r[0], r[1], r[2]) for r in cur.fetchall()]
res = []
for t, c, dt in cols:
    try:
        if dt == 'json':
            cur.execute("SELECT COUNT(*) FROM `%s` WHERE JSON_SEARCH(`%s`,'all','建筑企业') IS NOT NULL" % (t, c))
        else:
            cur.execute("SELECT COUNT(*) FROM `%s` WHERE `%s` LIKE '%%建筑企业%%'" % (t, c))
        n = cur.fetchone()[0]
        if n > 0:
            res.append({'table': t, 'col': c, 'count': n})
    except Exception:
        pass
with open('/tmp/dbcheck3.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print('DONE3', len(res))
