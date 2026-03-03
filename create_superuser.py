import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','mysite.settings')
import django
django.setup()
from django.contrib.auth import get_user_model

User = get_user_model()
username = 'Kane'
email = 'kaneworrall92@gmail.com'
password = 'Ducksintrees4321'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print('SUPERUSER_CREATED')
else:
    print('SUPERUSER_EXISTS')
