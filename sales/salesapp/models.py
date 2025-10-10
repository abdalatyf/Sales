from django.db import models

class Branch(models.Model):
    """
    يمثل هذا النموذج فروع الشركة المختلفة.
    """
    name = models.CharField(max_length=100, verbose_name="اسم الفرع")
    def __str__(self): return self.name

class Salesperson(models.Model):
    """
    يمثل مندوبي المبيعات، مع ربط كل مندوب بفرع محدد.
    """
    name = models.CharField(max_length=100, verbose_name="اسم المندوب")
    # --- التغيير: تم ربط المندوب بالفرع ---
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name="الفرع التابع له")
    
    def __str__(self): 
        return f"{self.name} ({self.branch.name})"

class InventoryItem(models.Model):
    """
    يمثل الأصناف في المخزن، حيث يكون لكل صنف مخزون خاص في كل فرع.
    """
    name = models.CharField(max_length=200, verbose_name="اسم الصنف")
    quantity = models.PositiveIntegerField(default=0, verbose_name="الكمية المتاحة")
    # --- التغيير: تم ربط الصنف بمخزن فرع معين ---
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name="مخزن الفرع")

    def __str__(self): 
        return f"{self.name} - فرع {self.branch.name}"

class Receipt(models.Model):
    """
    يمثل إيصالات البيع، ويظل مرتبطاً بالفرع الذي صدر منه.
    """
    receipt_number = models.CharField(max_length=50, unique=True, verbose_name="رقم الوصل")
    customer_name = models.CharField(max_length=150, verbose_name="اسم العميل")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="رقم الهاتف")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    area = models.CharField(max_length=100, blank=True, verbose_name="المنطقة")
    
    sale_date = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ البيع")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="الإجمالي")
    down_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="المقدم")
    
    installment_system = models.CharField(max_length=200, blank=True, verbose_name="وصف نظام القسط")

    salesperson = models.ForeignKey(Salesperson, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="المندوب")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="الفرع")
    
    def __str__(self): 
        return f"وصل {self.receipt_number} للعميل {self.customer_name}"

class SaleItem(models.Model):
    receipt = models.ForeignKey(Receipt, related_name='items', on_delete=models.CASCADE)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT) 
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

class InstallmentPayment(models.Model):
    receipt = models.ForeignKey(Receipt, related_name='payments', on_delete=models.CASCADE)
    payment_date = models.DateField(verbose_name="تاريخ الدفعة")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    is_paid = models.BooleanField(default=False, verbose_name="مدفوع")

