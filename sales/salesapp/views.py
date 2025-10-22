from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, F
from django.utils import timezone
import json
import re # (جديد) لاستخدام split في كود الأقساط
from datetime import date # (جديد) للتعامل مع التواريخ
from dateutil.relativedelta import relativedelta # (جديد) لحساب الشهور التالية

from .models import Branch, Salesperson, InventoryItem, Receipt, SaleItem, InstallmentPayment

# =======================================
# (Middleware) فلتر الفرع الشامل
# =======================================
def branch_required(view_func):
    # ... الكود كما هو ...
    def _wrapped_view(request, *args, **kwargs):
        if 'selected_branch_id' not in request.session: return redirect('select_branch')
        try: request.branch = Branch.objects.get(id=request.session['selected_branch_id'])
        except Branch.DoesNotExist: request.session.flush(); return redirect('select_branch')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# =======================================
# اختيار الفرع (شاشة البداية)
# =======================================
def select_branch(request):
    # ... الكود كما هو ...
    request.session.flush() 
    branches = Branch.objects.all()
    return render(request, 'salesapp/select_branch.html', {'branches': branches})

def set_branch(request, branch_id):
     # ... الكود كما هو ...
    branch = get_object_or_404(Branch, id=branch_id)
    request.session['selected_branch_id'] = branch.id
    request.session['selected_branch_name'] = branch.name
    return redirect('add_receipt') 

# =======================================
# قسم الإعدادات (لا تغيير هنا)
# =======================================
def manage_branches(request): # ... كما هو ...
    error_message = None 
    if request.method == 'POST':
        branch_name = request.POST.get('branch_name')
        if branch_name:
            try: Branch.objects.create(name=branch_name); return redirect('manage_branches')
            except IntegrityError: error_message = f"خطأ: الاسم '{branch_name}' موجود مسبقاً."
    branches = Branch.objects.all()
    context = {'branches': branches, 'page_title': 'إدارة الفروع', 'error_message': error_message}
    return render(request, 'salesapp/manage_branches.html', context)

@branch_required
def manage_salespersons(request): # ... كما هو ...
    current_branch = request.branch 
    error_message = None 
    if request.method == 'POST':
        person_name = request.POST.get('person_name')
        if person_name:
            try: Salesperson.objects.create(name=person_name, branch=current_branch); return redirect('manage_salespersons')
            except IntegrityError: error_message = f"خطأ: الاسم '{person_name}' موجود مسبقاً في هذا الفرع."
    all_salespersons = Salesperson.objects.filter(branch=current_branch)
    context = {'salespersons': all_salespersons, 'page_title': 'إدارة الموظفين', 'error_message': error_message}
    return render(request, 'salesapp/manage_salespersons.html', context)

@branch_required
def manage_products(request): # ... كما هو ...
     current_branch = request.branch
     error_message = None
     if request.method == 'POST':
        product_name = request.POST.get('product_name')
        quantity = request.POST.get('quantity', 0)
        purchase_price = request.POST.get('purchase_price', 0)
        commission_amount = request.POST.get('commission_amount', 0) 
        if product_name:
            try:
                InventoryItem.objects.create( name=product_name, branch=current_branch, quantity=quantity, purchase_price=purchase_price, salesperson_commission_amount=commission_amount); return redirect('manage_products')
            except IntegrityError: error_message = f"خطأ: اسم المنتج '{product_name}' موجود مسبقاً في هذا الفرع."
     all_products = InventoryItem.objects.filter(branch=current_branch)
     context = {'products': all_products, 'page_title': 'إدارة المنتجات', 'error_message': error_message}
     return render(request, 'salesapp/manage_products.html', context)
    
@branch_required 
def delete_branch(request, pk): # ... كما هو ...
    branch = get_object_or_404(Branch, pk=pk)
    error_message = None 
    try:
        branch.delete()
        if request.session.get('selected_branch_id') == pk: request.session.flush(); return redirect('select_branch')
        return redirect('manage_branches') 
    except ProtectedError: error_message = f"خطأ: لا يمكن حذف الفرع '{branch.name}' لأنه مرتبط ببيانات أخرى."
    branches = Branch.objects.all()
    context = {'branches': branches, 'page_title': 'إدارة الفروع', 'error_message': error_message}
    return render(request, 'salesapp/manage_branches.html', context)

@branch_required
def delete_salesperson(request, pk): # ... كما هو ...
    person = get_object_or_404(Salesperson, pk=pk, branch=request.branch)
    error_message = None 
    try: person.delete(); return redirect('manage_salespersons') 
    except ProtectedError: error_message = f"خطأ: لا يمكن حذف الموظف '{person.name}' لأنه مرتبط ببيانات أخرى."
    all_salespersons = Salesperson.objects.filter(branch=request.branch)
    context = {'salespersons': all_salespersons, 'page_title': 'إدارة الموظفين', 'error_message': error_message}
    return render(request, 'salesapp/manage_salespersons.html', context)

@branch_required
def delete_product(request, pk): # ... كما هو ...
    product = get_object_or_404(InventoryItem, pk=pk, branch=request.branch)
    error_message = None 
    try: product.delete(); return redirect('manage_products') 
    except ProtectedError: error_message = f"خطأ: لا يمكن حذف المنتج '{product.name}' لأنه مرتبط ببيانات أخرى."
    all_products = InventoryItem.objects.filter(branch=request.branch)
    context = {'products': all_products, 'page_title': 'إدارة المنتجات', 'error_message': error_message}
    return render(request, 'salesapp/manage_products.html', context)
    
@branch_required
def manage_inventory_movements(request): # ... كما هو ...
    current_branch = request.branch
    error_message = None
    success_message = None 
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity_str = request.POST.get('quantity')
        movement_type = request.POST.get('movement_type') 
        if not product_id or not quantity_str or not movement_type: error_message = "خطأ: يرجى ملء كل الحقول."
        else:
            try:
                quantity = int(quantity_str)
                if quantity <= 0: error_message = "خطأ: الكمية يجب أن تكون رقماً موجباً."
                else:
                    product = get_object_or_404(InventoryItem, pk=product_id, branch=current_branch)
                    if movement_type == 'add': product.quantity += quantity; success_message = f"تمت إضافة {quantity} قطعة."
                    elif movement_type == 'return':
                        if product.quantity >= quantity: product.quantity -= quantity; success_message = f"تم إرجاع {quantity} قطعة."
                        else: error_message = f"خطأ: الكمية المتاحة {product.quantity} فقط."
                    if not error_message: product.save() 
            except ValueError: error_message = "خطأ: الكمية يجب أن تكون رقماً صحيحاً."
            except InventoryItem.DoesNotExist: error_message = "خطأ: المنتج غير موجود."
    products_in_branch = InventoryItem.objects.filter(branch=current_branch)
    context = {'products': products_in_branch, 'page_title': 'حركات المخزون', 'error_message': error_message, 'success_message': success_message}
    return render(request, 'salesapp/manage_inventory_movements.html', context)

# =======================================
# (جديد) دالة تحليل نص نظام القسط
# =======================================
def parse_installment_string(ps_string):
    """
    تحليل نص نظام القسط (مثل "10*100 + 2*200")
    وتحويله إلى قائمة بالمبالغ الشهرية.
    ترجع قائمة بالأرقام أو رسالة خطأ نصية.
    """
    if not ps_string: # إذا كان النص فارغاً (بيع كاش أو خطأ)
        return [] # نرجع قائمة فارغة (أفضل من "SD")

    try:
        ps_list1 = re.split("\+", ps_string.strip())
        ps_list = []
        for m_part in ps_list1:
            m = m_part.strip()
            if not m:
                # return "SP" # جزء فارغ بين علامات +
                raise ValueError("يوجد جزء فارغ في نظام القسط (علامة + زائدة؟)")

            parts = m.split("*")
            
            # التأكد من وجود جزئين على الأقل بعد التقسيم بـ *
            if len(parts) < 2:
                 # إذا كان جزء واحد فقط (مثل "500")، نفترض أنه قسط واحد بهذا المبلغ
                 if len(parts) == 1 and parts[0].isdigit():
                     count = 1
                     amount_str = parts[0].strip()
                 else:
                     raise ValueError(f"الصيغة غير صحيحة للجزء: '{m_part}'. يجب أن تكون 'عدد*مبلغ' أو 'مبلغ'.")
            else:
                part1 = parts[0].strip()
                part2 = parts[1].strip()

                if not part1.isdigit() or not part2.isdigit():
                     raise ValueError(f"الأرقام غير صحيحة في الجزء: '{m_part}'. تأكد من استخدام أرقام فقط.")

                num1 = int(part1)
                num2 = int(part2)

                # منطق التبديل كما هو في الكود الأصلي
                if num2 < 20 and num1 >= 20: # نفترض أن الرقم الصغير هو العدد والكبير هو المبلغ
                    count = num2
                    amount_str = part1
                elif num1 < 20 and num2 >= 20:
                     count = num1
                     amount_str = part2
                else: # إذا كان كلاهما صغيراً أو كبيراً، نفترض الأول هو العدد
                    count = num1
                    amount_str = part2

            if not amount_str:
                # return "SM" # مبلغ فارغ
                raise ValueError(f"المبلغ فارغ في الجزء: '{m_part}'.")
            
            if not amount_str.isdigit():
                 raise ValueError(f"المبلغ '{amount_str}' ليس رقماً صحيحاً في الجزء: '{m_part}'.")

            amount = int(amount_str)
            for _ in range(count):
                ps_list.append(amount)
                
        return ps_list # إرجاع قائمة المبالغ (كأرقام)
        
    except ValueError as e:
        return f"خطأ في تحليل نظام القسط: {e}" # إرجاع رسالة الخطأ
    except Exception as e:
        # لأي أخطاء أخرى غير متوقعة
        return f"خطأ غير متوقع في تحليل نظام القسط: {e}"


# =======================================
# (تم التحديث بالكامل) قسم إضافة وصل
# =======================================
def generate_receipt_number(branch_id):
    # ... الكود كما هو ...
    last_receipt = Receipt.objects.filter(branch_id=branch_id).order_by('-id').first()
    if last_receipt and last_receipt.receipt_number.isdigit(): return str(int(last_receipt.receipt_number) + 1)
    else: return "1" 

@branch_required
def add_receipt(request):
    current_branch = request.branch
    error_message = None
    success_message = None
    retained_salesperson_id = request.session.pop('retained_salesperson_id', None)
    retained_area = request.session.pop('retained_area', '')

    if request.method == 'POST':
        # --- قراءة البيانات الأساسية ---
        receipt_number = request.POST.get('receipt_number')
        salesperson_id = request.POST.get('salesperson_id')
        sale_year = request.POST.get('sale_year')
        sale_month = request.POST.get('sale_month')
        is_cash_sale = request.POST.get('is_cash_sale') == 'on'
        area = request.POST.get('area', '')
        customer_name = request.POST.get('customer_name', '')
        phone_number = request.POST.get('phone_number', '')
        address = request.POST.get('address', '')
        down_payment_str = request.POST.get('down_payment', '0')
        down_payment = int(down_payment_str) if down_payment_str.isdigit() else 0
        installment_system = request.POST.get('installment_system', '').strip() # .strip() لإزالة المسافات
        sale_items_json = request.POST.get('sale_items_json', '[]')

        try:
            sale_items_data = json.loads(sale_items_json)
        except json.JSONDecodeError:
            error_message = "خطأ في بيانات المنتجات المضافة."
            sale_items_data = []

        # --- التحقق المبدئي ---
        if not salesperson_id or not sale_year or not sale_month or not receipt_number: error_message = "خطأ: يرجى ملء المندوب والتاريخ."
        elif not sale_items_data: error_message = "خطأ: يجب إضافة منتج واحد على الأقل."
        elif not is_cash_sale and not customer_name: error_message = "خطأ: اسم العميل إجباري للتقسيط."
        elif not is_cash_sale and not installment_system: error_message = "خطأ: يجب وصف نظام القسط للتقسيط."
        
        # --- (جديد) تحليل نص نظام القسط مبدئياً ---
        installment_amounts = []
        if not error_message and not is_cash_sale:
            parse_result = parse_installment_string(installment_system)
            if isinstance(parse_result, str): # إذا كانت النتيجة رسالة خطأ
                error_message = parse_result
            else:
                installment_amounts = parse_result # قائمة المبالغ
                if not installment_amounts: # إذا كانت القائمة فارغة رغم أنه ليس كاش
                     error_message = "خطأ: لم يتم العثور على أقساط صحيحة في نص نظام القسط."

        # --- عملية الحفظ ---
        if not error_message:
            try:
                with transaction.atomic():
                    # 1. التحقق من المخزون وتجهيز المبيعات
                    total_amount_calculated = 0
                    items_to_save = []
                    product_updates = {}
                    for item_data in sale_items_data:
                        product_id = item_data.get('id')
                        quantity = item_data.get('quantity')
                        unit_price = item_data.get('price')
                        if not product_id or not quantity or unit_price is None: raise ValueError("بيانات منتج غير مكتملة.")
                        
                        # --- (تحسين) استخدام select_for_update لضمان عدم حدوث تعديل متزامن ---
                        product = InventoryItem.objects.select_for_update().get(pk=product_id, branch=current_branch)
                        if product.quantity < quantity: raise IntegrityError(f"مخزون '{product.name}' غير كاف ({product.quantity} متاح).")
                        
                        items_to_save.append(SaleItem(inventory_item=product, quantity=quantity, unit_price=unit_price))
                        total_amount_calculated += quantity * unit_price
                        product_updates[product_id] = quantity 

                    # 2. التحقق من تطابق إجمالي الأقساط + المقدم مع إجمالي الفاتورة (للتقسيط)
                    if not is_cash_sale:
                         total_installments_value = sum(installment_amounts)
                         if total_installments_value + down_payment != total_amount_calculated:
                             raise ValueError(f"الإجمالي المحسوب ({total_amount_calculated}) لا يساوي مجموع المقدم ({down_payment}) والأقساط ({total_installments_value}). يرجى مراجعة نظام القسط أو الأسعار.")

                    # 3. حفظ الوصل الرئيسي
                    salesperson = get_object_or_404(Salesperson, pk=salesperson_id, branch=current_branch)
                    receipt = Receipt.objects.create(
                        receipt_number=receipt_number, branch=current_branch, salesperson=salesperson,
                        sale_year=int(sale_year), sale_month=int(sale_month), is_cash_sale=is_cash_sale,
                        customer_name=customer_name, phone_number=phone_number, address=address, area=area,
                        total_amount=total_amount_calculated,
                        down_payment=down_payment if not is_cash_sale else total_amount_calculated,
                        installment_system=installment_system if not is_cash_sale else ''
                    )

                    # 4. ربط المبيعات بالوصل وحفظها
                    for sale_item in items_to_save: sale_item.receipt = receipt
                    SaleItem.objects.bulk_create(items_to_save)

                    # 5. تحديث المخزون
                    for product_id, quantity_sold in product_updates.items():
                        InventoryItem.objects.filter(pk=product_id).update(quantity=F('quantity') - quantity_sold)

                    # 6. (هام) إنشاء سجلات الأقساط
                    if not is_cash_sale:
                        installments_to_create = []
                        # حساب تاريخ أول قسط (الشهر التالي للشراء)
                        # نفترض يوم 1 في الشهر لسهولة الحساب
                        try:
                            start_date = date(int(sale_year), int(sale_month), 1)
                        except ValueError:
                             raise ValueError("سنة أو شهر البيع غير صحيح.")

                        for i, amount in enumerate(installment_amounts):
                            payment_due_date = start_date + relativedelta(months=i + 1)
                            installments_to_create.append(InstallmentPayment(
                                receipt=receipt,
                                payment_date=payment_due_date,
                                amount=amount,
                                is_paid=False, # القسط يبدأ غير مدفوع
                                collector=None # يبدأ غير معين
                            ))
                        InstallmentPayment.objects.bulk_create(installments_to_create)

                    # --- نجاح العملية ---
                    success_message = f"تم حفظ الوصل رقم {receipt_number} بنجاح."
                    request.session['retained_salesperson_id'] = salesperson_id
                    request.session['retained_area'] = area
                    return redirect('add_receipt')

            except (IntegrityError, ValueError, InventoryItem.DoesNotExist, Salesperson.DoesNotExist) as e:
                error_message = f"خطأ أثناء الحفظ: {e}"
            except Exception as e:
                 error_message = f"حدث خطأ غير متوقع: {e}"

    # --- عرض الصفحة (GET) أو بعد خطأ في POST ---
    salespersons_in_branch = Salesperson.objects.filter(branch=current_branch)
    products_in_branch = InventoryItem.objects.filter(branch=current_branch, quantity__gt=0).order_by('name') # ترتيب أبجدي
    
    now = timezone.now()
    default_year = now.year
    default_month = now.month
    next_receipt_number = generate_receipt_number(current_branch.id)
    
    context = {
        'page_title': 'إضافة وصل جديد',
        'salespersons': salespersons_in_branch,
        'products': products_in_branch,
        'default_year': default_year,
        'default_month': default_month,
        'next_receipt_number': next_receipt_number,
        'error_message': error_message,
        'success_message': success_message,
        'retained_salesperson_id': retained_salesperson_id,
        'retained_area': retained_area,
    }
    return render(request, 'salesapp/add_receipt.html', context)
# ... (كل الكود السابق موجود هنا) ...
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger # (جديد) لتقسيم النتائج لصفحات

# =======================================
# (جديد) قسم بحث / طباعة الوصلات
# =======================================

@branch_required
def search_receipts(request):
    """
    صفحة للبحث عن الوصلات باستخدام فلاتر متعددة وعرض النتائج.
    """
    current_branch = request.branch
    
    # جلب كل الوصلات الخاصة بالفرع الحالي مبدئياً
    receipts_list = Receipt.objects.filter(branch=current_branch).order_by('-sale_year', '-sale_month', '-id') # الأحدث أولاً

    # --- تطبيق الفلاتر (من خلال GET parameters في الرابط) ---
    salesperson_id = request.GET.get('salesperson')
    search_year = request.GET.get('year')
    search_month = request.GET.get('month')
    receipt_from = request.GET.get('receipt_from')
    receipt_to = request.GET.get('receipt_to')
    customer_name = request.GET.get('customer')

    if salesperson_id:
        receipts_list = receipts_list.filter(salesperson_id=salesperson_id)
    if search_year:
        receipts_list = receipts_list.filter(sale_year=search_year)
    if search_month:
        receipts_list = receipts_list.filter(sale_month=search_month)
    # (ملاحظة: البحث برقم الوصل قد يحتاج لتحويله لرقم إذا كان الرقم تلقائياً)
    # سنفترضه نصياً حالياً كما هو في النموذج
    if receipt_from:
        receipts_list = receipts_list.filter(receipt_number__gte=receipt_from)
    if receipt_to:
        receipts_list = receipts_list.filter(receipt_number__lte=receipt_to)
    if customer_name:
        # البحث بـ "يحتوي على" لاسم العميل (غير حساس لحالة الأحرف)
        receipts_list = receipts_list.filter(customer_name__icontains=customer_name)

    # --- (جديد) تقسيم النتائج إلى صفحات ---
    paginator = Paginator(receipts_list, 25) # عرض 25 وصل في كل صفحة
    page_number = request.GET.get('page')
    try:
        receipts_page = paginator.page(page_number)
    except PageNotAnInteger:
        # إذا لم يكن رقم الصفحة صحيحاً، اعرض الصفحة الأولى
        receipts_page = paginator.page(1)
    except EmptyPage:
        # إذا كان رقم الصفحة خارج النطاق، اعرض الصفحة الأخيرة
        receipts_page = paginator.page(paginator.num_pages)

    # جلب الموظفين لعرضهم في فلتر البحث
    salespersons_in_branch = Salesperson.objects.filter(branch=current_branch)

    context = {
        'page_title': 'بحث / طباعة الوصلات',
        'receipts': receipts_page, # إرسال الصفحة الحالية للقالب
        'salespersons': salespersons_in_branch,
        # إعادة إرسال قيم الفلاتر للقالب لعرضها في الفورم
        'current_salesperson': salesperson_id,
        'current_year': search_year,
        'current_month': search_month,
        'current_receipt_from': receipt_from,
        'current_receipt_to': receipt_to,
        'current_customer': customer_name,
    }
    return render(request, 'salesapp/search_receipts.html', context)