// Mock Data (Replace with data from Django template)
const MOCK_SALESPERSONS = [
  { id: 1, name: "محمد عبد الله" },
  { id: 2, name: "أحمد محمود" },
];
const MOCK_BRANCHES = [
  { id: 1, name: "فرع القاهرة" },
  { id: 2, name: "فرع الإسكندرية" },
];
const MOCK_INVENTORY_ITEMS = [
  { id: 101, name: "منتج أ" },
  { id: 102, name: "منتج ب" },
  { id: 103, name: "منتج ج" },
];

// Populate Dropdowns
const salespersonSelect = document.getElementById("salesperson");
const branchSelect = document.getElementById("branch");
MOCK_SALESPERSONS.forEach((s) => {
  const option = new Option(s.name, s.id);
  salespersonSelect.add(option);
});
MOCK_BRANCHES.forEach((b) => {
  const option = new Option(b.name, b.id);
  branchSelect.add(option);
});

// Set today's date
document.getElementById("sale_date").valueAsDate = new Date();

const addSaleItemBtn = document.getElementById("addSaleItemBtn");
const saleItemsTableBody = document.getElementById("saleItemsTableBody");
const addInstallmentBtn = document.getElementById("addInstallmentBtn");
const installmentsTableBody = document.getElementById("installmentsTableBody");
const downPaymentInput = document.getElementById("down_payment");

// --- Core Logic ---

function createInventorySelect() {
  const select = document.createElement("select");
  select.className = "form-select inventory-item-select";
  MOCK_INVENTORY_ITEMS.forEach((item) => {
    select.add(new Option(item.name, item.id));
  });
  return select;
}

function addSaleItemRow() {
  const row = saleItemsTableBody.insertRow();
  row.innerHTML = `
        <td>${createInventorySelect().outerHTML}</td>
        <td><input type="number" class="form-control quantity" value="1" min="1"></td>
        <td><input type="number" class="form-control unit-price" value="0.00" min="0" step="0.01"></td>
        <td class="item-total">0.00</td>
        <td><i class="bi bi-trash-fill btn-remove" onclick="removeRow(this)"></i></td>
    `;
  updateAllCalculations();
}

function addInstallmentRow() {
  const row = installmentsTableBody.insertRow();
  row.innerHTML = `
        <td><input type="date" class="form-control installment-date"></td>
        <td><input type="number" class="form-control installment-amount" value="0.00" min="0" step="0.01"></td>
        <td><i class="bi bi-trash-fill btn-remove" onclick="removeRow(this)"></i></td>
    `;
  updateAllCalculations();
}

window.removeRow = function (element) {
  element.closest("tr").remove();
  updateAllCalculations();
};

function updateAllCalculations() {
  let totalAmount = 0;

  // Calculate sale items total
  saleItemsTableBody.querySelectorAll("tr").forEach((row) => {
    const quantity = parseFloat(row.querySelector(".quantity").value) || 0;
    const unitPrice = parseFloat(row.querySelector(".unit-price").value) || 0;
    const itemTotal = quantity * unitPrice;
    row.querySelector(".item-total").textContent = itemTotal.toFixed(2);
    totalAmount += itemTotal;
  });

  document.getElementById("totalAmount").textContent = totalAmount.toFixed(2);
  document.getElementById("grandTotal").textContent = `${totalAmount.toFixed(
    2
  )} ج.م`;

  // Calculate remaining amount
  const downPayment = parseFloat(downPaymentInput.value) || 0;
  const remainingAmount = totalAmount - downPayment;
  document.getElementById("remainingAmount").textContent =
    remainingAmount.toFixed(2);

  // Calculate total installments and check for mismatch
  let totalInstallments = 0;
  installmentsTableBody.querySelectorAll("tr").forEach((row) => {
    const amount =
      parseFloat(row.querySelector(".installment-amount").value) || 0;
    totalInstallments += amount;
  });

  const mismatchAlert = document.getElementById("installment-mismatch-alert");
  document.getElementById("totalInstallmentsAmount").textContent =
    totalInstallments.toFixed(2);
  document.getElementById("remainingAmountForAlert").textContent =
    remainingAmount.toFixed(2);

  if (
    remainingAmount.toFixed(2) !== totalInstallments.toFixed(2) &&
    remainingAmount > 0
  ) {
    mismatchAlert.style.display = "block";
  } else {
    mismatchAlert.style.display = "none";
  }
}

// --- Event Listeners ---
addSaleItemBtn.addEventListener("click", addSaleItemRow);
addInstallmentBtn.addEventListener("click", addInstallmentRow);

document.getElementById("receiptForm").addEventListener("input", function (e) {
  if (
    e.target.classList.contains("quantity") ||
    e.target.classList.contains("unit-price") ||
    e.target.id === "down_payment" ||
    e.target.classList.contains("installment-amount")
  ) {
    updateAllCalculations();
  }
});

// Initial state
addSaleItemRow(); // Start with one item row
