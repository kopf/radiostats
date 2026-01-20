from base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        #'OPTIONS': {"timeout": 20, "transaction_mode": "IMMEDIATE"} # transaction_mode in later versions of django
        'OPTIONS': {"timeout": 20}
    }
}
