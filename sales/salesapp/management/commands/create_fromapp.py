import csv
import re
import datetime
from dateutil.relativedelta import relativedelta
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from salesapp.models import Branch, Salesperson, InventoryItem, Receipt, SaleItem, InstallmentPayment
from django.db.models import ProtectedError, F, Max

# -------------------------------------------------------------------
# (1) دالة تحليل الأقساط
# -------------------------------------------------------------------
def parse_installment_string(ps_string):
    """
    تحليل نص نظام القسط (مثل "10*100 + 2*200")
    وتحويله إلى قائمة بالمبالغ الشهرية.
    """
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


# -------------------------------------------------------------------
# (2) السكربت الرئيسي
# -------------------------------------------------------------------
class Command(BaseCommand):
    help = 'Imports data from the old Cheks.csv file into the new database structure.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("بدء عملية استيراد البيانات من Cheks.csv..."))

        # --- مسح البيانات القديمة (لبدء صفحة نظيفة) ---
        self.stdout.write("  - مسح البيانات القديمة من قاعدة البيانات...")
        try:
            # الترتيب مهم بسبب الحماية
            InstallmentPayment.objects.all().delete()
            SaleItem.objects.all().delete()
            Receipt.objects.all().delete()
            InventoryItem.objects.all().delete()
            Salesperson.objects.all().delete()
            Branch.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("  - تم مسح البيانات القديمة بنجاح."))
        except ProtectedError as e:
             self.stdout.write(self.style.ERROR(f"خطأ أثناء مسح البيانات: {e}"))
             return

        # (!!!) تأكد من أن ملف Cheks.csv موجود في نفس المجلد الذي تشغل منه الأمر
        csv_file_path = 'Cheks.csv' 
        
        created_receipts = 0
        created_installments = 0
        skipped_rows = 0
        branches_cache = {}
        salespersons_cache = {}
        dummy_products_cache = {}

        try:
            with open(csv_file_path, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    try:
                        with transaction.atomic(): # معاملة واحدة لكل صف
                            # 1. تنظيف البيانات
                            area_name = row.get('Area', '').strip()
                            employee_name = row.get('EmployeeName', '').strip()
                            receipt_id_str = row.get('ID', '').strip()
                            price_str = row.get('Price', '0').strip()
                            retainer_str = row.get('Retainer', '0').strip()
                            products_text_data = row.get('Products', '').strip() # (جديد)

                            if not area_name or not employee_name or not receipt_id_str or not price_str:
                                skipped_rows += 1
                                continue
                                
                            try: price = int(price_str)
                            except ValueError: price = 0
                            
                            try: retainer = int(retainer_str)
                            except ValueError: retainer = 0
                            
                            try: receipt_id_int = int(receipt_id_str)
                            except ValueError: skipped_rows += 1; continue
                            
                            # 2. جلب أو إنشاء الفرع
                            if area_name not in branches_cache:
                                branch, _ = Branch.objects.get_or_create(name=area_name)
                                branches_cache[area_name] = branch
                            branch = branches_cache[area_name]

                            # 3. جلب أو إنشاء الموظف
                            if (employee_name, branch.id) not in salespersons_cache:
                                sp, _ = Salesperson.objects.get_or_create(name=employee_name, branch=branch)
                                salespersons_cache[(employee_name, branch.id)] = sp
                            salesperson = salespersons_cache[(employee_name, branch.id)]

                            # 4. جلب أو إنشاء المنتج الافتراضي
                            if branch.id not in dummy_products_cache:
                                dummy, _ = InventoryItem.objects.get_or_create(
                                    name="منتج مستورد (النظام القديم)", branch=branch,
                                    defaults={'quantity': 9999, 'purchase_price': 0, 'salesperson_commission_amount': 0}
                                )
                                dummy_products_cache[branch.id] = dummy
                            dummy_product = dummy_products_cache[branch.id]
                            
                            # 5. تحليل التاريخ
                            try:
                                selling_date_obj = datetime.datetime.strptime(row.get('SellingDate', ''), "%d/%m/%Y").date()
                                sale_year = selling_date_obj.year
                                sale_month = selling_date_obj.month
                                first_payment_start_date = selling_date_obj.replace(day=15)
                            except ValueError:
                                skipped_rows += 1; continue
                                
                            # 6. إنشاء الوصل
                            installment_system = row.get('InstSystem', '').strip()
                            is_cash = (not installment_system) or (installment_system.lower() == 'كاش')
                            
                            receipt = Receipt.objects.create(
                                id=receipt_id_int, # استخدام الـ ID القديم
                                receipt_number=receipt_id_int, # (تم التعديل) استخدام رقم صحيح
                                branch=branch,
                                salesperson=salesperson,
                                customer_name=row.get('CName', ''),
                                products_text=products_text_data, # (جديد) حفظ نص المنتجات
                                phone_number=row.get('PhoneNum', ''),
                                address=row.get('CAddress', ''),
                                area=row.get('Zone', ''),
                                total_amount=price,
                                down_payment=retainer if not is_cash else price,
                                installment_system=installment_system,
                                sale_year=sale_year,
                                sale_month=sale_month,
                                is_cash_sale=is_cash
                            )
                            created_receipts += 1
                            
                            # 7. إنشاء بند المبيعات
                            SaleItem.objects.create(
                                receipt=receipt, inventory_item=dummy_product,
                                quantity=1, unit_price=price
                            )
                            
                            # 8. إنشاء الأقساط
                            if not is_cash:
                                installment_amounts = parse_installment_string(installment_system)
                                if isinstance(installment_amounts, list) and installment_amounts:
                                    installments_to_create = []
                                    for i, amount in enumerate(installment_amounts):
                                        if amount > 0:
                                            payment_due_date = first_payment_start_date + relativedelta(months=i + 1)
                                            installments_to_create.append(InstallmentPayment(
                                                receipt=receipt, payment_date=payment_due_date, amount=amount
                                            ))
                                    if installments_to_create:
                                        InstallmentPayment.objects.bulk_create(installments_to_create)
                                        created_installments += len(installments_to_create)

                    except IntegrityError as e:
                         skipped_rows += 1
                    except Exception as e:
                         self.stdout.write(self.style.ERROR(f"  - فشل معالجة الصف {receipt_id_str}: {e}"))
                         skipped_rows += 1
                
                if reader.line_num % 100 == 0:
                     self.stdout.write(f"  ... تمت معالجة {reader.line_num} صف...")
                     
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"خطأ: لم يتم العثور على الملف '{csv_file_path}'. يرجى وضعه بجوار 'manage.py'."))
            return
        except Exception as e:
             self.stdout.write(self.style.ERROR(f"حدث خطأ فادح أثناء قراءة الملف: {e}"))
             return

        self.stdout.write(self.style.SUCCESS("="*30))
        self.stdout.write(self.style.SUCCESS(f"اكتمل الاستيراد بنجاح!"))
        self.stdout.write(f"  - تم إنشاء {created_receipts} وصل جديد.")
        self.stdout.write(f"  - تم إنشاء {created_installments} قسط جديد.")
        self.stdout.write(f"  - تم تخطي {skipped_rows} صف (بسبب أخطاء أو تكرار).")