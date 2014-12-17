from base import *
from auth import DB

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radiostats',
        'USER': DB['username'],
        'PASSWORD': DB['password'],
        'HOST': DB['host'],
        'OPTIONS': {
            'init_command': 'SET NAMES "utf8"'
        }
    }
}
