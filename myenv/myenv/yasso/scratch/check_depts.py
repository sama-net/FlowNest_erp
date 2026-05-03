import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yasso.settings')
django.setup()

from products.models import Profile, CustomDepartment

print("--- Departments ---")
for d in CustomDepartment.objects.all():
    print(f"ID: {d.id}, Name: {d.name}")

print("\n--- Manager Profiles ---")
for p in Profile.objects.filter(role='manager'):
    dept_name = p.department.name if p.department else "None"
    print(f"User: {p.user.username}, Role: {p.role}, Dept: {dept_name}")
