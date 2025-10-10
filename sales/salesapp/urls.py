from django.urls import path
from . import views # استيراد ملف views.py من نفس التطبيق

# urlpatterns هي قائمة تحتوي على كل مسارات URL الخاصة بهذا التطبيق
urlpatterns = [
    # المسار الأول:
    # '' : يعني الصفحة الرئيسية (بدون أي شيء بعد اسم الموقع)
    # views.dashboard_view : الدالة التي سيتم تنفيذها عند زيارة هذا المسار
    # name='dashboard' : اسم مميز لهذا المسار لاستخدامه داخل القوالب لاحقاً
    path('', views.dashboard_view, name='dashboard'),
]
