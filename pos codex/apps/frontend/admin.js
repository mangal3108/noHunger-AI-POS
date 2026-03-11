const notificationsEl = document.getElementById("notifications");
const notifCountEl = document.getElementById("notifCount");
const ordersEl = document.getElementById("orders");
const inventoryEl = document.getElementById("inventory");
const refreshOrdersBtn = document.getElementById("refreshOrders");
const refreshInventoryBtn = document.getElementById("refreshInventory");

let lastUnreadIds = new Set();

function formatDate(value) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function htmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`HTTP ${response.status}: ${body}`);
  }
  return response.json();
}

async function loadNotifications() {
  try {
    const rows = await fetchJson("/admin/notifications?unread_only=false&limit=100");
    const unread = rows.filter((r) => !r.is_read);
    notifCountEl.textContent = `${unread.length} unread`;

    notificationsEl.innerHTML = rows.length
      ? rows.map((row) => {
          const markBtn = row.is_read
            ? `<span class="muted">Read</span>`
            : `<button type="button" data-id="${row.id}">Mark Read</button>`;
          return `
            <article class="notif">
              <strong>${htmlEscape(row.type)}</strong>
              <div>${htmlEscape(row.message)}</div>
              <div class="meta">order: ${htmlEscape(row.order_id || "-")} | ${formatDate(row.created_at)}</div>
              ${markBtn}
            </article>
          `;
        }).join("")
      : "<p class='muted'>No notifications yet.</p>";

    document.querySelectorAll(".notif button[data-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        try {
          await fetchJson(`/admin/notifications/${id}/read`, { method: "POST" });
          await loadNotifications();
        } catch (error) {
          alert(`Failed to mark notification: ${error}`);
        }
      });
    });

    const unreadIds = new Set(unread.map((row) => row.id));
    const newUnread = unread.filter((row) => !lastUnreadIds.has(row.id));
    if (newUnread.length > 0) {
      if ("Notification" in window && Notification.permission === "granted") {
        const top = newUnread[0];
        // Browser notification for new chatbot order events.
        new Notification("New chatbot order", { body: top.message });
      }
    }
    lastUnreadIds = unreadIds;
  } catch (error) {
    notificationsEl.innerHTML = `<p class='muted'>Failed to load notifications: ${htmlEscape(error)}</p>`;
  }
}

async function loadOrders() {
  try {
    const rows = await fetchJson("/admin/orders?limit=50");
    if (!rows.length) {
      ordersEl.innerHTML = "<p class='muted'>No orders yet.</p>";
      return;
    }
    ordersEl.innerHTML = rows.map((row) => {
      const items = Array.isArray(row.items) ? row.items : [];
      const itemLines = items.length
        ? items.map((item) => `
            <li>
              ${htmlEscape(item.item_name)} x${item.quantity}
              - INR ${(Number(item.unit_price) * Number(item.quantity)).toFixed(2)}
            </li>
          `).join("")
        : "<li>No items</li>";

      return `
        <details class="order-details" open>
          <summary>
            <strong>${htmlEscape(row.order_id)}</strong>
            <span class="muted"> | ${htmlEscape(row.order_status)} / ${htmlEscape(row.payment_status)}</span>
            <span class="muted"> | INR ${Number(row.total_amount).toFixed(2)}</span>
          </summary>
          <div class="order-body">
            <p><strong>Session:</strong> ${htmlEscape(row.session_id || "-")}</p>
            <p><strong>Restaurant:</strong> ${htmlEscape(row.restaurant_name || "-")}</p>
            <p><strong>Address:</strong> ${htmlEscape(row.delivery_address || "-")}</p>
            <p><strong>Payment:</strong> ${htmlEscape(row.payment_method || "-")}</p>
            <p><strong>Created:</strong> ${formatDate(row.created_at)}</p>
            <p><strong>Updated:</strong> ${formatDate(row.updated_at)}</p>
            <p><strong>Items:</strong></p>
            <ul>${itemLines}</ul>
          </div>
        </details>
      `;
    }).join("");
  } catch (error) {
    ordersEl.innerHTML = `<p class='muted'>Failed to load orders: ${htmlEscape(error)}</p>`;
  }
}

async function loadInventory() {
  try {
    const rows = await fetchJson("/admin/inventory");
    if (!rows.length) {
      inventoryEl.innerHTML = "<p class='muted'>No inventory rows found.</p>";
      return;
    }

    inventoryEl.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th>Description</th>
            <th>Price</th>
            <th>Stock</th>
            <th>Available</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row, idx) => `
            <tr data-index="${idx}">
              <td>${htmlEscape(row.item_name)}</td>
              <td>${htmlEscape(row.category || "Chef Specials")}</td>
              <td>${htmlEscape(row.description || "-")}</td>
              <td><input type="number" step="0.01" min="0" value="${Number(row.unit_price).toFixed(2)}" data-key="unit_price"></td>
              <td><input type="number" step="1" min="0" value="${row.stock_qty}" data-key="stock_qty"></td>
              <td><input type="checkbox" data-key="is_available" ${row.is_available ? "checked" : ""}></td>
              <td><button class="save-btn" type="button" data-item="${htmlEscape(row.item_name)}">Save</button></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    document.querySelectorAll(".save-btn[data-item]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const row = btn.closest("tr");
        const itemName = btn.getAttribute("data-item");
        const unitPrice = Number(row.querySelector('input[data-key="unit_price"]').value);
        const stockQty = Math.max(0, Math.round(Number(row.querySelector('input[data-key="stock_qty"]').value)));
        const isAvailable = row.querySelector('input[data-key="is_available"]').checked;

        try {
          await fetchJson(`/admin/inventory/${encodeURIComponent(itemName)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              unit_price: unitPrice,
              stock_qty: stockQty,
              is_available: isAvailable,
            }),
          });
          await Promise.all([loadInventory(), loadNotifications()]);
        } catch (error) {
          alert(`Failed to update inventory: ${error}`);
        }
      });
    });
  } catch (error) {
    inventoryEl.innerHTML = `<p class='muted'>Failed to load inventory: ${htmlEscape(error)}</p>`;
  }
}

async function initialLoad() {
  await Promise.all([loadNotifications(), loadOrders(), loadInventory()]);
}

refreshOrdersBtn.addEventListener("click", loadOrders);
refreshInventoryBtn.addEventListener("click", loadInventory);

if ("Notification" in window && Notification.permission === "default") {
  Notification.requestPermission().catch(() => {});
}

initialLoad();
setInterval(() => {
  loadNotifications();
  loadOrders();
}, 5000);
