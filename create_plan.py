import os
import db
import config

print('DB path:', config.DB_PATH)
print('DB exists:', os.path.exists(config.DB_PATH))
plan_id = db.create_subscription_level('over2.5', 100000, 0, '30 days subscription')
print('Created plan id:', plan_id)
print('Current subscription levels:')
for row in db.list_subscription_levels():
    print(row)
