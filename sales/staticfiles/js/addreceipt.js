document.addEventListener('DOMContentLoaded', function () {
const arabicNumerals = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];

function toArabicNumerals(number) {
    if (number === null || number === undefined) return '';
    let numStr = String(number);
    let arabicStr = '';
    for (let i = 0; i < numStr.length; i++) {
        let char = numStr[i];
        if (char >= '0' && char <= '9') {
            arabicStr += arabicNumerals[parseInt(char)];
        } else {
            arabicStr += char; // Keep non-digit characters like '.'
        }
    }
    return arabicStr;
}

const currentDate = new Date();
document.querySelector('input[name="sale_month"]').value = toArabicNumerals(currentDate.getMonth() + 1);
document.querySelector('input[name="sale_year"]').value = toArabicNumerals(currentDate.getFullYear());

const addItemBtn = document.getElementById('add-item-btn');
const saleItemsTbody = document.getElementById('sale-items-tbody');
const downPaymentInput = document.getElementById('down_payment');

function calculateTotals() {
    let totalAmount = 0;
    saleItemsTbody.querySelectorAll('tr').forEach(row => {
        const quantity = parseFloat(row.querySelector('.item-quantity').value) || 0;
        const price = parseFloat(row.querySelector('.item-price').value) || 0;
        const itemTotal = quantity * price;
        row.querySelector('.item-total').textContent = toArabicNumerals(itemTotal.toFixed(2));
        totalAmount += itemTotal;
    });

    document.getElementById('summary-total').textContent = `${toArabicNumerals(totalAmount.toFixed(2))} جنيه`;

    // Remaining amount calculation is removed
}

addItemBtn.addEventListener('click', () => {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td><input type="text" name="item_name[]" class="form-control form-control-sm" placeholder="اسم المنتج"></td>
        <td><input type="number" name="item_quantity[]" class="form-control form-control-sm item-quantity" value="1" min="1"></td>
        <td><input type="number" name="item_price[]" class="form-control form-control-sm item-price" step="0.01" min="0"></td>
        <td><span class="item-total fw-bold">٠.٠٠</span></td>
        <td><button type="button" class="btn btn-danger btn-sm remove-btn"><i class="fa-solid fa-trash"></i></button></td>
    `;
    row.querySelector('.item-quantity').value = '١';
    saleItemsTbody.appendChild(row);
});

document.body.addEventListener('click', e => {
    if (e.target.closest('.remove-btn')) {
        e.target.closest('tr').remove();
        calculateTotals();
    }
});

document.body.addEventListener('input', e => {
    if (e.target.classList.contains('item-quantity') || e.target.classList.contains('item-price') || e.target.id === 'down_payment') {
        calculateTotals();
    }
});

// Event listener for Tab key
saleItemsTbody.addEventListener('keydown', e => {
    if (e.key === 'Tab' && !e.shiftKey) {
        const currentRow = e.target.closest('tr');
        // Check if Tab was pressed on the price input of the last row
        if (e.target.classList.contains('item-price') && currentRow === saleItemsTbody.lastElementChild) {
            // Prevent default Tab behavior (moving to next element on page)
            e.preventDefault();
            
            // Simulate a click on the "Add Item" button
            addItemBtn.click();
            
            // Focus on the first input of the newly added row
            const newRow = saleItemsTbody.lastElementChild;
            if (newRow) {
                newRow.querySelector('input[name="item_name[]"]').focus();
            }
        }
    }
});
calculateTotals();
    });