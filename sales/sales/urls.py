from django.contrib import admin
from django.urls import path, include  # تأكد من إضافة include هنا

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- أضف هذا السطر ---
    # هذا يخبر Django باستخدام الملف الذي أنشأناه للتو
    path('', include('salesapp.urls')), # افترض أن اسم تطبيقك هو sales
]