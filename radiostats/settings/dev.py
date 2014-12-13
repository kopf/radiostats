from base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radiostats',
        'USER': 'radiostats',
        'PASSWORD': 'r4diostats',
        'HOST': '192.168.92.20',
        'OPTIONS': {
            'init_command': 'SET NAMES "utf8"'
        }
    }
}
