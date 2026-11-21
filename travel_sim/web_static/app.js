"use strict";

(function () {
  const CATEGORY_LABELS = {
    CONNECTIVITY: "Conectividad móvil",
    AIRPORT_TRANSFER: "Traslado aeropuerto",
    URBAN_TRANSIT: "Transporte urbano",
    DAY_TRIP: "Escapadas del día",
    DINING: "Comida y gastronomía",
    CURRENCY_EXCHANGE: "Divisas y pagos"
  };

  const SCENARIO_DESCRIPTIONS = {
    ZERO_FRICTION: "Prioriza mínima fricción operativa y máxima inmediatez.",
    BALANCED: "Sustituye opciones solo cuando el ahorro justifica la fricción extra.",
    LOCAL_OPTIMIZED: "Prioriza el menor costo total usando alternativas locales."
  };

  const DEVICE_LABELS = {
    "esim-only": "Solo eSIM",
    "physical-only": "Solo chip físico",
    "dual": "Dual (eSIM + chip físico)"
  };

  const SIM_TYPE_LABELS = {
    ESIM: "eSIM",
    PHYSICAL_SIM: "Chip físico",
    NOT_APPLICABLE: "No aplica"
  };

  const REJECTION_REASON_LABELS = {
    CITY_MISMATCH: "No corresponde a la ciudad seleccionada",
    UNSUPPORTED_PHYSICAL_SIM: "El teléfono no tiene ranura para chip físico",
    UNSUPPORTED_ESIM: "El teléfono no soporta eSIM",
    INVALID_CONNECTIVITY_SIM_TYPE: "Tipo de SIM inválido para conectividad",
    REQUIRES_LOCAL_ID: "Requiere documento de identidad local (RUT)",
    PAYMENT_METHOD_INCOMPATIBLE: "Método de pago incompatible",
    INSUFFICIENT_DATA_QUOTA: "Cuota de datos insuficiente para el viaje",
    INCOMPATIBLE_WITH_SELECTED: "Incompatible con otra opción seleccionada"
  };

  const FRESHNESS_LABELS = {
    STALE: "Dato desactualizado (61–180 días)",
    EXPIRED: "Dato vencido (>180 días)"
  };

  const FIELD_INPUT_IDS = {
    city: "city-select",
    days: "days-input",
    data_gb: "data-gb-input",
    device: "device-select",
    tolerance: "tolerance-select",
    has_local_id: "has-local-id-input"
  };

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

  function clearFieldErrors() {
    Object.keys(FIELD_INPUT_IDS).forEach(function (fieldKey) {
      const el = document.getElementById(FIELD_INPUT_IDS[fieldKey]);
      if (el) {
        el.removeAttribute("aria-invalid");
      }
    });
  }

  function clearPreviousResults() {
    const warningBanner = document.getElementById("warning-banner");
    if (warningBanner) {
      clearChildren(warningBanner);
      warningBanner.hidden = true;
    }

    const scenariosSection = document.getElementById("scenarios-section");
    const scenariosGrid = document.getElementById("scenarios-grid");
    const profileSummary = document.getElementById("profile-summary");
    if (scenariosGrid) {
      clearChildren(scenariosGrid);
    }
    if (profileSummary) {
      profileSummary.textContent = "";
    }
    if (scenariosSection) {
      scenariosSection.hidden = true;
    }

    const missingSection = document.getElementById("missing-section");
    const missingList = document.getElementById("missing-list");
    if (missingList) {
      clearChildren(missingList);
    }
    if (missingSection) {
      missingSection.hidden = true;
    }

    const rejectedSection = document.getElementById("rejected-section");
    const rejectedTbody = document.getElementById("rejected-tbody");
    const rejectedEmpty = document.getElementById("rejected-empty");
    const rejectedTableWrapper = document.getElementById("rejected-table-wrapper");
    if (rejectedTbody) {
      clearChildren(rejectedTbody);
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

    if (fieldName && FIELD_INPUT_IDS[fieldName]) {
      const target = document.getElementById(FIELD_INPUT_IDS[fieldName]);
      if (target) {
        target.setAttribute("aria-invalid", "true");
        target.focus();
      }
    }
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

  function renderScenarioCard(scenario, data) {
    const currency = (data.city && data.city.local_currency) || "CLP";
    const freshnessMap = data.option_freshness || {};
    const allCategories = Array.isArray(data.categories) ? data.categories : [];

    const card = createElement("article", "scenario-card");
    card.setAttribute("data-scenario-type", scenario.scenario_type);

    const header = createElement("div", "scenario-header");
    const titleBox = createElement("div", null);
    titleBox.appendChild(createElement("h3", "scenario-title", scenario.label));
    titleBox.appendChild(
      createElement(
        "p",
        "scenario-subtitle",
        SCENARIO_DESCRIPTIONS[scenario.scenario_type] || ""
      )
    );
    header.appendChild(titleBox);

    if (scenario.unverified) {
      header.appendChild(
        createElement("span", "badge badge-warning", "Incluye datos sin verificar")
      );
    } else {
      header.appendChild(createElement("span", "badge badge-success", "Verificado"));
    }
    card.appendChild(header);

    const metrics = createElement("div", "metrics-grid");
    metrics.appendChild(
      createMetricItem(
        "Costo total",
        formatUsd(scenario.total_cost_usd),
        formatLocal(scenario.total_cost_clp, currency)
      )
    );

    const savings = scenario.savings_vs_zero_friction || {};
    const savingsPct = Number(savings.savings_percentage || 0).toFixed(1) + "%";
    metrics.appendChild(
      createMetricItem(
        "Ahorro vs. Cero Fricción",
        formatUsd(savings.savings_usd) + " (" + savingsPct + ")",
        formatLocal(savings.savings_clp, currency)
      )
    );

    metrics.appendChild(
      createMetricItem(
        "Puntaje de fricción",
        Number(scenario.friction_score || 0).toFixed(2) + " / 100",
        "Total acumulado: " + Number(scenario.total_friction_score || 0).toFixed(2)
      )
    );

    metrics.appendChild(
      createMetricItem(
        "Tiempo extra",
        "+" + String(scenario.extra_time_minutes || 0) + " min",
        "Instalación total: " + String(scenario.total_setup_time_minutes || 0) + " min"
      )
    );
    card.appendChild(metrics);

    card.appendChild(createElement("h4", "choices-heading", "Elección por categoría"));

    const choicesByCategory = {};
    if (Array.isArray(scenario.choices)) {
      scenario.choices.forEach(function (choice) {
        choicesByCategory[choice.category] = choice;
      });
    }

    const choicesList = createElement("ul", "choices-list");
    allCategories.forEach(function (cat) {
      const choice = choicesByCategory[cat];
      const item = createElement("li", "choice-item");

      const topRow = createElement("div", "choice-top");
      topRow.appendChild(createElement("span", "choice-category", categoryLabel(cat)));

      if (!choice) {
        topRow.appendChild(createElement("span", "badge", "Sin datos"));
        item.appendChild(topRow);
        item.appendChild(
          createElement(
            "p",
            "choice-name",
            "Sin opción disponible en el catálogo para esta categoría"
          )
        );
        choicesList.appendChild(item);
        return;
      }

      topRow.appendChild(
        createElement(
          "span",
          "choice-cost",
          formatUsd(choice.total_cost_usd) +
            " / " +
            formatLocal(choice.total_cost_clp, currency)
        )
      );
      item.appendChild(topRow);

      item.appendChild(
        createElement(
          "p",
          "choice-name",
          choice.name + " (" + choice.provider + ")"
        )
      );

      const meta = createElement("div", "choice-meta");
      meta.appendChild(
        createElement(
          "span",
          null,
          "Fricción: " + Number(choice.friction_score || 0).toFixed(2)
        )
      );
      meta.appendChild(
        createElement(
          "span",
          null,
          "Tiempo extra: +" + String(choice.extra_time_minutes || 0) + " min"
        )
      );
      if (choice.sim_type && choice.sim_type !== "NOT_APPLICABLE") {
        meta.appendChild(
          createElement("span", "badge", "SIM: " + simTypeLabel(choice.sim_type))
        );
      }
      if (choice.unverified) {
        meta.appendChild(
          createElement("span", "badge badge-warning", "Sin verificar")
        );
      } else if (
        freshnessMap[choice.option_id] === "STALE" ||
        freshnessMap[choice.option_id] === "EXPIRED"
      ) {
        meta.appendChild(
          createElement(
            "span",
            "badge badge-warning",
            FRESHNESS_LABELS[freshnessMap[choice.option_id]]
          )
        );
      }

      item.appendChild(meta);
      choicesList.appendChild(item);
    });

    card.appendChild(choicesList);
    return card;
  }

  function renderMissingCategories(data) {
    const section = document.getElementById("missing-section");
    const list = document.getElementById("missing-list");
    clearChildren(list);

    const missing = Array.isArray(data.missing_categories) ? data.missing_categories : [];
    if (missing.length === 0) {
      list.appendChild(
        createElement("li", "badge badge-success", "Todas las categorías tienen opciones")
      );
    } else {
      missing.forEach(function (cat) {
        list.appendChild(
          createElement(
            "li",
            "badge badge-warning",
            categoryLabel(cat) + " (" + cat + ")"
          )
        );
      });
    }
    section.hidden = false;
  }

  function renderRejectedOptions(data) {
    const section = document.getElementById("rejected-section");
    const tbody = document.getElementById("rejected-tbody");
    const emptyMsg = document.getElementById("rejected-empty");
    const tableWrapper = document.getElementById("rejected-table-wrapper");
    clearChildren(tbody);

    const rejected = Array.isArray(data.rejected_options) ? data.rejected_options : [];
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

    const scenariosSection = document.getElementById("scenarios-section");
    const scenariosGrid = document.getElementById("scenarios-grid");
    const profileSummary = document.getElementById("profile-summary");
    clearChildren(scenariosGrid);

    const traveler = data.traveler || {};
    const deviceMode =
      (traveler.device_profile && traveler.device_profile.mode) || "dual";
    const cityName = (data.city && data.city.name) || "Santiago";

    profileSummary.textContent =
      cityName +
      " · " +
      String(traveler.trip_duration_days || 7) +
      " días · " +
      String(traveler.target_data_gb || 0) +
      " GB · Dispositivo: " +
      (DEVICE_LABELS[deviceMode] || deviceMode) +
      " · ID local: " +
      (traveler.has_local_id ? "Sí" : "No") +
      " · Tolerancia: " +
      String(traveler.friction_tolerance || "MEDIUM");

    const scenarios = Array.isArray(data.scenarios) ? data.scenarios : [];
    scenarios.forEach(function (scenario) {
      scenariosGrid.appendChild(renderScenarioCard(scenario, data));
    });
    scenariosSection.hidden = false;

    renderMissingCategories(data);
    renderRejectedOptions(data);
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
    const dataGbRaw = document.getElementById("data-gb-input").value.trim();
    const device = document.getElementById("device-select").value;
    const tolerance = document.getElementById("tolerance-select").value;
    const hasLocalId = Boolean(
      document.getElementById("has-local-id-input").checked
    );

    const days = Number(daysRaw);
    const dataGb = Number(dataGbRaw);

    if (!city) {
      throw createValidationError("city", "Selecciona una ciudad válida.");
    }
    if (!daysRaw || !Number.isInteger(days) || days < 1 || days > 365) {
      throw createValidationError(
        "days",
        "La duración del viaje debe ser un número entero entre 1 y 365 días."
      );
    }
    if (!dataGbRaw || !Number.isFinite(dataGb) || dataGb < 0 || dataGb > 1000) {
      throw createValidationError(
        "data_gb",
        "El consumo de datos debe ser un número finito entre 0 y 1000 GB."
      );
    }
    if (!device) {
      throw createValidationError("device", "Selecciona una capacidad SIM válida.");
    }
    if (!tolerance) {
      throw createValidationError(
        "tolerance",
        "Selecciona un nivel de tolerancia a la fricción válido."
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
      });
    }
    loadCities().then(function () {
      submitSimulation(null);
    });
  });
})();
