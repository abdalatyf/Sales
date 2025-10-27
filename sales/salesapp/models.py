from django.db import models

# ==========================================================
# القسم الأول: النماذج الأساسية (الإعدادات)
# ==========================================================

class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم الفرع")
    
    def __str__(self): 
        return f"[{self.id}] {self.name}"

class Salesperson(models.Model):
    name = models.CharField(max_length=100, verbose_name="اسم الموظف")
    # --- (تعديل) تم تغيير الحذف إلى "حماية" ---
    # لا يمكن حذف الفرع إذا كان مرتبطاً بموظفين
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, verbose_name="الفرع التابع له")
    
    class Meta:
        unique_together = ('name', 'branch')

    def __str__(self): 
        return f"[{self.id}] {self.name} ({self.branch.name})"

class InventoryItem(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم الصنف")
    quantity = models.PositiveIntegerField(default=0, verbose_name="الكمية المتاحة")
    # --- (تعديل) تم تغيير الحذف إلى "حماية" ---
    # لا يمكن حذف الفرع إذا كان مرتبطاً بمنتجات
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, verbose_name="مخزن الفرع")
    purchase_price = models.PositiveIntegerField(default=0, verbose_name="سعر الشراء")
    salesperson_commission_amount = models.PositiveIntegerField(
        default=0, verbose_name="قيمة عمولة المندوب (مبلغ ثابت)"
    )

    class Meta:
        unique_together = [
            ('name', 'branch'),
        ]

    def __str__(self): 
        return f"[{self.id}] {self.name} - فرع {self.branch.name}"

# ==========================================================
# القسم الثاني: النماذج الخاصة بالبيع والتحصيل
# ==========================================================

class Receipt(models.Model):
    receipt_number = models.PositiveIntegerField(verbose_name="رقم الوصل", unique=True, editable=False)
    customer_name = models.CharField(max_length=150, verbose_name="اسم العميل", blank=True)
    products_text = models.TextField(verbose_name="نص المنتجات (للطباعة)", blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="رقم الهاتف")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    area = models.CharField(max_length=100, blank=True, verbose_name="المنطقة")
    total_amount = models.PositiveIntegerField(default=0, verbose_name="الإجمالي")
    down_payment = models.PositiveIntegerField(default=0, verbose_name="المقدم")
    installment_system = models.CharField(max_length=200, blank=True, verbose_name="وصف نظام القسط")
    
    # --- (تعديل) تم تغيير الحذف إلى "حماية" ---
    # لا يمكن حذف المندوب إذا كان مرتبطاً بوصلات
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT, null=True, blank=True, verbose_name="المندوب (البائع)")
    
    # --- (تعديل) تم تغيير الحذف إلى "حماية" ---
    # لا يمكن حذف الفرع إذا كان مرتبطاً بوصلات
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, verbose_name="الفرع")
    
    sale_year = models.PositiveIntegerField(verbose_name="سنة البيع")
    sale_month = models.PositiveIntegerField(verbose_name="شهر البيع")
    is_cash_sale = models.BooleanField(default=False, verbose_name="بيع كاش؟")
    
    def __str__(self): 
        return f"وصل {self.receipt_number} للعميل {self.customer_name}"

class SaleItem(models.Model):
    # (هنا الحذف يجب أن يكون CASCADE، لأن حذف الوصل يجب أن يحذف مبيعاته)
    receipt = models.ForeignKey(Receipt, related_name='items', on_delete=models.CASCADE, verbose_name="الوصل التابع له")
    
    # (هنا الحماية موجودة، وهذا صحيح)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, verbose_name="الصنف") 
    
    quantity = models.PositiveIntegerField(default=1, verbose_name="الكمية")
    unit_price = models.PositiveIntegerField(verbose_name="سعر الوحدة")

    def __str__(self):
        return f"{self.quantity} x {self.inventory_item.name} @ {self.unit_price}"

class InstallmentPayment(models.Model):
    # (هنا الحذف يجب أن يكون CASCADE، لأن حذف الوصل يجب أن يحذف أقساطه)
    receipt = models.ForeignKey(Receipt, related_name='payments', on_delete=models.CASCADE, verbose_name="الوصل التابع له")
    
    payment_date = models.DateField(verbose_name="تاريخ الدفعة المستقة")
    amount = models.PositiveIntegerField(verbose_name="المبلغ")
    is_paid = models.BooleanField(default=False, verbose_name="مدفوع؟")
    
    # --- (تعديل) تم تغيير الحذف إلى "حماية" ---
    # لا يمكن حذف المندوب/المحصل إذا كان مرتبطاً بأقساط
    collector = models.ForeignKey(
        Salesperson, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        verbose_name="المُحصّل المسؤول"
    )

    def __str__(self):
        return f"قسط {self.amount} - تاريخ {self.payment_date} - (مدفوع: {self.is_paid})"