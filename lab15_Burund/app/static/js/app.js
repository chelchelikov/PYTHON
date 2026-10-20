// Подтверждение удаления и подсчёт суммы заказа на странице оформления
document.querySelectorAll("form[data-confirm]").forEach(form => {
  form.addEventListener("submit", event => {
    if (!confirm(form.dataset.confirm)) event.preventDefault();
  });
});

const orderForm = document.getElementById("order-form");
if (orderForm) {
  const recalc = () => {
    let total = 0;
    orderForm.querySelectorAll("input.qty").forEach(input => {
      const price = parseFloat(input.closest("tr").querySelector("[data-price]").dataset.price);
      total += (parseInt(input.value, 10) || 0) * price;
    });
    document.getElementById("order-total").textContent = total.toFixed(2);
  };
  orderForm.addEventListener("input", recalc);
  recalc();
}
