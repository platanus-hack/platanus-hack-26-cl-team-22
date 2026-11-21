"use strict";

(function () {
  const DATA_USAGE_PRESETS = Object.freeze({
    LIGHT: 3,
    NORMAL: 10,
    INTENSE: 30
  });

  const DATA_PRESET_LABELS = Object.freeze({
    LIGHT: "Ligero",
    NORMAL: "Normal",
    INTENSE: "Intenso"
  });

  const SCENARIO_ORDER = Object.freeze([
    "ZERO_FRICTION",
    "BALANCED",
    "LOCAL_OPTIMIZED"
  ]);

  const SCENARIO_LABELS = Object.freeze({
    ZERO_FRICTION: "Cero Fricción",
    BALANCED: "Balanceado",
    LOCAL_OPTIMIZED: "Optimizado Local"
  });

  const SCENARIO_DESCRIPTIONS = Object.freeze({
    ZERO_FRICTION: "Mínima fricción operativa e inmediatez total.",
    BALANCED: "Cambia de opción solo cuando el ahorro justifica la fricción.",
    LOCAL_OPTIMIZED: "Menor costo total usando alternativas locales."
  });

  const CATEGORY_SECTIONS = Object.freeze([
    {
      key: "connectivity",
      title: "Conectividad",
      subtitle: "Planes móviles, eSIM de viaje y chips locales.",
      categories: [{ code: "CONNECTIVITY", label: null }]
    },
    {
      key: "transport",
      title: "Transporte",
      subtitle: "Traslado desde el aeropuerto y movilidad urbana diaria.",
      categories: [
        { code: "AIRPORT_TRANSFER", label: "Aeropuerto" },
        { code: "URBAN_TRANSIT", label: "Transporte urbano" }
      ]
    },
    {
      key: "day_trips",
      title: "Escapadas",
      subtitle: "Excursiones de un día y recorridos cercanos.",
      categories: [{ code: "DAY_TRIP", label: null }]
    },
    {
      key: "dining",
      title: "Comida",
      subtitle: "Opciones diarias de alimentación según estilo de consumo.",
      categories: [{ code: "DINING", label: null }]
    },
    {
      key: "payments",
      title: "Pagos y divisas",
      subtitle: "Cambio de moneda y uso de tarjetas o efectivo.",
      categories: [{ code: "CURRENCY_EXCHANGE", label: null }]
    }
  ]);

  const CATEGORY_LABELS = Object.freeze({
    CONNECTIVITY: "Conectividad",
    AIRPORT_TRANSFER: "Transporte — Aeropuerto",
    URBAN_TRANSIT: "Transporte — Urbano",
    DAY_TRIP: "Escapadas",
    DINING: "Comida",
    CURRENCY_EXCHANGE: "Pagos y divisas"
  });

  const DEVICE_LABELS = Object.freeze({
    "esim-only": "Solo eSIM",
    "physical-only": "Solo SIM física",
    "dual": "Ambas"
  });

  const TOLERANCE_LABELS = Object.freeze({
    LOW: "Prefiero lo simple",
    MEDIUM: "Equilibrio",
    HIGH: "Me da igual el esfuerzo"
  });

  const SIM_TYPE_LABELS = Object.freeze({
    ESIM: "eSIM",
    PHYSICAL_SIM: "Chip físico",
    NOT_APPLICABLE: "No aplica"
  });

  const REJECTION_REASON_LABELS = Object.freeze({
    CITY_MISMATCH: "No corresponde a la ciudad seleccionada",
    UNSUPPORTED_PHYSICAL_SIM: "El teléfono no tiene ranura para chip físico",
    UNSUPPORTED_ESIM: "El teléfono no soporta eSIM",
    INVALID_CONNECTIVITY_SIM_TYPE: "Tipo de SIM inválido para conectividad",
    REQUIRES_LOCAL_ID: "Requiere documento de identidad local (RUT)",
    PAYMENT_METHOD_INCOMPATIBLE: "Método de pago incompatible",
    INSUFFICIENT_DATA_QUOTA: "Cuota de datos insuficiente para el viaje",
    INCOMPATIBLE_WITH_SELECTED: "Incompatible con otra opción seleccionada"
  });

  const FRESHNESS_LABELS = Object.freeze({
    STALE: "Dato desactualizado (61–180 días)",
    EXPIRED: "Dato vencido (>180 días)"
  });

  const FIELD_SELECTORS = Object.freeze({
    city: "#city-select",
    days: "#days-input",
    data_gb: "#data-gb-input",
    has_local_id: "#has-local-id-input",
    device: 'input[name="device"]',
    tolerance: 'input[name="tolerance"]'
  });

  function clearChildren(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function createElement(tag, className, text) {
    const el = document.createElement(tag);
    if (className) {
      el.className = className;
    }
    if (text !== undefined && text !== null) {
      el.textContent = String(text);
    }
    return el;
  }

  function formatUsd(amount) {
    const num = Number(amount);
    if (!Number.isFinite(num)) {
      return "$0.00 USD";
    }
    return "$" + num.toFixed(2) + " USD";
  }

  function formatLocal(amount, currency) {
    const code = currency || "CLP";
    const num = Number(amount);
    if (!Number.isFinite(num)) {
      return "0 " + code;
    }
    const rounded = Math.round(num);
    if (Math.abs(num - rounded) < 0.005) {
      return rounded.toLocaleString("es-CL") + " " + code;
    }
    return num.toFixed(2) + " " + code;
  }

  function categoryLabel(code) {
    return CATEGORY_LABELS[code] || code;
  }

  function reasonLabel(code) {
    return REJECTION_REASON_LABELS[code] || code;
  }

  function simTypeLabel(code) {
    return SIM_TYPE_LABELS[code] || code;
  }

  function scenarioLabel(scenario) {
    if (!scenario) {
      return "";
    }
    return SCENARIO_LABELS[scenario.scenario_type] || scenario.label || scenario.scenario_type;
  }

  function getCheckedRadioValue(name) {
    const checked = document.querySelector('input[name="' + name + '"]:checked');
    return checked ? checked.value : "";
  }

  function clearFieldErrors() {
    Object.keys(FIELD_SELECTORS).forEach(function (fieldKey) {
      const nodes = document.querySelectorAll(FIELD_SELECTORS[fieldKey]);
      nodes.forEach(function (el) {
        el.removeAttribute("aria-invalid");
      });
    });
  }

  function focusInvalidField(fieldName) {
    if (!fieldName || !FIELD_SELECTORS[fieldName]) {
      return;
    }
    if (fieldName === "data_gb") {
      const details = document.getElementById("manual-data-details");
      if (details) {
        details.open = true;
      }
    }
    const selector = FIELD_SELECTORS[fieldName];
    const target =
      document.querySelector(selector + ":checked") ||
      document.querySelector(selector);
    if (target) {
      target.setAttribute("aria-invalid", "true");
      target.focus();
    }
  }

  function clearPreviousResults() {
    const warningBanner = document.getElementById("warning-banner");
    if (warningBanner) {
      clearChildren(warningBanner);
      warningBanner.hidden = true;
    }

    const summarySection = document.getElementById("summary-section");
    const summaryGrid = document.getElementById("summary-scenarios-grid");
    const profileSummary = document.getElementById("profile-summary");
    if (summaryGrid) {
      clearChildren(summaryGrid);
    }
    if (profileSummary) {
      profileSummary.textContent = "";
    }
    if (summarySection) {
      summarySection.hidden = true;
    }

    const categoriesSection = document.getElementById("categories-section");
    const categoriesContainer = document.getElementById("categories-container");
    if (categoriesContainer) {
      clearChildren(categoriesContainer);
    }
    if (categoriesSection) {
      categoriesSection.hidden = true;
    }

    const rejectedSection = document.getElementById("rejected-section");
    const rejectedTbody = document.getElementById("rejected-tbody");
    const rejectedCount = document.getElementById("rejected-count");
    const rejectedEmpty = document.getElementById("rejected-empty");
    const rejectedTableWrapper = document.getElementById("rejected-table-wrapper");
    if (rejectedTbody) {
      clearChildren(rejectedTbody);
    }
    if (rejectedCount) {
      rejectedCount.textContent = "0";
    }
    if (rejectedEmpty) {
      rejectedEmpty.hidden = true;
    }
    if (rejectedTableWrapper) {
      rejectedTableWrapper.hidden = true;
    }
    if (rejectedSection) {
      rejectedSection.hidden = true;
    }
  }

  function showError(message, fieldName) {
    clearPreviousResults();
    clearFieldErrors();

    const banner = document.getElementById("error-banner");
    clearChildren(banner);
    const title = createElement("h3", null, "No se pudo ejecutar la simulación");
    const detail = createElement("p", null, message);
    banner.appendChild(title);
    banner.appendChild(detail);
    banner.hidden = false;

    focusInvalidField(fieldName);
  }

  function hideError() {
    const banner = document.getElementById("error-banner");
    clearChildren(banner);
    banner.hidden = true;
    clearFieldErrors();
  }

  function renderWarnings(data) {
    const banner = document.getElementById("warning-banner");
    clearChildren(banner);

    const messages = [];
    const unverifiedIds = Array.isArray(data.unverified_option_ids)
      ? data.unverified_option_ids
      : [];
    const staleIds = Array.isArray(data.stale_option_ids) ? data.stale_option_ids : [];
    const expiredIds = Array.isArray(data.expired_option_ids) ? data.expired_option_ids : [];
    const cityInfo = data.city || {};

    if (data.unverified || cityInfo.unverified || unverifiedIds.length > 0) {
      if (cityInfo.unverified && unverifiedIds.length > 0) {
        messages.push(
          "Advertencia de verificación: los metadatos de la ciudad y " +
            unverifiedIds.length +
            " opción(es) del catálogo no tienen fuente o fecha de verificación confirmada (" +
            unverifiedIds.join(", ") +
            ")."
        );
      } else if (cityInfo.unverified) {
        messages.push(
          "Advertencia de verificación: el tipo de cambio de la ciudad aún no tiene fecha de verificación."
        );
      } else {
        messages.push(
          "Advertencia de verificación: " +
            unverifiedIds.length +
            " opción(es) del catálogo no están verificadas (" +
            unverifiedIds.join(", ") +
            ")."
        );
      }
    }

    const cityExpired = cityInfo.freshness_status === "EXPIRED";
    if (cityExpired || expiredIds.length > 0) {
      if (cityExpired && expiredIds.length > 0) {
        messages.push(
          "Advertencia de vigencia: los metadatos de la ciudad y " +
            expiredIds.length +
            " opción(es) superaron la ventana de 180 días y requieren reverificación (" +
            expiredIds.join(", ") +
            ")."
        );
      } else if (cityExpired) {
        messages.push(
          "Advertencia de vigencia: los metadatos de la ciudad superaron la ventana de 180 días y requieren reverificación."
        );
      } else {
        messages.push(
          "Advertencia de vigencia: " +
            expiredIds.length +
            " opción(es) superaron la ventana de 180 días y requieren reverificación (" +
            expiredIds.join(", ") +
            ")."
        );
      }
    }

    const cityStale = cityInfo.freshness_status === "STALE";
    if (cityStale || staleIds.length > 0) {
      if (cityStale && staleIds.length > 0) {
        messages.push(
          "Aviso de frescura: los metadatos de la ciudad y " +
            staleIds.length +
            " opción(es) se encuentran en la ventana de 61 a 180 días desde su última verificación (" +
            staleIds.join(", ") +
            ")."
        );
      } else if (cityStale) {
        messages.push(
          "Aviso de frescura: los metadatos de la ciudad se encuentran en la ventana de 61 a 180 días desde su última verificación."
        );
      } else {
        messages.push(
          "Aviso de frescura: " +
            staleIds.length +
            " opción(es) se encuentran en la ventana de 61 a 180 días desde su última verificación (" +
            staleIds.join(", ") +
            ")."
        );
      }
    }

    if (messages.length === 0) {
      banner.hidden = true;
      return;
    }

    const heading = createElement(
      "h3",
      null,
      "Atención: datos con verificación pendiente o desactualizados"
    );
    const list = createElement("ul", null);
    messages.forEach(function (msg) {
      list.appendChild(createElement("li", null, msg));
    });

    banner.appendChild(heading);
    banner.appendChild(list);
    banner.hidden = false;
  }

  function createMetricItem(label, value, subtext) {
    const item = createElement("div", "metric-item");
    item.appendChild(createElement("span", "metric-label", label));
    item.appendChild(createElement("span", "metric-value", value));
    if (subtext) {
      item.appendChild(createElement("span", "metric-sub", subtext));
    }
    return item;
  }

  function indexScenariosByType(scenarios) {
    const map = {};
    if (Array.isArray(scenarios)) {
      scenarios.forEach(function (scenario) {
        if (scenario && scenario.scenario_type) {
          map[scenario.scenario_type] = scenario;
        }
      });
    }
    return map;
  }

  function renderSummaryCard(scenario, currency) {
    const card = createElement("article", "summary-card");
    card.setAttribute("data-scenario-type", scenario.scenario_type);

    const header = createElement("div", "summary-card-header");
    const titleWrap = createElement("div", null);
    titleWrap.appendChild(createElement("h3", "summary-card-title", scenarioLabel(scenario)));
    titleWrap.appendChild(
      createElement(
        "p",
        "summary-card-subtitle",
        SCENARIO_DESCRIPTIONS[scenario.scenario_type] || ""
      )
    );
    header.appendChild(titleWrap);

    if (scenario.unverified) {
      header.appendChild(
        createElement("span", "badge badge-warning", "estimado / sin verificar")
      );
    } else {
      header.appendChild(createElement("span", "badge badge-success", "Verificado"));
    }
    card.appendChild(header);

    const metrics = createElement("div", "summary-metrics");
    metrics.appendChild(
      createMetricItem(
        "Total del viaje",
        formatUsd(scenario.total_cost_usd),
        formatLocal(scenario.total_cost_clp, currency)
      )
    );

    const savings = scenario.savings_vs_zero_friction || {};
    const savingsPct = Number(savings.savings_percentage || 0).toFixed(1) + "%";
    const savingsPrimary =
      scenario.scenario_type === "ZERO_FRICTION"
        ? "Referencia base (0.0%)"
        : formatUsd(savings.savings_usd) + " (" + savingsPct + ")";
    const savingsSub =
      scenario.scenario_type === "ZERO_FRICTION"
        ? "Punto de comparación"
        : formatLocal(savings.savings_clp, currency);
    metrics.appendChild(
      createMetricItem("Ahorro vs. Cero Fricción", savingsPrimary, savingsSub)
    );

    metrics.appendChild(
      createMetricItem(
        "Tiempo extra total",
        "+" + String(scenario.extra_time_minutes || 0) + " min",
        "Fricción promedio: " + Number(scenario.friction_score || 0).toFixed(2) + " / 100"
      )
    );

    card.appendChild(metrics);
    return card;
  }

  function renderTripSummary(data) {
    const summarySection = document.getElementById("summary-section");
    const summaryGrid = document.getElementById("summary-scenarios-grid");
    const profileSummary = document.getElementById("profile-summary");
    clearChildren(summaryGrid);

    const traveler = data.traveler || {};
    const deviceMode =
      (traveler.device_profile && traveler.device_profile.mode) || "dual";
    const cityName = (data.city && data.city.name) || "Santiago";
    const currency = (data.city && data.city.local_currency) || "CLP";
    const toleranceCode = String(traveler.friction_tolerance || "MEDIUM");

    const manualInput = document.getElementById("data-gb-input");
    const manualRaw = manualInput ? manualInput.value.trim() : "";
    const presetKey = getCheckedRadioValue("data_preset");
    const dataText = manualRaw
      ? String(traveler.target_data_gb || 0) + " GB (manual)"
      : (DATA_PRESET_LABELS[presetKey] || "Normal") +
        " (~" +
        String(traveler.target_data_gb || 0) +
        " GB aprox.)";

    profileSummary.textContent =
      cityName +
      " · " +
      String(traveler.trip_duration_days || 7) +
      " días · Datos: " +
      dataText +
      " · Teléfono: " +
      (DEVICE_LABELS[deviceMode] || deviceMode) +
      " · " +
      (traveler.has_local_id ? "Con RUT/cédula" : "Sin RUT/cédula") +
      " · " +
      (TOLERANCE_LABELS[toleranceCode] || toleranceCode);

    const scenariosByType = indexScenariosByType(data.scenarios);
    SCENARIO_ORDER.forEach(function (scenarioType) {
      const scenario = scenariosByType[scenarioType];
      if (scenario) {
        summaryGrid.appendChild(renderSummaryCard(scenario, currency));
      }
    });

    summarySection.hidden = false;
  }

  function findChoiceForCategory(scenario, categoryCode) {
    if (!scenario || !Array.isArray(scenario.choices)) {
      return null;
    }
    for (let i = 0; i < scenario.choices.length; i += 1) {
      if (scenario.choices[i] && scenario.choices[i].category === categoryCode) {
        return scenario.choices[i];
      }
    }
    return null;
  }

  function renderCategoryScenarioPick(scenarioType, choice, data) {
    const currency = (data.city && data.city.local_currency) || "CLP";
    const freshnessMap = data.option_freshness || {};

    const card = createElement("div", "pick-card");
    card.setAttribute("data-scenario-type", scenarioType);

    const top = createElement("div", "pick-card-top");
    top.appendChild(createElement("span", "pick-scenario-name", SCENARIO_LABELS[scenarioType]));

    if (choice && choice.unverified) {
      top.appendChild(
        createElement("span", "badge badge-warning", "estimado / sin verificar")
      );
    } else if (
      choice &&
      (freshnessMap[choice.option_id] === "STALE" ||
        freshnessMap[choice.option_id] === "EXPIRED")
    ) {
      top.appendChild(
        createElement(
          "span",
          "badge badge-warning",
          FRESHNESS_LABELS[freshnessMap[choice.option_id]]
        )
      );
    }
    card.appendChild(top);

    if (!choice) {
      card.classList.add("pick-card-empty");
      card.appendChild(createElement("p", "pick-empty-text", "Sin datos todavía"));
      return card;
    }

    card.appendChild(createElement("p", "pick-option-name", choice.name));
    if (choice.provider) {
      card.appendChild(createElement("p", "pick-provider", choice.provider));
    }

    const priceRow = createElement("div", "pick-price-row");
    priceRow.appendChild(createElement("span", "pick-price-usd", formatUsd(choice.total_cost_usd)));
    priceRow.appendChild(
      createElement("span", "pick-price-clp", formatLocal(choice.total_cost_clp, currency))
    );
    card.appendChild(priceRow);

    const meta = createElement("div", "pick-meta");
    meta.appendChild(
      createElement(
        "span",
        "meta-pill",
        "Fricción: " + Number(choice.friction_score || 0).toFixed(2)
      )
    );
    meta.appendChild(
      createElement(
        "span",
        "meta-pill",
        "Extra: +" + String(choice.extra_time_minutes || 0) + " min"
      )
    );
    if (choice.sim_type && choice.sim_type !== "NOT_APPLICABLE") {
      meta.appendChild(
        createElement("span", "badge", "SIM: " + simTypeLabel(choice.sim_type))
      );
    }
    card.appendChild(meta);

    return card;
  }

  function renderCategoryBlock(container, categoryDef, scenariosByType, data) {
    const block = createElement("div", "subcategory-block");
    if (categoryDef.label) {
      block.appendChild(createElement("h4", "subcategory-heading", categoryDef.label));
    }

    const anyChoice = SCENARIO_ORDER.some(function (scenarioType) {
      return findChoiceForCategory(scenariosByType[scenarioType], categoryDef.code) !== null;
    });

    if (!anyChoice) {
      const emptyBox = createElement("div", "empty-category-box");
      emptyBox.appendChild(createElement("span", "badge", "Sin datos todavía"));
      emptyBox.appendChild(
        createElement(
          "p",
          "empty-category-note",
          "No hay opciones cargadas o compatibles para tu perfil en esta categoría."
        )
      );
      block.appendChild(emptyBox);
      container.appendChild(block);
      return;
    }

    const grid = createElement("div", "category-picks-grid");
    SCENARIO_ORDER.forEach(function (scenarioType) {
      const choice = findChoiceForCategory(scenariosByType[scenarioType], categoryDef.code);
      grid.appendChild(renderCategoryScenarioPick(scenarioType, choice, data));
    });
    block.appendChild(grid);
    container.appendChild(block);
  }

  function renderCategoriesSection(data) {
    const categoriesSection = document.getElementById("categories-section");
    const container = document.getElementById("categories-container");
    clearChildren(container);

    const scenariosByType = indexScenariosByType(data.scenarios);

    CATEGORY_SECTIONS.forEach(function (sectionDef) {
      const sectionCard = createElement("article", "panel category-panel");
      sectionCard.setAttribute("data-category-group", sectionDef.key);

      const header = createElement("div", "category-panel-header");
      header.appendChild(createElement("h3", "category-panel-title", sectionDef.title));
      header.appendChild(createElement("p", "category-panel-subtitle", sectionDef.subtitle));
      sectionCard.appendChild(header);

      sectionDef.categories.forEach(function (categoryDef) {
        renderCategoryBlock(sectionCard, categoryDef, scenariosByType, data);
      });

      container.appendChild(sectionCard);
    });

    categoriesSection.hidden = false;
  }

  function renderRejectedOptions(data) {
    const section = document.getElementById("rejected-section");
    const details = document.getElementById("rejected-details");
    const tbody = document.getElementById("rejected-tbody");
    const countSpan = document.getElementById("rejected-count");
    const emptyMsg = document.getElementById("rejected-empty");
    const tableWrapper = document.getElementById("rejected-table-wrapper");
    clearChildren(tbody);

    const rejected = Array.isArray(data.rejected_options) ? data.rejected_options : [];
    if (countSpan) {
      countSpan.textContent = String(rejected.length);
    }
    if (details) {
      details.open = false;
    }

    if (rejected.length === 0) {
      emptyMsg.hidden = false;
      tableWrapper.hidden = true;
      section.hidden = false;
      return;
    }

    emptyMsg.hidden = true;
    tableWrapper.hidden = false;

    rejected.forEach(function (item) {
      const tr = createElement("tr", null);
      tr.appendChild(createElement("td", null, categoryLabel(item.category)));
      tr.appendChild(createElement("td", null, item.name));
      tr.appendChild(createElement("td", null, item.provider));
      tr.appendChild(createElement("td", null, simTypeLabel(item.sim_type)));

      const reasonsTd = createElement("td", null);
      const reasons = Array.isArray(item.reasons) ? item.reasons : [];
      const formattedReasons = reasons
        .map(function (r) {
          return reasonLabel(r) + " [" + r + "]";
        })
        .join("; ");
      reasonsTd.textContent = formattedReasons;
      tr.appendChild(reasonsTd);

      tbody.appendChild(tr);
    });

    section.hidden = false;
  }

  function renderSimulationResult(data) {
    hideError();
    renderWarnings(data);
    renderTripSummary(data);
    renderCategoriesSection(data);
    renderRejectedOptions(data);
  }

  function populatePresetHints() {
    const hints = document.querySelectorAll("[data-preset-gb]");
    hints.forEach(function (el) {
      const key = el.getAttribute("data-preset-gb");
      if (key && Object.prototype.hasOwnProperty.call(DATA_USAGE_PRESETS, key)) {
        el.textContent = "Aprox. " + String(DATA_USAGE_PRESETS[key]) + " GB";
      }
    });
  }

  async function loadCities() {
    const citySelect = document.getElementById("city-select");
    try {
      const response = await fetch("/api/cities", {
        method: "GET",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (!payload || !Array.isArray(payload.cities) || payload.cities.length === 0) {
        return;
      }
      clearChildren(citySelect);
      payload.cities.forEach(function (city) {
        const label =
          city.name +
          (city.country_code ? " (" + city.country_code + ")" : "");
        const opt = createElement("option", null, label);
        opt.value = city.id;
        citySelect.appendChild(opt);
      });
    } catch (_err) {
      // Keep default fallback option if offline fetch fails.
    }
  }

  function createValidationError(field, message) {
    const err = new Error(message);
    err.field = field;
    return err;
  }

  function readFormPayload() {
    const city = document.getElementById("city-select").value.trim();
    const daysRaw = document.getElementById("days-input").value.trim();
    const manualGbRaw = document.getElementById("data-gb-input").value.trim();
    const presetKey = getCheckedRadioValue("data_preset");
    const device = getCheckedRadioValue("device");
    const tolerance = getCheckedRadioValue("tolerance");
    const hasLocalId = Boolean(
      document.getElementById("has-local-id-input").checked
    );

    const days = Number(daysRaw);

    if (!city) {
      throw createValidationError("city", "Selecciona una ciudad válida.");
    }
    if (!daysRaw || !Number.isInteger(days) || days < 1 || days > 365) {
      throw createValidationError(
        "days",
        "La duración del viaje debe ser un número entero entre 1 y 365 días."
      );
    }

    let dataGb;
    if (manualGbRaw !== "") {
      dataGb = Number(manualGbRaw);
      if (!Number.isFinite(dataGb) || dataGb < 0 || dataGb > 1000) {
        throw createValidationError(
          "data_gb",
          "El consumo manual de datos debe ser un número finito entre 0 y 1000 GB."
        );
      }
    } else if (
      presetKey &&
      Object.prototype.hasOwnProperty.call(DATA_USAGE_PRESETS, presetKey)
    ) {
      dataGb = DATA_USAGE_PRESETS[presetKey];
    } else {
      throw createValidationError(
        "data_gb",
        "Selecciona un nivel de datos o ingresa un valor manual válido."
      );
    }

    if (!device) {
      throw createValidationError("device", "Selecciona una capacidad SIM válida.");
    }
    if (!tolerance) {
      throw createValidationError(
        "tolerance",
        "Selecciona una preferencia de tolerancia a la fricción."
      );
    }

    return {
      city: city,
      days: days,
      data_gb: dataGb,
      device: device,
      has_local_id: hasLocalId,
      tolerance: tolerance
    };
  }

  async function submitSimulation(event) {
    if (event) {
      event.preventDefault();
    }
    const button = document.getElementById("simulate-button");
    const statusText = document.getElementById("status-indicator");
    clearFieldErrors();

    let payload;
    try {
      payload = readFormPayload();
    } catch (validationErr) {
      showError(validationErr.message, validationErr.field || null);
      statusText.textContent = "";
      return;
    }

    button.disabled = true;
    statusText.textContent = "Calculando escenarios...";

    try {
      let response;
      let rawText;
      try {
        response = await fetch("/api/simulate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json"
          },
          body: JSON.stringify(payload)
        });
        rawText = await response.text();
      } catch (_networkErr) {
        showError("No fue posible comunicarse con el servidor local.", null);
        statusText.textContent = "";
        return;
      }

      let result = null;
      if (rawText) {
        try {
          result = JSON.parse(rawText);
        } catch (_parseErr) {
          result = null;
        }
      }

      if (!response.ok) {
        if (result && typeof result.error === "string" && result.error) {
          showError(result.error, result.field || null);
        } else {
          showError(
            "El servidor devolvió una respuesta no válida (código " + response.status + ").",
            null
          );
        }
        statusText.textContent = "";
        return;
      }

      if (!result || typeof result !== "object") {
        showError(
          "El servidor devolvió una respuesta en formato inesperado (se esperaba JSON).",
          null
        );
        statusText.textContent = "";
        return;
      }

      renderSimulationResult(result);
      statusText.textContent = "Simulación actualizada.";
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    populatePresetHints();

    const form = document.getElementById("simulation-form");
    if (form) {
      form.addEventListener("submit", submitSimulation);
      form.addEventListener("input", function (event) {
        if (event.target && event.target.hasAttribute("aria-invalid")) {
          event.target.removeAttribute("aria-invalid");
        }
      });
      form.addEventListener("change", function (event) {
        if (event.target && event.target.hasAttribute("aria-invalid")) {
          event.target.removeAttribute("aria-invalid");
        }
        if (event.target && event.target.name === "data_preset") {
          const manualInput = document.getElementById("data-gb-input");
          if (manualInput) {
            manualInput.value = "";
            manualInput.removeAttribute("aria-invalid");
          }
        }
      });
    }

    loadCities().then(function () {
      submitSimulation(null);
    });
  });
})();
