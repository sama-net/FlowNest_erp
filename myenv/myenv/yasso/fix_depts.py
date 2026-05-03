"""
One-time script: clean duplicate departments on production.
Run with: railway run python myenv/myenv/yasso/fix_depts.py
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yasso.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from products.models import CustomDepartment
from collections import defaultdict

seen = defaultdict(list)
for d in CustomDepartment.objects.all().order_by('id'):
    key = (d.company_name.strip().lower(), d.name.strip().lower())
    seen[key].append(d.id)

deleted = 0
for key, ids in seen.items():
    if len(ids) > 1:
        to_delete = ids[1:]
        CustomDepartment.objects.filter(id__in=to_delete).delete()
        deleted += len(to_delete)
        print(f'Deleted {len(to_delete)} duplicates of dept "{key[1]}" for company "{key[0]}"')

print(f'\n✅ Total deleted: {deleted}')
print(f'✅ Remaining departments: {CustomDepartment.objects.count()}')
