from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, F, Sum, Count, Value, Max
from django.db.models.functions import Coalesce
from django.utils import timezone
import json
import re
from datetime import date
from dateutil.relativedelta import relativedelta
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from salesapp.models import Branch, Salesperson, InventoryItem, Receipt, SaleItem, InstallmentPayment

# --- (تم التعديل) دالة إنشاء رقم الوصل ---
def generate_receipt_number():
    """
    يجلب أعلى رقم وصل موجود في قاعدة البيانات ويزيده بواحد.
    """
    last_receipt = Receipt.objects.order_by('-receipt_number').first()
    if last_receipt:
        # زيادة 1 على آخر رقم
        return last_receipt.receipt_number + 1
    # إذا كانت قاعدة البيانات فارغة، نبدأ من 1
    return 1

def parse_installment_string(ps_string):
    # ... (الكود كما هو) ...
    if not ps_string: return []
    try:
        ps_list1 = re.split("\+", ps_string.strip())
        ps_list = []
        for m_part in ps_list1:
            m = m_part.strip();
            if not m: raise ValueError("يوجد جزء فارغ (علامة + زائدة؟)")
            parts = m.split("*")
            if len(parts) < 2:
                 if len(parts) == 1 and parts[0].isdigit():
                     count = 1; amount_str = parts[0].strip()
                 else: raise ValueError(f"الصيغة '{m_part}' خاطئة.")
            else:
                part1 = parts[0].strip(); part2 = parts[1].strip()
                if not part1.isdigit() or not part2.isdigit(): raise ValueError(f"الأرقام غير صحيحة في '{m_part}'.")
                num1 = int(part1); num2 = int(part2)
                if num2 < 20 and num1 >= 20: count = num2; amount_str = part1
                elif num1 < 20 and num2 >= 20: count = num1; amount_str = part2
                else: count = num1; amount_str = part2
            if not amount_str: raise ValueError(f"المبلغ فارغ في '{m_part}'.")
            if not amount_str.isdigit(): raise ValueError(f"المبلغ '{amount_str}' ليس رقماً.")
            amount = int(amount_str)
            for _ in range(count): ps_list.append(amount)
        return ps_list
    except ValueError as e: return f"خطأ في تحليل نظام القسط: {e}"
    except Exception as e: return f"خطأ غير متوقع في تحليل نظام القسط: {e}"

# =======================================
# (Middleware) فلتر الفرع الشامل
# =======================================
def branch_required(view_func):
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
    request.session.flush() 
    branches = Branch.objects.all()
    return render(request, 'salesapp/select_branch.html', {'branches': branches})

def set_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    request.session['selected_branch_id'] = branch.id
    request.session['selected_branch_name'] = branch.name
    return redirect('dashboard') 

# =======================================
# قسم Dashboard
# =======================================
@branch_required
def dashboard(request):
    # ... (الكود كما هو) ...
    current_branch = request.branch
    now = timezone.now()
    selected_year = request.GET.get('year', now.year)
    selected_month = request.GET.get('month', now.month)
    try:
        selected_year = int(selected_year); selected_month = int(selected_month)
        if not (1 <= selected_month <= 12): selected_month = now.month
    except (ValueError, TypeError): selected_year = now.year; selected_month = now.month

    sales_by_salesperson = Salesperson.objects.filter(
        branch=current_branch, receipt__sale_year=selected_year, receipt__sale_month=selected_month
    ).annotate(total_sales=Coalesce(Sum('receipt__total_amount'), 0), receipt_count=Count('receipt')
    ).filter(receipt_count__gt=0).order_by('-total_sales')
    total_sales_all = sum(s.total_sales for s in sales_by_salesperson)
    downpayments_and_cash = Receipt.objects.filter(
        branch=current_branch, sale_year=selected_year, sale_month=selected_month
    ).aggregate(total_downpayments=Coalesce(Sum('down_payment'), 0))['total_downpayments']
    
    collected_installments_by_collector = Salesperson.objects.filter(
        branch=current_branch, installmentpayment__is_paid=True,
        installmentpayment__payment_date__year=selected_year, 
        installmentpayment__payment_date__month=selected_month
    ).annotate(
        total_collected=Coalesce(Sum('installmentpayment__amount'), 0),
        installments_count=Count('installmentpayment')
    ).filter(installments_count__gt=0).order_by('-total_collected')
    total_collected_all = sum(c.total_collected for c in collected_installments_by_collector)
    total_cash_in = downpayments_and_cash + total_collected_all

    last_day_of_selected_month = (date(selected_year, selected_month, 1) + relativedelta(months=1)) - relativedelta(days=1)
    remaining_installments = InstallmentPayment.objects.filter(
        receipt__branch=current_branch, payment_date__lte=last_day_of_selected_month, is_paid=False
    )
    remaining_unassigned = remaining_installments.filter(collector__isnull=True).aggregate(count=Count('id'), total=Coalesce(Sum('amount'), 0))
    remaining_assigned_not_paid = remaining_installments.filter(collector__isnull=False).aggregate(count=Count('id'), total=Coalesce(Sum('amount'), 0))
    
    available_years = range(now.year - 2, now.year + 2)
    available_months = range(1, 13)

    context = {
        'page_title': 'Dashboard الرئيسية', 'selected_year': selected_year, 'selected_month': selected_month,
        'available_years': available_years, 'available_months': available_months,
        'sales_by_salesperson': sales_by_salesperson, 'total_sales_all': total_sales_all,
        'downpayments_and_cash': downpayments_and_cash, 'collected_installments_by_collector': collected_installments_by_collector,
        'total_collected_all': total_collected_all, 'total_cash_in': total_cash_in,
        'remaining_unassigned': remaining_unassigned, 'remaining_assigned_not_paid': remaining_assigned_not_paid,
    }
    return render(request, 'salesapp/dashboard.html', context)


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
# (تم التعديل) قسم إضافة وصل
# =======================================
@branch_required
def add_receipt(request):
    current_branch = request.branch
    now = timezone.now()

    context = {
        'page_title': 'إضافة وصل جديد',
        'salespersons': Salesperson.objects.filter(branch=current_branch),
        'products': InventoryItem.objects.filter(branch=current_branch, quantity__gt=0).order_by('name'),
        'default_year': now.year, 'default_month': now.month,
        'error_message': None, 'success_message': request.session.pop('success_message', None),
        'retained_salesperson_id': request.session.pop('retained_salesperson_id', None),
        'retained_area': request.session.pop('retained_area', ''),
        'retained_customer_name': '', 'retained_phone': '', 'retained_address': '',
        'retained_down_payment': 0, 'retained_installment_system': '',
        'retained_is_cash': False, 'retained_sale_items_json': '[]',
        'highlight_installment_system': False,
    }
    # (تم التعديل) إنشاء رقم جديد دائماً في البداية
    context['next_receipt_number'] = generate_receipt_number()


    if request.method == 'POST':
        # --- (تم التعديل) لم نعد نقرأ رقم الوصل من الفورم ---
        # receipt_number = request.POST.get('receipt_number')
        salesperson_id = request.POST.get('salesperson_id')
        sale_year = request.POST.get('sale_year'); sale_month = request.POST.get('sale_month')
        is_cash_sale = request.POST.get('is_cash_sale') == 'on'
        area = request.POST.get('area', ''); customer_name = request.POST.get('customer_name', '')
        phone_number = request.POST.get('phone_number', ''); address = request.POST.get('address', '')
        down_payment_str = request.POST.get('down_payment', '0')
        down_payment = int(down_payment_str) if down_payment_str.isdigit() else 0
        installment_system = request.POST.get('installment_system', '').strip()
        sale_items_json = request.POST.get('sale_items_json', '[]')
        
        error_message = None 

        try: sale_items_data = json.loads(sale_items_json)
        except json.JSONDecodeError: error_message = "خطأ في بيانات المنتجات."; sale_items_data = []
        if not salesperson_id or not sale_year or not sale_month: error_message = "خطأ: يرجى ملء المندوب والتاريخ."
        elif not sale_items_data: error_message = "خطأ: يجب إضافة منتج واحد على الأقل."
        elif not is_cash_sale and not customer_name: error_message = "خطأ: اسم العميل إجباري للتقسيط."
        elif not is_cash_sale and not installment_system: error_message = "خطأ: يجب وصف نظام القسط للتقسيط."
        
        installment_amounts = []
        if not error_message and not is_cash_sale:
            parse_result = parse_installment_string(installment_system)
            if isinstance(parse_result, str): error_message = parse_result
            else:
                installment_amounts = parse_result
                if not installment_amounts: error_message = "خطأ: لم يتم العثور على أقساط صحيحة."

        if not error_message:
            try:
                with transaction.atomic():
                    # 1. تجهيز المنتجات
                    product_strings = []
                    total_amount_calculated = 0; items_to_save = []; product_updates = {}
                    for item_data in sale_items_data:
                        product_id = item_data.get('id'); quantity = item_data.get('quantity'); unit_price = item_data.get('price')
                        product_name = item_data.get('name')
                        if not product_id or not quantity or unit_price is None or not product_name: raise ValueError("بيانات منتج غير مكتملة.")
                        product = InventoryItem.objects.select_for_update().get(pk=product_id, branch=current_branch)
                        if product.quantity < quantity: raise IntegrityError(f"مخزون '{product.name}' غير كاف ({product.quantity} متاح).")
                        items_to_save.append(SaleItem(inventory_item=product, quantity=quantity, unit_price=unit_price))
                        total_amount_calculated += quantity * unit_price
                        product_updates[product_id] = quantity
                        product_strings.append(f"{quantity} x {product_name}")
                    products_text_to_save = " + ".join(product_strings)

                    # 2. التحقق من تطابق إجمالي الأقساط
                    if not is_cash_sale:
                         total_installments_value = sum(installment_amounts)
                         if total_installments_value + down_payment != total_amount_calculated:
                             raise ValueError(f"الإجمالي ({total_amount_calculated}) لا يساوي المقدم ({down_payment}) + الأقساط ({total_installments_value}).")
                    
                    salesperson = get_object_or_404(Salesperson, pk=salesperson_id, branch=current_branch)
                    
                    # --- (تم التعديل) إنشاء الرقم هنا ---
                    receipt_number_to_save = generate_receipt_number()
                    
                    receipt = Receipt.objects.create(
                        receipt_number=receipt_number_to_save,
                        branch=current_branch, salesperson=salesperson,
                        sale_year=int(sale_year), sale_month=int(sale_month), is_cash_sale=is_cash_sale,
                        customer_name=customer_name, products_text=products_text_to_save, 
                        phone_number=phone_number, address=address, area=area,
                        total_amount=total_amount_calculated,
                        down_payment=down_payment if not is_cash_sale else total_amount_calculated,
                        installment_system=installment_system if not is_cash_sale else ''
                    )
                    
                    # 4. حفظ المبيعات
                    for sale_item in items_to_save: sale_item.receipt = receipt
                    SaleItem.objects.bulk_create(items_to_save)
                    # 5. تحديث المخزون
                    for product_id, quantity_sold in product_updates.items():
                        InventoryItem.objects.filter(pk=product_id).update(quantity=F('quantity') - quantity_sold)
                    # 6. إنشاء الأقساط
                    if not is_cash_sale and installment_amounts:
                        installments_to_create = []
                        try: start_date = date(int(sale_year), int(sale_month), 15)
                        except ValueError: raise ValueError("سنة أو شهر البيع غير صحيح.")
                        for i, amount in enumerate(installment_amounts):
                            if amount > 0:
                                payment_due_date = start_date + relativedelta(months=i + 1)
                                installments_to_create.append(InstallmentPayment(
                                    receipt=receipt, payment_date=payment_due_date, amount=amount
                                ))
                        if installments_to_create:
                            InstallmentPayment.objects.bulk_create(installments_to_create)

                    request.session['retained_salesperson_id'] = salesperson_id
                    request.session['retained_area'] = area
                    request.session['success_message'] = f"تم حفظ الوصل رقم {receipt_number_to_save} بنجاح."
                    return redirect('add_receipt') 

            except (IntegrityError, ValueError, InventoryItem.DoesNotExist, Salesperson.DoesNotExist) as e:
                error_message = f"خطأ أثناء الحفظ: {e}"
                # (جديد) معالجة خطأ تضارب الأرقام (نادر)
                if "receipt_number" in str(e):
                    error_message = f"خطأ تضارب: تم حفظ وصل آخر بنفس الرقم. تم إنشاء رقم جديد، يرجى المحاولة مرة أخرى."
            except Exception as e:
                 error_message = f"حدث خطأ غير متوقع: {e}"
        
        # --- (تم التعديل) معالجة الأخطاء (بدون فقدان البيانات) ---
        context['error_message'] = error_message
        context['retained_salesperson_id'] = salesperson_id
        context['retained_area'] = area
        context['retained_customer_name'] = customer_name
        context['retained_phone'] = phone_number
        context['retained_address'] = address
        context['retained_down_payment'] = down_payment
        context['retained_installment_system'] = installment_system
        context['retained_is_cash'] = is_cash_sale
        context['retained_sale_items_json'] = sale_items_json
        context['default_year'] = int(sale_year) if sale_year and sale_year.isdigit() else now.year
        context['default_month'] = int(sale_month) if sale_month and sale_month.isdigit() else now.month
        
        # --- (تم الإصلاح) ---
        # دائماً قم بإنشاء رقم جديد عند عرض الصفحة (سواء GET أو POST خطأ)
        context['next_receipt_number'] = generate_receipt_number() 
            
        if "الإجمالي" in str(error_message): # تمييز الخطأ الخاص بك
            context['highlight_installment_system'] = True
            
        return render(request, 'salesapp/add_receipt.html', context)

    return render(request, 'salesapp/add_receipt.html', context)


# =======================================
# قسم بحث / طباعة الوصلات
# =======================================
@branch_required
def search_receipts(request):
    # ... (الكود كما هو) ...
    current_branch = request.branch
    receipts_list = Receipt.objects.filter(branch=current_branch).order_by('-receipt_number')
    salesperson_id = request.GET.get('salesperson')
    search_year = request.GET.get('year')
    search_month = request.GET.get('month')
    receipt_from = request.GET.get('receipt_from')
    receipt_to = request.GET.get('receipt_to')
    customer_name = request.GET.get('customer')
    if salesperson_id: receipts_list = receipts_list.filter(salesperson_id=salesperson_id)
    if search_year: receipts_list = receipts_list.filter(sale_year=search_year)
    if search_month: receipts_list = receipts_list.filter(sale_month=search_month)
    try:
        if receipt_from: receipts_list = receipts_list.filter(receipt_number__gte=int(receipt_from))
    except (ValueError, TypeError): pass
    try:
        if receipt_to: receipts_list = receipts_list.filter(receipt_number__lte=int(receipt_to))
    except (ValueError, TypeError): pass
    if customer_name: receipts_list = receipts_list.filter(customer_name__icontains=customer_name)
    
    paginator = Paginator(receipts_list, 25)
    page_number = request.GET.get('page')
    try: receipts_page = paginator.page(page_number)
    except PageNotAnInteger: receipts_page = paginator.page(1)
    except EmptyPage: receipts_page = paginator.page(paginator.num_pages)
    salespersons_in_branch = Salesperson.objects.filter(branch=current_branch)
    context = {
        'page_title': 'بحث / طباعة الوصلات', 'receipts': receipts_page,
        'salespersons': salespersons_in_branch, 'current_salesperson': salesperson_id,
        'current_year': search_year, 'current_month': search_month,
        'current_receipt_from': receipt_from, 'current_receipt_to': receipt_to,
        'current_customer': customer_name,
    }
    return render(request, 'salesapp/search_receipts.html', context)

# =======================================
# قسم تعديل الوصل (الخطوة القادمة)
# =======================================
@branch_required
def edit_receipt(request, receipt_id):
    # ... (الكود كما هو) ...
    current_branch = request.branch
    try: receipt = Receipt.objects.prefetch_related('items', 'payments').get(pk=receipt_id, branch=current_branch)
    except Receipt.DoesNotExist: return redirect('search_receipts') 
    error_message = None; success_message = None; highlight_installment_system = False
    
    if request.method == 'POST':
        # (سنبرمج هذا لاحقاً)
        error_message = "لم يتم برمجة الحفظ بعد."
        pass # سنملأ هذا قريباً
    
    salespersons_in_branch = Salesperson.objects.filter(branch=current_branch)
    current_product_ids = receipt.items.values_list('inventory_item_id', flat=True)
    available_products = InventoryItem.objects.filter(branch=current_branch, quantity__gt=0).order_by('name')
    current_products_in_receipt = InventoryItem.objects.filter(pk__in=current_product_ids)
    products_in_dropdown = (available_products | current_products_in_receipt).distinct().order_by('name')

    if error_message: 
         sale_items_json_str = request.POST.get('sale_items_json', '[]')
    else: 
        current_sale_items = receipt.items.all()
        sale_items_list = []
        for item in current_sale_items:
            sale_items_list.append({
                'id': str(item.inventory_item.id), 'name': item.inventory_item.name,
                'quantity': item.quantity, 'price': item.unit_price
            })
        sale_items_json_str = json.dumps(sale_items_list)
    context = {
        'page_title': f'تعديل وصل رقم {receipt.receipt_number}', 'receipt': receipt,
        'salespersons': salespersons_in_branch, 
        'products': products_in_dropdown, 
        'sale_items_json_str': sale_items_json_str, 'error_message': error_message,
        'success_message': success_message, 'highlight_installment_system': highlight_installment_system,
    }
    return render(request, 'salesapp/edit_receipt.html', context)


# =======================================
# دوال الحذف (لا تغيير هنا)
# =======================================
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