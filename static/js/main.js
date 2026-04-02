function formatNumber(num) {
  const n = Number(num || 0);
  return n.toFixed(2);
}

function bindInvoiceForm() {
  const form = document.getElementById("invoice-form");
  if (!form) return;

  const itemsTable = document.getElementById("items-table");
  const addBtn = document.getElementById("add-item-btn");
  const rowTemplate = document.getElementById("item-row-template");

  function rowLineTotal(row) {
    const qty = parseFloat(row.querySelector('input[name="item_quantity[]"]').value || 0);
    const price = parseFloat(row.querySelector('input[name="item_unit_price[]"]').value || 0);
    const total = qty * price;
    row.querySelector(".line-total-display").value = formatNumber(total);
    return total;
  }

  function collectItems() {
    const rows = [...itemsTable.querySelectorAll("tbody tr.item-row")];
    return rows.map((row) => ({
      description: row.querySelector('input[name="item_description[]"]').value,
      quantity: row.querySelector('input[name="item_quantity[]"]').value,
      unit_price: row.querySelector('input[name="item_unit_price[]"]').value
    }));
  }

  async function updatePreview() {
    [...itemsTable.querySelectorAll("tbody tr.item-row")].forEach(rowLineTotal);

    const payload = {
      items: collectItems()
    };

    try {
      const resp = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      document.getElementById("subtotal-preview").textContent = formatNumber(data.subtotal);
      document.getElementById("total-preview").textContent = formatNumber(data.total);
    } catch (err) {
      console.error("Preview update failed", err);
    }
  }

  function attachRowEvents(scope = document) {
    scope.querySelectorAll(".remove-row").forEach((btn) => {
      btn.onclick = (e) => {
        const rows = itemsTable.querySelectorAll("tbody tr.item-row");
        if (rows.length <= 1) {
          const row = btn.closest("tr");
          row.querySelectorAll("input").forEach((input) => {
            if (input.type === "number") input.value = input.name.includes("quantity") ? "1" : "0";
            else if (!input.readOnly) input.value = "";
          });
        } else {
          btn.closest("tr").remove();
        }
        updatePreview();
      };
    });

    scope.querySelectorAll('input[name="item_quantity[]"], input[name="item_unit_price[]"], input[name="item_description[]"]').forEach((input) => {
      input.oninput = updatePreview;
    });
  }

  addBtn?.addEventListener("click", () => {
    const fragment = rowTemplate.content.cloneNode(true);
    itemsTable.querySelector("tbody").appendChild(fragment);
    attachRowEvents(itemsTable);
    updatePreview();
  });

  attachRowEvents(form);
  updatePreview();
}

document.addEventListener("DOMContentLoaded", bindInvoiceForm);
