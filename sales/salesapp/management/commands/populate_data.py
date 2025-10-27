import random
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import F, Max, ProtectedError

from salesapp.models import Branch, Salesperson, InventoryItem, Receipt, SaleItem, InstallmentPayment
import re
from datetime import date

# ... (قوائم الأسماء والمدن والمنتجات كما هي) ...
FIRST_NAMES = ["محمد", "أحمد", "علي", "محمود", "إبراهيم", "حسن", "حسين", "خالد", "يوسف", "عمر"]
LAST_NAMES = ["السيد", "عبدالله", "علي", "محمود", "حسن", "خالد", "جمال", "صالح", "سعيد", "منصور"]
CITIES = ["القاهرة", "الجيزة", "الإسكندرية", "المنصورة", "طنطا", "المحلة", "أسيوط", "سوهاج"]
PRODUCTS = [
    ("ثلاجة", 1500, 3000), ("غسالة", 1800, 3500), ("بوتاجاز", 1000, 2500),
    ("تلفزيون", 1200, 2800), ("مروحة", 300, 800), ("مكواة", 150, 400),
    ("خلاط", 200, 600), ("كبة", 250, 700), ("مكنسة", 800, 2000),
    ("دفاية", 400, 1000), ("سخان", 600, 1500), ("فلتر مياه", 700, 1800),
    ("شاشة كمبيوتر", 900, 2200), ("لابتوب", 2500, 5000), ("طابعة", 500, 1200),
    ("راوتر", 100, 300), ("موبايل", 1000, 4000), ("تابلت", 800, 2500),
    ("سماعة بلوتوث", 50, 200), ("باور بانك", 80, 250)
]

class Command(BaseCommand):
    help = 'Populates the database with a large amount of fake sales data (2500 receipts per branch).'

    last_receipt_number = 0

    def get_next_receipt_number(self):
        if self.last_receipt_number == 0:
            max_num_dict = Receipt.objects.aggregate(Max('receipt_number'))
            max_num = max_num_dict.get('receipt_number__max')
            try: self.last_receipt_number = int(max_num) if max_num and max_num.isdigit() else 0
            except (ValueError, TypeError): self.last_receipt_number = 0
        self.last_receipt_number += 1
        return str(self.last_receipt_number)

    def handle(self, *args, **kwargs):
        self.stdout.write("بدء عملية إضافة البيانات المزيفة (كمية كبيرة)...")

        self.stdout.write("مسح البيانات القديمة...")
        try:
            InstallmentPayment.objects.all().delete()
            SaleItem.objects.all().delete()
            Receipt.objects.all().delete()
            InventoryItem.objects.all().delete()
            Salesperson.objects.all().delete()
            Branch.objects.all().delete()
            self.stdout.write("تم مسح البيانات القديمة.")
        except ProtectedError as e:
             self.stdout.write(self.style.ERROR(f"خطأ أثناء مسح البيانات: {e}"))
             self.stdout.write(self.style.WARNING("قد تحتاج لحذف ملف db.sqlite3 يدوياً."))
             return

        # --- 1. إنشاء الفروع ---
        branches = []
        num_branches = 2 # فرعين فقط
        created_branches_count = 0
        branch_names_to_create = random.sample(CITIES, k=num_branches)
        for i, city_name in enumerate(branch_names_to_create):
            branch_name = f"فرع {city_name}"
            try:
                branch, created = Branch.objects.get_or_create(name=branch_name)
                branches.append(branch)
                if created: created_branches_count += 1
            except IntegrityError: pass
        if not branches:
             self.stdout.write(self.style.ERROR("لم يتم إنشاء أو العثور على أي فروع. التوقف."))
             return
        self.stdout.write(f"تم إنشاء {created_branches_count} فروع جديدة (الإجمالي: {len(branches)}).")

        # --- 2. إنشاء الموظفين ---
        all_salespersons = []
        salespersons_by_branch = {b.id: [] for b in branches}
        total_salespersons = 0
        num_salespersons_per_branch = 5
        for branch in branches:
            created_in_branch = 0
            attempts = 0
            while created_in_branch < num_salespersons_per_branch and attempts < 50:
                attempts += 1
                name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                try:
                    person, created = Salesperson.objects.get_or_create(name=name, branch=branch)
                    salespersons_by_branch[branch.id].append(person)
                    all_salespersons.append(person)
                    if created: total_salespersons += 1; created_in_branch += 1
                except IntegrityError: pass
            if created_in_branch < num_salespersons_per_branch:
                 self.stdout.write(self.style.WARNING(f"تم إنشاء {created_in_branch} موظفين جدد فقط في {branch.name}."))
        if not all_salespersons:
            self.stdout.write(self.style.ERROR("لم يتم إنشاء أو العثور على أي موظفين. التوقف."))
            return
        self.stdout.write(f"تم إنشاء {total_salespersons} موظفين جدد (الإجمالي: {len(all_salespersons)}).")

        # --- 3. إنشاء المنتجات والمخزون ---
        inventory_items_by_branch = {b.id: [] for b in branches}
        total_inventory = 0
        num_products_per_branch = 20
        for branch in branches:
            created_in_branch = 0
            product_sample = random.sample(PRODUCTS, k=num_products_per_branch)
            for prod_name, min_price, max_price in product_sample:
                try:
                    item_name = prod_name
                    item, created = InventoryItem.objects.get_or_create(
                        name=item_name, branch=branch,
                        defaults={
                             'quantity': random.randint(150, 500), # زيادة الكمية الأولية أكثر
                             'purchase_price': random.randint(min_price // 2, max_price // 2),
                             'salesperson_commission_amount': random.randint(10, 50)
                        }
                    )
                    inventory_items_by_branch[branch.id].append(item)
                    if created: total_inventory += 1; created_in_branch += 1
                except IntegrityError: pass
        self.stdout.write(f"تم إنشاء {total_inventory} سجلات مخزون جديدة.")


        # --- 4. إنشاء الوصلات (2500 لكل فرع) ---
        self.stdout.write("بدء إنشاء الوصلات (سيستغرق وقتاً طويلاً)...")
        receipts_created_total = 0
        current_date = timezone.now().date()
        self.last_receipt_number = 0

        # --- (تم التعديل) حلقة الفروع ---
        for branch in branches:
            self.stdout.write(f"  - إنشاء 2500 وصل لـ {branch.name}...")
            receipts_created_for_branch = 0
            # التأكد من وجود موظفين ومنتجات في هذا الفرع
            branch_salespersons = salespersons_by_branch.get(branch.id, [])
            if not branch_salespersons:
                self.stdout.write(self.style.WARNING(f"    * تخطي الفرع {branch.name} لعدم وجود موظفين."))
                continue
                
            # --- (تم التعديل) حلقة إنشاء 2500 وصل ---
            for i in range(2500):
                try:
                    with transaction.atomic():
                        # اختيار مندوب عشوائي من هذا الفرع
                        salesperson = random.choice(branch_salespersons)

                        # تاريخ عشوائي خلال آخر 14 شهر
                        month_offset = random.randint(0, 13) # 0 to 13 for 14 months
                        target_date = current_date - relativedelta(months=month_offset)
                        # إضافة يوم عشوائي في الشهر
                        try:
                             random_day = random.randint(1, target_date.replace(day=1).days_in_month) # يجب التأكد من عدد أيام الشهر
                             target_date = target_date.replace(day=random_day)
                        except AttributeError: # Fallback for potential date calculation issues near month ends
                             pass # Keep the first day if calculation fails

                        target_year = target_date.year
                        target_month = target_date.month

                        # اختيار المنتجات (يجب أن تكون من نفس الفرع)
                        available_products = list(InventoryItem.objects.filter(branch=branch, quantity__gt=0))
                        if not available_products:
                             # إذا نفذ المخزون، نضيف كمية افتراضية للمنتجات الموجودة
                             self.stdout.write(self.style.WARNING(f"    * نفذ المخزون في {branch.name}. تتم إضافة كميات جديدة..."))
                             InventoryItem.objects.filter(branch=branch).update(quantity=F('quantity') + random.randint(50, 150))
                             available_products = list(InventoryItem.objects.filter(branch=branch, quantity__gt=0))
                             if not available_products:
                                 self.stdout.write(self.style.ERROR(f"    * لا توجد منتجات متاحة في {branch.name} حتى بعد محاولة الإضافة. التوقف لهذا الفرع."))
                                 break # نوقف إنشاء الوصلات لهذا الفرع


                        num_items_in_receipt = random.randint(1, 5)
                        selected_products_info = []
                        receipt_total = 0
                        possible_items = random.sample(available_products, k=min(num_items_in_receipt, len(available_products)))
                        items_added_count = 0
                        product_pks_to_update = {}

                        for product_item in possible_items:
                            quantity_to_sell = random.randint(1, 2)
                            # قراءة المخزون الحالي بدقة داخل الـ transaction
                            try:
                                # قفل السجل للقراءة والكتابة
                                current_product_instance = InventoryItem.objects.select_for_update().get(pk=product_item.pk)
                                current_stock = current_product_instance.quantity
                            except InventoryItem.DoesNotExist:
                                continue # المنتج تم حذفه في عملية متزامنة نادرة

                            already_allocated = product_pks_to_update.get(product_item.pk, 0)

                            if current_stock - already_allocated >= quantity_to_sell:
                                sale_price = random.randint(10, 60) * 50
                                selected_products_info.append((product_item, quantity_to_sell, sale_price))
                                receipt_total += quantity_to_sell * sale_price
                                items_added_count += 1
                                product_pks_to_update[product_item.pk] = already_allocated + quantity_to_sell

                        if items_added_count == 0: continue

                        # باقي البيانات (كاش، عميل، دفع، ...)
                        is_cash = random.random() < 0.01
                        cust_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}" if not is_cash else ""
                        cust_phone = f"01{random.randint(0, 2)}{random.randint(10000000, 99999999)}" if not is_cash else ""
                        cust_address = f"شارع {random.randint(1, 100)}, {random.choice(CITIES)}" if not is_cash else ""
                        cust_area = random.choice(CITIES)
                        down_payment = 0
                        installment_system_str = ""
                        installment_amounts = []

                        if not is_cash:
                            if random.random() < 0.80: down_payment = random.choice([50, 100])
                            down_payment = min(down_payment, receipt_total)
                            remaining_amount = receipt_total - down_payment
                            if random.random() < 0.90: num_months = 12
                            else:
                                possible_months = list(range(6, 19)); possible_months.remove(12)
                                num_months = random.choice(possible_months) if possible_months else 12

                            if num_months > 0 and remaining_amount > 0:
                                 base_monthly = remaining_amount // num_months
                                 monthly_amount = max(10, (base_monthly // 10) * 10)
                                 last_amount = remaining_amount - (monthly_amount * (num_months - 1))
                                 if last_amount <=0 and num_months > 1:
                                     monthly_amount = max(10, ((remaining_amount // (num_months -1)) // 10) * 10)
                                     last_amount = remaining_amount - (monthly_amount * (num_months - 1))
                                 if last_amount <= 0: monthly_amount = 0; last_amount = remaining_amount

                                 if monthly_amount == last_amount or num_months == 1:
                                     installment_system_str = f"{num_months}*{monthly_amount}"
                                     installment_amounts = [monthly_amount] * num_months
                                 elif monthly_amount == 0 and last_amount > 0:
                                      installment_system_str = f"1*{last_amount}"; installment_amounts = [last_amount]; num_months = 1
                                 elif last_amount > 0 :
                                     installment_system_str = f"{num_months-1}*{monthly_amount}+1*{last_amount}"
                                     installment_amounts = [monthly_amount] * (num_months - 1) + [last_amount]
                                 else:
                                      installment_system_str = f"{num_months}*{monthly_amount}"; installment_amounts = [monthly_amount] * num_months
                            elif remaining_amount <= 0: installment_system_str = "تم الدفع بالكامل"; num_months = 0

                        receipt_num_str = self.get_next_receipt_number()
                        receipt = Receipt.objects.create(
                            receipt_number=receipt_num_str, branch=branch, salesperson=salesperson,
                            sale_year=target_year, sale_month=target_month, is_cash_sale=is_cash,
                            customer_name=cust_name, phone_number=cust_phone, address=cust_address,
                            area=cust_area, total_amount=receipt_total,
                            down_payment=down_payment if not is_cash else receipt_total, installment_system=installment_system_str
                        )

                        items_to_save_db = []
                        for product_item, quantity_sold, price_sold in selected_products_info:
                             items_to_save_db.append(SaleItem(receipt=receipt, inventory_item=product_item, quantity=quantity_sold, unit_price=price_sold))
                        SaleItem.objects.bulk_create(items_to_save_db)

                        for pk, quantity_to_deduct in product_pks_to_update.items():
                             InventoryItem.objects.filter(pk=pk).update(quantity=F('quantity') - quantity_to_deduct)

                        if not is_cash and installment_amounts:
                            installments_to_create = []
                            start_date = date(target_year, target_month, 15)
                            for month_offset, amount in enumerate(installment_amounts):
                                 if amount > 0:
                                    payment_due_date = start_date + relativedelta(months=month_offset + 1)
                                    installments_to_create.append(InstallmentPayment(receipt=receipt, payment_date=payment_due_date, amount=amount))
                            if installments_to_create:
                                InstallmentPayment.objects.bulk_create(installments_to_create)

                        receipts_created_total += 1
                        receipts_created_for_branch += 1
                        if receipts_created_total % 500 == 0: # طباعة التقدم كل 500 وصل
                            self.stdout.write(f"تم إنشاء {receipts_created_total} وصل إجمالاً...")

                except (IntegrityError, ValueError, InventoryItem.DoesNotExist, Salesperson.DoesNotExist) as e:
                     # self.stdout.write(self.style.WARNING(f"تخطي وصل بسبب خطأ: {e}"))
                     pass # تقليل الإخراج عند التخطي
                except Exception as e:
                     self.stdout.write(self.style.ERROR(f"حدث خطأ غير متوقع فتوقف إنشاء الوصلات: {e}"))
                     import traceback
                     traceback.print_exc()
                     break # إيقاف الحلقة الداخلية للفرع
            # نهاية حلقة إنشاء 2500 وصل للفرع

            self.stdout.write(f"  - تم إنشاء {receipts_created_for_branch} وصل لـ {branch.name}.")
            if 'e' in locals() and isinstance(locals().get('e'), Exception): break # إيقاف الحلقة الخارجية أيضاً
        # نهاية حلقة الفروع

        self.stdout.write(self.style.SUCCESS(f"اكتملت العملية! تم إنشاء {receipts_created_total} وصل إجمالاً."))