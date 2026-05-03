web: python myenv/myenv/yasso/manage.py migrate && gunicorn --chdir myenv/myenv/yasso --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 120 --log-level info yasso.wsgi
