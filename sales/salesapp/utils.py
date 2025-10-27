import re
import datetime as dt
from num2words import num2words

def ed2ad(number_string):
    """
    Converts English digits (str) to Arabic-Indic digits (str).
    """
    numerals = {
        '0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤',
        '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩',
        '.': '٫', # (اختياري) الفاصلة العشرية
    }
    return "".join(numerals.get(digit, digit) for digit in str(number_string))

def get_paydL(selds, nofm):
    """
    Calculates the payment due dates based on the selling date string.
    (Copied from your app_functions.py)
    """
    # selds هو تاريخ البيع كنص (مثل 25/09/2025)
    # nofm هو عدد الشهور
    try:
        dl = re.split('/', selds)
        # (هام) التأكد من أن التاريخ المدخل هو Y/M/D أو D/M/Y
        # بناءً على ملف CSV، التنسيق هو D/M/Y
        seld = dt.date(int(dl[2]), int(dl[1]), int(dl[0]))
    except (ValueError, IndexError):
        # إذا فشل، استخدم تاريخ اليوم كقاعدة
        seld = dt.date.today()

    paydL = []
    
    # نفترض أن أول قسط يبدأ بعد شهر من تاريخ البيع
    # (تعديل: الكود الأصلي الخاص بك يبدأ القسط التالي مباشرة)
    current_date = seld

    for i in range(nofm):
        # إضافة شهر واحد
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:    
            current_date = current_date.replace(month=current_date.month + 1)
        
        # (اختياري) تثبيت يوم الدفع (مثلاً يوم 15)
        # current_date = current_date.replace(day=15)
            
        paydL.append(str(current_date.strftime(r"%d/%m/%Y")))
        
    return paydL

def get_num_to_words_ar(number):
    """
    Converts an integer number to Arabic words.
    """
    try:
        return num2words(int(number), lang='ar')
    except Exception:
        return ""