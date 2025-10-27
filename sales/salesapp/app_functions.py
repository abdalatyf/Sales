import re

def parse_installment_string(installment_string: str) -> list or str:
    """
    يحلل سلسلة نصية مثل '100*3 + 50*2' إلى قائمة بمبالغ الأقساط.
    يعيد قائمة من الأعداد الصحيحة (المبالغ) أو سلسلة نصية تحتوي على رسالة خطأ.
    """
    installment_string = installment_string.strip()
    if not installment_string:
        return "يجب تحديد نظام القسط بوضوح (مثال: 100*12)."
        
    parts = re.split(r'\s*\+\s*', installment_string)
    installments = []
    
    for part in parts:
        part = part.strip()
        if not part: continue # تخطي الأجزاء الفارغة إذا تم استخدام '++'
        
        # البحث عن صيغة 'Amount*Count'
        match = re.match(r'(\d+)\s*\*\s*(\d+)', part)
        if match:
            amount = int(match.group(1))
            count = int(match.group(2))
            
            if amount <= 0 or count <= 0:
                return f"الكمية أو المبلغ في جزء '{part}' يجب أن يكون أكبر من الصفر."

            for _ in range(count):
                installments.append(amount)
        
        # البحث عن صيغة 'Amount' (قسط واحد)
        elif part.isdigit():
            amount = int(part)
            if amount <= 0:
                return f"المبلغ في جزء '{part}' يجب أن يكون أكبر من الصفر."
            installments.append(amount)

        else:
            return f"صيغة القسط غير صحيحة في الجزء: '{part}'"

    return installments