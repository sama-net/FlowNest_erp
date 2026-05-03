"""
WSGI config for yasso project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
# Force ChromaDB silence at the earliest possible moment
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yasso.settings')

application = get_wsgi_application()
