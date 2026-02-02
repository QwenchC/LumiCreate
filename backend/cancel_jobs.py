import sqlite3

conn = sqlite3.connect('lumicreate.db')
cursor = conn.cursor()

# 把卡住的 GENERATING_AUDIO 状态重置为 IMAGES_READY
cursor.execute("UPDATE segments SET status = 'IMAGES_READY' WHERE status = 'GENERATING_AUDIO'")
print(f'已重置 {cursor.rowcount} 个 GENERATING_AUDIO -> IMAGES_READY')

conn.commit()

cursor.execute('SELECT DISTINCT status FROM jobs')
print('Jobs 状态值:', cursor.fetchall())

cursor.execute('SELECT DISTINCT status FROM segments')
print('Segments 状态值:', cursor.fetchall())

conn.close()

