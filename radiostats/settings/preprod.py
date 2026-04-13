from .base import *
from .auth import DB

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radiostats',
        'USER': DB['username'],
        'PASSWORD': DB['password'],
        'HOST': DB['host'],
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

ALLOWED_HOSTS = ['*']
