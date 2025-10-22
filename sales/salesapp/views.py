from django.shortcuts import render
from .models import Branch # 1. تم استيراد نموذج الفروع

def dashboard_view(request):
    """
    هذه الدالة مسؤولة عن عرض صفحة لوحة التحكم الرئيسية.
    وتقوم الآن بجلب قائمة بجميع الفروع من قاعدة البيانات
    لتمريرها إلى القائمة المنسدلة الخاصة بتغيير الفرع.
    """
    # 2. جلب كل الفروع من قاعدة البيانات
    all_branches = Branch.objects.all()
    
    # 3. تجهيز البيانات لإرسالها إلى القالب
    context = {
        'branches': all_branches
    }
    
    # 4. إرسال البيانات مع عرض ملف القالب
    return render(request, 'salesapp/dashboard.html', context)

def addreceipt_view(request):
    """
    هذه الدالة مسؤولة عن عرض صفحة لوحة التحكم الرئيسية.
    وتقوم الآن بجلب قائمة بجميع الفروع من قاعدة البيانات
    لتمريرها إلى القائمة المنسدلة الخاصة بتغيير الفرع.
    """
    # 2. جلب كل الفروع من قاعدة البيانات
    all_branches = Branch.objects.all()
    
    # 3. تجهيز البيانات لإرسالها إلى القالب
    context = {
        'branches': all_branches
    }
    
    # 4. إرسال البيانات مع عرض ملف القالب
    return render(request, 'salesapp/addreceipt.html', context)

# يمكنك إضافة باقي دوال العرض الخاصة بالتطبيق هنا لاحقاً
# مثلاً: add_receipt_view, view_receipts_view, etc.
