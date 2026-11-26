    const LS_KEY = "ustabor_standalone_store_v1";
    let store = loadStore();
    let activeCategory = "Barchasi";
    let backendOnline = false;
    let API_BASE = "";
    let adminToken = "";
    let isAdminLogged = false;
    let adminPollTimer = null;

    function loadStore() {
      try {
        const raw = localStorage.getItem(LS_KEY);
        if (raw) return JSON.parse(raw);
      } catch {}
      return {
        services: DEFAULT_SERVICES,
        masters: DEFAULT_MASTERS,
        orders: DEFAULT_ORDERS,
        tgToken: "",
        tgAdminIds: ""
      };
    }
    function saveStore() {
      try { localStorage.setItem(LS_KEY, JSON.stringify(store)); } catch {}
    }

    function fmtUzs(v) { return Number(v || 0).toLocaleString("ru-RU"); }
    function esc(s) { return String(s || "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m])); }
    function showToast(msg) {
      const t = document.getElementById("toast");
      t.textContent = msg; t.classList.add("show");
      setTimeout(() => t.classList.remove("show"), 3200);
    }

    function serviceImg(svc) {
      const slug = svc.slug || "evro-remont";
      if (svc.image_url) {
        if (svc.image_url.startsWith("/static/")) {
          return backendOnline ? (API_BASE + svc.image_url) : ("./app" + svc.image_url);
        }
        return svc.image_url;
      }
      return (backendOnline ? API_BASE + "/static/images/services/" : "./app/static/images/services/") + slug + ".png";
    }

    function fallbackImg(slug) {
      return EMBEDDED_IMAGES[slug] || EMBEDDED_IMAGES["evro-remont"] || "";
    }

    function resolvePhotoUrl(p) {
      if (!p) return "";
      if (p.startsWith("data:") || p.startsWith("http")) return p;
      if (backendOnline && p.startsWith("/")) return API_BASE + p;
      return p;
    }

    async function detectBackend() {
      const candidates = location.protocol === "file:"
        ? [localStorage.getItem("ustabor_api_base"), "http://127.0.0.1:5002", "http://172.50.6.66:5002"].filter(Boolean)
        : ["", "http://127.0.0.1:5002"];

      for (const base of candidates) {
        try {
          const res = await fetch(base + "/api/services");
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data.services) && data.services.length) {
              API_BASE = base;
              backendOnline = true;
              store.services = data.services;
              const badge = document.getElementById("connModeBadge");
              badge.textContent = "Server bilan jonli rejim";
              badge.classList.remove("offline");
              const heroEl = document.getElementById("heroImg");
              if (heroEl) heroEl.src = (API_BASE || "") + "/static/images/hero.jpg";
              renderCategories();
              renderServices();
              fillServiceDropdown();
              return true;
            }
          }
        } catch {}
      }
      return false;
    }

    function switchView(name) {
      ["site", "client", "admin"].forEach(v => {
        document.getElementById("view-" + v).classList.toggle("hidden", v !== name);
        document.getElementById("tab-" + v).classList.toggle("active", v === name);
      });
      if (adminPollTimer) { clearInterval(adminPollTimer); adminPollTimer = null; }
      if (name !== "admin") {
        isAdminLogged = false;
        adminToken = "";
      }
      if (name === "client") renderClientOrders();
      if (name === "admin") {
        // Require login and password every single time Admin Panel is opened
        isAdminLogged = false;
        adminToken = "";
        const uEl = document.getElementById("admUser");
        const pEl = document.getElementById("admPass");
        if (uEl) uEl.value = "";
        if (pEl) pEl.value = "";
        renderAdminView();
        adminPollTimer = setInterval(() => {
          if (backendOnline && isAdminLogged && adminToken && !document.getElementById("view-admin").classList.contains("hidden")) {
            syncAdminDashboard();
          }
        }, 8000);
      }
    }

    function renderCategories() {
      const groups = ["Barchasi", ...new Set(store.services.map(s => s.group_name))];
      document.getElementById("categoryPills").innerHTML = groups.map(g =>
        `<button class="pill ${g === activeCategory ? 'active' : ''}" onclick="setCategory('${esc(g).replace(/'/g, "\\'")}')">${esc(g)}</button>`
      ).join("");
    }
    function setCategory(g) { activeCategory = g; renderCategories(); renderServices(); }

    function renderServices() {
      const q = (document.getElementById("searchInput").value || "").trim().toLowerCase();
      const filtered = store.services.filter(s => {
        const okCat = activeCategory === "Barchasi" || s.group_name === activeCategory;
        const okQ = !q || (s.name + " " + s.description + " " + s.group_name).toLowerCase().includes(q);
        return okCat && okQ;
      });
      const grid = document.getElementById("servicesGrid");
      if (!filtered.length) {
        grid.innerHTML = `<div class="panel-box" style="grid-column:1/-1;text-align:center;">So'rovingiz bo'yicha xizmat topilmadi.</div>`;
        return;
      }
      grid.innerHTML = filtered.map(s => `
        <article class="card">
          <div class="card-img-wrap">
            <img src="${esc(serviceImg(s))}" alt="${esc(s.name)}" loading="lazy" onerror="this.onerror=null;this.src='${fallbackImg(s.slug)}';" />
            <span class="card-badge">${esc(s.group_name)}</span>
            <span class="card-eta">⏱ ~${s.eta_minutes || 45} daq</span>
          </div>
          <div class="card-body">
            <h3 class="card-title">${esc(s.name)}</h3>
            <p class="card-desc">${esc(s.description)}</p>
            <div class="card-foot">
              <div>
                <span class="price-label">Boshlang'ich narx</span>
                <span class="price-val">${fmtUzs(s.price_from)} <small style="color:var(--muted);font-weight:600;">${esc(s.unit || "so'mdan")}</small></span>
              </div>
              <button class="btn-primary" onclick="openOrderModal(${s.id})">Chaqirish →</button>
            </div>
          </div>
        </article>
      `).join("");
    }

    function fillServiceDropdown() {
      document.getElementById("ordServiceId").innerHTML = store.services.map(s =>
        `<option value="${s.id}">${esc(s.name)} (${fmtUzs(s.price_from)} ${esc(s.unit)})</option>`
      ).join("");
    }

    function openOrderModal(svcId) {
      fillServiceDropdown();
      if (svcId) document.getElementById("ordServiceId").value = String(svcId);
      document.getElementById("orderFormSection").classList.remove("hidden");
      document.getElementById("orderDoneSection").classList.add("hidden");
      document.getElementById("orderModal").classList.add("open");
    }
    function closeOrderModal() { document.getElementById("orderModal").classList.remove("open"); }

    function readFileAsDataUrl(file) {
      return new Promise((resolve) => {
        if (!file) return resolve("");
        const fr = new FileReader();
        fr.onload = () => resolve(fr.result || "");
        fr.onerror = () => resolve("");
        fr.readAsDataURL(file);
      });
    }

    async function notifyTelegramDirect(order) {
      if (!store.tgToken || !store.tgAdminIds) return;
      const ids = store.tgAdminIds.split(",").map(x => x.trim()).filter(Boolean);
      const text = `🔔 YANGI ARIZA (${order.order_code})\n🛠 Xizmat: ${order.service_name}\n👤 Mijoz: ${order.client_name}\n📞 Tel: ${order.client_phone}\n📍 Manzil: ${order.district ? order.district + ', ' : ''}${order.address}\n⏰ Vaqt: ${order.preferred_time}\n📝 Izoh: ${order.description || '—'}`;
      for (const chatId of ids) {
        try {
          await fetch(`https://api.telegram.org/bot${encodeURIComponent(store.tgToken)}/sendMessage`, {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({ chat_id: chatId, text })
          });
        } catch {}
      }
    }

    async function submitOrder(e) {
      e.preventDefault();
      const svcId = Number(document.getElementById("ordServiceId").value);
      const svc = store.services.find(s => Number(s.id) === svcId) || store.services[0];
      const photoFile = document.getElementById("ordPhoto").files[0];

      let created = null;
      if (!backendOnline) await detectBackend();
      if (backendOnline) {
        try {
          const fd = new FormData();
          fd.append("service_id", String(svcId));
          fd.append("client_name", document.getElementById("ordName").value.trim());
          fd.append("client_phone", document.getElementById("ordPhone").value.trim());
          fd.append("district", document.getElementById("ordDistrict").value.trim());
          fd.append("address", document.getElementById("ordAddress").value.trim());
          fd.append("description", document.getElementById("ordDesc").value.trim());
          fd.append("preferred_time", document.getElementById("ordTime").value);
          if (photoFile) fd.append("photo", photoFile);
          const res = await fetch(API_BASE + "/api/orders", { method: "POST", body: fd });
          if (res.ok) created = (await res.json()).order;
        } catch {}
      }

      if (!created) {
        const photoData = await readFileAsDataUrl(photoFile);
        const nextNum = 1001 + store.orders.length;
        created = {
          id: Date.now(),
          order_code: "UST-" + nextNum,
          service_id: svcId,
          service_name: svc ? svc.name : "Usta xizmati",
          client_name: document.getElementById("ordName").value.trim(),
          client_phone: document.getElementById("ordPhone").value.trim(),
          district: document.getElementById("ordDistrict").value.trim(),
          address: document.getElementById("ordAddress").value.trim(),
          description: document.getElementById("ordDesc").value.trim(),
          preferred_time: document.getElementById("ordTime").value,
          status: "new",
          master_id: null,
          admin_note: "",
          photo_path: photoData,
          source: "web",
          created_at: new Date().toISOString().slice(0, 16).replace("T", " ")
        };
        store.orders.unshift(created);
        saveStore();
        notifyTelegramDirect(created);
      }

      document.getElementById("clientPhoneSearch").value = created.client_phone;
      document.getElementById("doneOrderCode").textContent = created.order_code;
      document.getElementById("orderFormSection").classList.add("hidden");
      document.getElementById("orderDoneSection").classList.remove("hidden");
      document.getElementById("orderForm").reset();
      showToast("Ariza muvaffaqiyatli yuborildi!");
    }

    async function renderClientOrders() {
      const phoneQ = (document.getElementById("clientPhoneSearch").value || "").trim().replace(/\s+/g, "");
      let orders = store.orders;
      if (backendOnline && phoneQ) {
        try {
          const r = await fetch(API_BASE + "/api/orders/track?phone=" + encodeURIComponent(phoneQ));
          if (r.ok) orders = (await r.json()).orders;
        } catch {}
      } else if (phoneQ) {
        orders = store.orders.filter(o => (o.client_phone || "").replace(/\s+/g, "").includes(phoneQ));
      }

      const wrap = document.getElementById("clientOrdersList");
      if (!orders.length) {
        wrap.innerHTML = `<div class="panel-box" style="text-align:center;">Arizalar topilmadi. Telefon raqamingizni kiriting.</div>`;
        return;
      }
      wrap.innerHTML = orders.map(o => {
        const master = store.masters.find(m => Number(m.id) === Number(o.master_id));
        const masterHtml = o.master_name
          ? `${esc(o.master_name)} (${esc(o.master_phone || '')})`
          : (master ? `${esc(master.full_name)} (${esc(master.phone)})` : "Usta tayinlanishi kutilmoqda...");
        const srcBadge = o.source === "telegram" ? "🤖 Telegram Bot" : "🌐 Sayt";
        return `
          <div class="panel-box">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;">
              <div>
                <strong>${esc(o.order_code)}</strong>
                <span class="status-badge st-${esc(o.status)}" style="margin-left:8px;">${esc(STATUS_LABELS[o.status] || o.status)}</span>
                <span style="margin-left:8px;font-size:0.75rem;color:var(--muted);font-weight:700;">${srcBadge}</span>
                <h3 style="margin:8px 0 4px;font-size:1.1rem;">${esc(o.service_name)}</h3>
                <div style="font-size:0.82rem;color:var(--muted);">📅 ${esc(o.created_at)} • ⏰ ${esc(o.preferred_time)}</div>
              </div>
              <div style="text-align:right;font-size:0.84rem;">
                <div><strong>Mijoz:</strong> ${esc(o.client_name)} (${esc(o.client_phone)})</div>
                <div><strong>Usta:</strong> ${masterHtml}</div>
              </div>
            </div>
            <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;font-size:0.85rem;">
              <div><strong>Manzil:</strong> ${o.district ? esc(o.district) + ', ' : ''}${esc(o.address)}</div>
              ${o.description ? `<div style="margin-top:4px;color:var(--muted);"><strong>Izoh:</strong> ${esc(o.description)}</div>` : ''}
              ${o.admin_note ? `<div style="margin-top:4px;color:var(--primary);"><strong>Operator:</strong> ${esc(o.admin_note)}</div>` : ''}
              ${o.photo_path ? `<div style="margin-top:6px;"><button class="btn-soft" onclick="previewPhoto('${esc(resolvePhotoUrl(o.photo_path))}')">🖼 Rasmni ko'rish</button></div>` : ''}
            </div>
          </div>
        `;
      }).join("");
    }

    function adminHeaders(extra = {}) {
      const h = { ...extra };
      if (adminToken) h["Authorization"] = "Bearer " + adminToken;
      return h;
    }

    async function adminLogin() {
      const u = document.getElementById("admUser").value.trim();
      const p = document.getElementById("admPass").value;
      if (!backendOnline) await detectBackend();
      if (backendOnline) {
        try {
          const res = await fetch(API_BASE + "/api/admin/token", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({ username: u, password: p })
          });
          if (res.ok) {
            const data = await res.json();
            adminToken = data.token;
            isAdminLogged = true;
            await syncAdminDashboard();
            renderAdminView();
            return;
          } else {
            alert("Admin login yoki parol noto'g'ri!");
            return;
          }
        } catch {}
      }
      if (u === "abdulloh" && p === "abdulloh2004") {
        isAdminLogged = true;
        renderAdminView();
      } else {
        alert("Admin login yoki parol noto'g'ri!");
      }
    }

    function adminLogout() {
      isAdminLogged = false;
      adminToken = "";
      const uEl = document.getElementById("admUser");
      const pEl = document.getElementById("admPass");
      if (uEl) uEl.value = "";
      if (pEl) pEl.value = "";
      renderAdminView();
    }

    async function syncAdminDashboard() {
      if (!backendOnline || !adminToken) return;
      try {
        const res = await fetch(API_BASE + "/api/admin/dashboard", {
          headers: adminHeaders()
        });
        if (res.status === 401) {
          adminLogout();
          return;
        }
        if (!res.ok) return;
        const data = await res.json();
        store.orders = data.orders || [];
        store.masters = data.masters || [];
        store.services = data.services || [];
        renderAdminKpis();
        renderAdminOrders();
        renderAdminServices();
        renderAdminMasters();
      } catch {}
    }

    function renderAdminView() {
      if (backendOnline && isAdminLogged && !adminToken) {
        isAdminLogged = false;
      }
      document.getElementById("adminLoginBox").classList.toggle("hidden", isAdminLogged);
      document.getElementById("adminDashboard").classList.toggle("hidden", !isAdminLogged);
      if (!isAdminLogged) return;
      if (backendOnline && adminToken) {
        syncAdminDashboard();
      } else {
        renderAdminKpis();
        renderAdminOrders();
        renderAdminServices();
        renderAdminMasters();
      }
      document.getElementById("cfgBotToken").value = store.tgToken || "";
      document.getElementById("cfgAdminIds").value = store.tgAdminIds || "";
    }

    function switchAdminTab(tab) {
      ["orders", "services", "masters", "settings"].forEach(t => {
        document.getElementById("adm-tab-" + t).classList.toggle("hidden", t !== tab);
      });
    }

    function renderAdminKpis() {
      const total = store.orders.length;
      const newC = store.orders.filter(o => o.status === "new").length;
      const actC = store.orders.filter(o => ["accepted", "on_the_way", "in_progress"].includes(o.status)).length;
      const doneC = store.orders.filter(o => o.status === "completed").length;
      const tgC = store.orders.filter(o => o.source === "telegram").length;
      const webC = total - tgC;
      document.getElementById("adminKpis").innerHTML = `
        <div class="kpi-card"><div class="kpi-label">Jami arizalar</div><div class="kpi-num">${total}</div><div style="font-size:0.75rem;color:var(--muted);">Sayt: ${webC} • Telegram: ${tgC}</div></div>
        <div class="kpi-card"><div class="kpi-label" style="color:#2563eb;">Yangi arizalar</div><div class="kpi-num" style="color:#1d4ed8;">${newC}</div></div>
        <div class="kpi-card"><div class="kpi-label" style="color:#d97706;">Jarayonda</div><div class="kpi-num" style="color:#b45309;">${actC}</div></div>
        <div class="kpi-card"><div class="kpi-label" style="color:#059669;">Bajarilgan</div><div class="kpi-num" style="color:#047857;">${doneC}</div></div>
      `;

      const counts = {};
      store.orders.forEach(o => {
        if (!counts[o.service_name]) counts[o.service_name] = { total: 0, newC: 0 };
        counts[o.service_name].total++;
        if (o.status === "new") counts[o.service_name].newC++;
      });
      document.getElementById("admServiceBreakdown").innerHTML = Object.entries(counts).map(([name, c]) =>
        `<button class="btn-soft" onclick="document.getElementById('admOrderFilterText').value='${esc(name).replace(/'/g,"\\'")}';renderAdminOrders();">${esc(name)} <b>(${c.total})</b> ${c.newC ? `<span style="color:#2563eb;">+${c.newC} yangi</span>` : ''}</button>`
      ).join("") || `<span style="color:var(--muted);font-size:0.84rem;">Hozircha arizalar yo'q</span>`;
    }

    function renderAdminOrders() {
      const q = (document.getElementById("admOrderFilterText").value || "").trim().toLowerCase();
      const st = document.getElementById("admOrderFilterStatus").value;
      const srcEl = document.getElementById("admOrderFilterSource");
      const srcFilter = srcEl ? srcEl.value : "all";
      const rows = store.orders.filter(o => {
        const okSt = st === "all" || o.status === st;
        const okSrc = srcFilter === "all" || o.source === srcFilter;
        const okQ = !q || (o.order_code + " " + o.service_name + " " + o.client_name + " " + o.client_phone + " " + o.address).toLowerCase().includes(q);
        return okSt && okSrc && okQ;
      });
      const tbody = document.getElementById("admOrdersTbody");
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--muted);">Arizalar topilmadi.</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(o => {
        const mOpts = `<option value="">-- Tanlanmagan --</option>` + store.masters.map(m =>
          `<option value="${m.id}" ${Number(o.master_id) === Number(m.id) ? "selected" : ""}>${esc(m.full_name)}</option>`
        ).join("");
        const sOpts = Object.entries(STATUS_LABELS).map(([k, v]) =>
          `<option value="${k}" ${o.status === k ? "selected" : ""}>${esc(v)}</option>`
        ).join("");
        const srcTag = o.source === "telegram"
          ? `<span style="display:inline-block;margin-top:3px;padding:2px 6px;border-radius:6px;background:#e0f2fe;color:#0369a1;font-size:0.7rem;font-weight:800;">🤖 Telegram</span>`
          : `<span style="display:inline-block;margin-top:3px;padding:2px 6px;border-radius:6px;background:#f1f5f9;color:#475569;font-size:0.7rem;font-weight:800;">🌐 Sayt</span>`;
        return `
          <tr>
            <td><strong>${esc(o.order_code)}</strong><div>${srcTag}</div><div style="font-size:0.74rem;color:var(--muted);margin-top:2px;">${esc(o.created_at)}</div></td>
            <td><strong>${esc(o.service_name)}</strong><div style="font-size:0.74rem;color:var(--muted);">⏰ ${esc(o.preferred_time)}</div></td>
            <td>
              <strong>${esc(o.client_name)}</strong><div style="color:var(--primary);font-weight:700;">${esc(o.client_phone)}</div>
              <div style="font-size:0.78rem;color:var(--muted);">${o.district ? esc(o.district)+', ' : ''}${esc(o.address)}</div>
              ${o.description ? `<div style="font-size:0.76rem;font-style:italic;">"${esc(o.description)}"</div>` : ''}
              ${o.photo_path ? `<button class="btn-soft" style="margin-top:4px;padding:3px 8px;font-size:0.72rem;" onclick="previewPhoto('${esc(resolvePhotoUrl(o.photo_path))}')">🖼 Rasm</button>` : ''}
            </td>
            <td>
              <select style="padding:5px 8px;border:1px solid var(--border);border-radius:8px;font-size:0.78rem;" onchange="updateAdminOrder(${o.id}, {master_id: this.value ? Number(this.value) : null})">${mOpts}</select>
              <input type="text" value="${esc(o.admin_note || '')}" placeholder="Izoh..." onblur="updateAdminOrder(${o.id}, {admin_note: this.value})" style="display:block;margin-top:5px;padding:4px 8px;border:1px solid var(--border);border-radius:8px;font-size:0.75rem;width:150px;" />
            </td>
            <td>
              <span class="status-badge st-${esc(o.status)}" style="margin-bottom:4px;">${esc(STATUS_LABELS[o.status] || o.status)}</span>
              <select style="display:block;padding:5px 8px;border:1px solid var(--border);border-radius:8px;font-size:0.78rem;" onchange="updateAdminOrder(${o.id}, {status: this.value})">${sOpts}</select>
            </td>
            <td><button class="btn-danger" onclick="deleteAdminOrder(${o.id})">O'chirish</button></td>
          </tr>
        `;
      }).join("");
    }

    async function updateAdminOrder(id, patch) {
      if (backendOnline && adminToken) {
        const res = await fetch(API_BASE + `/api/admin/orders/${id}`, {
          method: "PATCH",
          headers: adminHeaders({"Content-Type": "application/json"}),
          body: JSON.stringify(patch)
        });
        if (res.ok) {
          showToast("Ariza yangilandi!");
          await syncAdminDashboard();
          return;
        }
      }
      const idx = store.orders.findIndex(o => o.id === id);
      if (idx === -1) return;
      store.orders[idx] = { ...store.orders[idx], ...patch };
      saveStore();
      renderAdminKpis();
      renderAdminOrders();
      showToast("Ariza yangilandi");
    }

    async function deleteAdminOrder(id) {
      if (!confirm("Arizani o'chirmoqchimisiz?")) return;
      if (backendOnline && adminToken) {
        const res = await fetch(API_BASE + `/api/admin/orders/${id}`, {
          method: "DELETE",
          headers: adminHeaders()
        });
        if (res.ok) {
          showToast("Ariza o'chirildi");
          await syncAdminDashboard();
          return;
        }
      }
      store.orders = store.orders.filter(o => o.id !== id);
      saveStore();
      renderAdminKpis();
      renderAdminOrders();
    }

    function renderAdminServices() {
      document.getElementById("admServicesList").innerHTML = store.services.map(s => `
        <div class="panel-box" style="margin:0;display:flex;gap:12px;align-items:center;">
          <img src="${esc(serviceImg(s))}" onerror="this.onerror=null;this.src='${fallbackImg(s.slug)}';" style="width:72px;height:72px;object-fit:cover;border-radius:12px;" />
          <div style="flex:1;min-width:0;">
            <strong style="display:block;">${esc(s.name)}</strong>
            <span style="font-size:0.75rem;color:var(--muted);">${esc(s.group_name)}</span>
            <div style="font-weight:800;font-size:0.84rem;margin-top:4px;">${fmtUzs(s.price_from)} ${esc(s.unit)}</div>
          </div>
        </div>
      `).join("");
    }

    async function addService() {
      const name = document.getElementById("newSvcName").value.trim();
      if (!name) return alert("Xizmat nomini kiriting");
      const group_name = document.getElementById("newSvcGroup").value.trim() || "Qo'shimcha xizmatlar";
      const description = document.getElementById("newSvcDesc").value.trim() || "Professional usta xizmati.";
      const price_from = Number(document.getElementById("newSvcPrice").value) || 100000;

      if (backendOnline && adminToken) {
        const fd = new FormData();
        fd.append("name", name);
        fd.append("group_name", group_name);
        fd.append("description", description);
        fd.append("price_from", String(price_from));
        const res = await fetch(API_BASE + "/api/admin/services", {
          method: "POST",
          headers: adminHeaders(),
          body: fd
        });
        if (res.ok) {
          await syncAdminDashboard();
          renderCategories();
          renderServices();
          document.getElementById("newSvcName").value = "";
          document.getElementById("newSvcDesc").value = "";
          showToast("Yangi xizmat bazaga qo'shildi!");
          return;
        }
      }
      store.services.unshift({
        id: Date.now(),
        slug: "evro-remont",
        name,
        group_name,
        description,
        price_from,
        unit: "so'mdan",
        eta_minutes: 45
      });
      saveStore();
      renderCategories();
      renderServices();
      renderAdminServices();
      document.getElementById("newSvcName").value = "";
      document.getElementById("newSvcDesc").value = "";
      showToast("Yangi xizmat qo'shildi!");
    }

    function renderAdminMasters() {
      document.getElementById("admMastersList").innerHTML = store.masters.map(m => `
        <div class="panel-box" style="margin:0;">
          <strong>${esc(m.full_name)}</strong>
          <div style="font-size:0.8rem;color:var(--muted);margin:4px 0;">${esc(m.specialty)}</div>
          <div style="font-size:0.8rem;">📞 ${esc(m.phone)} • 📍 ${esc(m.district)}</div>
          <button class="btn-danger" style="margin-top:10px;" onclick="deleteMaster(${m.id})">O'chirish</button>
        </div>
      `).join("");
    }

    async function addMaster() {
      const full_name = document.getElementById("newMasterName").value.trim();
      const phone = document.getElementById("newMasterPhone").value.trim();
      if (!full_name || !phone) return alert("Ism va telefonni kiriting");
      const specialty = document.getElementById("newMasterSpec").value.trim() || "Umumiy usta";
      const district = document.getElementById("newMasterDist").value.trim() || "Barcha tumanlar";

      if (backendOnline && adminToken) {
        const res = await fetch(API_BASE + "/api/admin/masters", {
          method: "POST",
          headers: adminHeaders({"Content-Type":"application/json"}),
          body: JSON.stringify({ full_name, phone, specialty, district })
        });
        if (res.ok) {
          await syncAdminDashboard();
          document.getElementById("newMasterName").value = "";
          document.getElementById("newMasterPhone").value = "";
          showToast("Yangi usta bazaga qo'shildi!");
          return;
        }
      }
      store.masters.push({ id: Date.now(), full_name, phone, specialty, district, status: "available" });
      saveStore();
      renderAdminMasters();
      document.getElementById("newMasterName").value = "";
      document.getElementById("newMasterPhone").value = "";
      showToast("Yangi usta qo'shildi!");
    }

    async function deleteMaster(id) {
      if (backendOnline && adminToken) {
        const res = await fetch(API_BASE + `/api/admin/masters/${id}`, {
          method: "DELETE",
          headers: adminHeaders()
        });
        if (res.ok) { await syncAdminDashboard(); return; }
      }
      store.masters = store.masters.filter(m => m.id !== id);
      saveStore();
      renderAdminMasters();
    }

    async function saveTgConfig() {
      const token = document.getElementById("cfgBotToken").value.trim();
      const adminIds = document.getElementById("cfgAdminIds").value.trim();
      if (backendOnline && adminToken) {
        const res = await fetch(API_BASE + "/api/admin/bot/config", {
          method: "POST",
          headers: adminHeaders({"Content-Type":"application/json"}),
          body: JSON.stringify({ telegram_bot_token: token, admin_telegram_ids: adminIds })
        });
        if (res.ok) {
          showToast("Telegram bot serverda saqlandi va ishga tushirildi!");
          return;
        }
      }
      store.tgToken = token;
      store.tgAdminIds = adminIds;
      saveStore();
      showToast("Telegram sozlamalari saqlandi!");
    }

    function previewPhoto(src) {
      document.getElementById("photoViewImg").src = src;
      document.getElementById("photoViewModal").classList.add("open");
    }

    renderCategories();
    renderServices();
    fillServiceDropdown();
    detectBackend();
  </script>
</body>
</html>
