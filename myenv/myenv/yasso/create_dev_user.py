import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yasso.settings')
django.setup()

from django.contrib.auth.models import User
from products.models import Profile

def create_dev_user():
    username = 'admin_dev'
    password = 'DevMaster@2026'
    
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_superuser(username=username, email='admin@flownest.core', password=password)
        # Check if profile exists, if not create as developer
        profile, created = Profile.objects.get_or_create(user=user)
        profile.role = 'developer'
        profile.company_name = 'FlowNest Core'
        profile.is_approved = True
        profile.save()
        print(f"✅ Success: User '{username}' created as a Developer Admin!")
    else:
        # Update existing user to be developer just in case
        user = User.objects.get(username=username)
        user.set_password(password)
        user.save()
        profile, created = Profile.objects.get_or_create(user=user)
        profile.role = 'developer'
        profile.company_name = 'FlowNest Core'
        profile.is_approved = True
        profile.save()
        print(f"ℹ️ User '{username}' already existed. Password and role have been reset.")

if __name__ == '__main__':
    create_dev_user()
