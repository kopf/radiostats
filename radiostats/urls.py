from django.contrib import admin
from django.urls import include, re_path

urlpatterns = [
    # Examples:
    # re_path(r'^$', 'radiostats.views.home', name='home'),
    # re_path(r'^blog/', include('blog.urls')),

    re_path(r'^admin/', admin.site.urls),
]
