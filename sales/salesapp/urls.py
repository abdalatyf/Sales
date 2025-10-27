from django.urls import path
from . import views

urlpatterns = [
    path('', views.select_branch, name='select_branch'), 
    path('set_branch/<int:branch_id>/', views.set_branch, name='set_branch'),
    # رابط الـ Dashboard (يفضل أن يكون بعد اختيار الفرع مباشرة)
    path('dashboard/', views.dashboard, name='dashboard'),
    # روابط الإعدادات
    path('settings/branches/', views.manage_branches, name='manage_branches'),
    path('settings/salespersons/', views.manage_salespersons, name='manage_salespersons'),
    path('settings/products/', views.manage_products, name='manage_products'),
    path('receipts/edit/<int:receipt_id>/', views.edit_receipt, name='edit_receipt'),
    # --- (هذه هي الروابط التي كانت ناقصة) ---
    # روابط الحذف الجديدة
    path('settings/branches/delete/<int:pk>/', views.delete_branch, name='delete_branch'),
    path('settings/salespersons/delete/<int:pk>/', views.delete_salesperson, name='delete_salesperson'),
    path('settings/products/delete/<int:pk>/', views.delete_product, name='delete_product'),
path('settings/inventory/', views.manage_inventory_movements, name='manage_inventory_movements'),
path('receipts/add/', views.add_receipt, name='add_receipt'),
path('receipts/search/', views.search_receipts, name='search_receipts'),]