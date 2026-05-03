import re

with open('requirements.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

cleaned = []
ignored_packages = ['pywin32', 'pypiwin32', 'comtypes', 'pyreadline3', 'pipwin', 'playsound']

for line in lines:
    line = line.strip()
    if not line:
        continue
    # Remove local build suffixes like +cu118 or +2026.1.4
    line = re.sub(r'\+[a-zA-Z0-9\.]+', '', line)
    
    # Ignore windows-specific packages
    package_name = line.split('==')[0].lower()
    if package_name in ignored_packages:
        continue
        
    cleaned.append(line)

# Add essential gunicorn and CPU torch index
if 'gunicorn' not in [l.split('==')[0].lower() for l in cleaned]:
    cleaned.append('gunicorn')

with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(cleaned) + '\n')
