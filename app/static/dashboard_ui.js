"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const numbers = new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
  });
  const dates = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Africa/Tunis",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const colors = {
    DEBUG: "#718096",
    INFO: "#1268ed",
    WARNING: "#c48806",
    ERROR: "#d7354b",
    CRITICAL: "#781b27",
  };
  const order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function svgElement(tag, attributes = {}, text) {
    const node = document.createElementNS(
      "http://www.w3.org/2000/svg", tag
    );
    for (const [name, value] of Object.entries(attributes)) {
      node.setAttribute(name, String(value));
    }
    if (text != null) node.textContent = text;
    return node;
  }

  function empty(container, text) {
    container.replaceChildren(element("p", text, "empty-state"));
  }

  function timeline(overview) {
    const container = byId("dashboard-timeline");
    const rows = overview.logs_over_time;

    byId("dashboard-interval").textContent =
      `Intervalles de ${numbers.format(overview.interval_seconds)} secondes. ` +
      "Horaires affichés dans Africa/Tunis.";

    if (!overview.period_total || !rows.length) {
      empty(container, "Aucun log sur la période sélectionnée.");
      return;
    }

    const width = 680;
    const height = 250;
    const left = 58;
    const right = 18;
    const top = 22;
    const bottom = 48;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    const maximum = Math.max(1, ...rows.map((row) => row.count));

    const svg = svgElement("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-label":
        `${numbers.format(overview.period_total)} logs sur la période. ` +
        "Le détail des intervalles est disponible sous le graphique.",
    });

    for (let step = 0; step <= 4; step += 1) {
      const y = top + plotHeight * step / 4;
      svg.append(
        svgElement("line", {
          x1: left, x2: width - right, y1: y, y2: y,
          stroke: "#e6ebf2",
        }),
        svgElement("text", {
          x: left - 9, y: y + 4,
          "text-anchor": "end",
          fill: "#5d6d82", "font-size": 11,
        }, numbers.format(maximum * (4 - step) / 4))
      );
    }

    const points = rows.map((row, index) => ({
      x: left + index * plotWidth / Math.max(1, rows.length - 1),
      y: top + plotHeight * (1 - row.count / maximum),
      row,
    }));

    const coordinates = points.map((point) =>
      `${point.x},${point.y}`
    ).join(" ");

    svg.append(
      svgElement("polygon", {
        points:
          `${left},${top + plotHeight} ${coordinates} ` +
          `${points[points.length - 1].x},${top + plotHeight}`,
        fill: "#1268ed", "fill-opacity": ".08",
      }),
      svgElement("polyline", {
        points: coordinates,
        fill: "none", stroke: "#1268ed", "stroke-width": 2.5,
        "stroke-linejoin": "round",
      })
    );

    for (const point of points) {
      const circle = svgElement("circle", {
        cx: point.x, cy: point.y, r: 3,
        fill: "#1268ed",
      });
      circle.append(svgElement(
        "title", {},
        `${dates.format(new Date(point.row.timestamp))} : ` +
        `${numbers.format(point.row.count)} logs`
      ));
      const tip =
        `${dates.format(new Date(point.row.timestamp))} — Africa/Tunis\n` +
        `${numbers.format(point.row.count)} logs dans cet intervalle`;

      circle.setAttribute("data-chart-tip", tip);

      const step = plotWidth / Math.max(1, rows.length - 1);
      const zoneLeft = Math.max(left, point.x - step / 2);
      const zoneRight = Math.min(width - right, point.x + step / 2);

      svg.append(svgElement("rect", {
        x: zoneLeft,
        y: top,
        width: Math.max(1, zoneRight - zoneLeft),
        height: plotHeight,
        fill: "transparent",
        "data-chart-tip": tip,
        "aria-hidden": "true",
        class: "timeline-hover-zone",
      }));

      svg.append(circle);
    }

    const labels = [...new Set([
      0, Math.floor((rows.length - 1) / 2), rows.length - 1,
    ])];

    for (const index of labels) {
      const point = points[index];
      svg.append(svgElement("text", {
        x: point.x,
        y: height - 12,
        "text-anchor":
          index === 0 ? "start" :
          index === rows.length - 1 ? "end" : "middle",
        fill: "#5d6d82", "font-size": 11,
      }, dates.format(new Date(point.row.timestamp))));
    }

    const details = element("details", null, "chart-details");
    details.append(element("summary", "Consulter les valeurs"));
    const list = element("ul");

    for (const row of rows) {
      list.append(element(
        "li",
        `${dates.format(new Date(row.timestamp))} : ` +
        `${numbers.format(row.count)} logs`
      ));
    }

    details.append(list);
    container.replaceChildren(svg, details);
  }

  function levels(overview) {
    const container = byId("dashboard-levels");

    if (!overview.period_total) {
      empty(container, "Aucun niveau à répartir sur cette période.");
      return;
    }

    const counts = Object.fromEntries(
      overview.levels.map((row) => [row.level, row.count])
    );
    const svg = svgElement("svg", {
      viewBox: "0 0 160 160",
      role: "group",
      "aria-label": "Répartition des logs, détaillée dans la légende.",
      class: "donut",
    });

    svg.append(svgElement("circle", {
      cx: 80, cy: 80, r: 60,
      fill: "none", stroke: "#edf1f6", "stroke-width": 20,
    }));

    let offset = 0;
    const circumference = 2 * Math.PI * 60;
    const legend = element("div", null, "level-legend");

    for (const level of order) {
      const count = counts[level] || 0;
      const fraction = count / overview.period_total;

      if (count) {
        const tip =
          `${level} : ${numbers.format(count)} logs\n` +
          `${numbers.format(fraction * 100)} % de la période`;

        const attributes = {
          fill: "none",
          stroke: colors[level],
          "stroke-width": 20,
          "data-chart-tip": tip,
          "aria-label": tip,
          tabindex: 0,
          class: "donut-segment",
        };

        let segment;

        if (fraction >= 1) {
          segment = svgElement("circle", {
            ...attributes, cx: 80, cy: 80, r: 60,
          });
        } else {
          const startAngle = offset * 2 * Math.PI - Math.PI / 2;
          const endAngle =
            (offset + fraction) * 2 * Math.PI - Math.PI / 2;

          const x1 = 80 + 60 * Math.cos(startAngle);
          const y1 = 80 + 60 * Math.sin(startAngle);
          const x2 = 80 + 60 * Math.cos(endAngle);
          const y2 = 80 + 60 * Math.sin(endAngle);

          segment = svgElement("path", {
            ...attributes,
            d: `M ${x1} ${y1} A 60 60 0 ` +
               `${fraction > 0.5 ? 1 : 0} 1 ${x2} ${y2}`,
          });
        }

        svg.append(segment);
      }

      offset += fraction;
      const item = element("div", null, "level-item");
      item.setAttribute(
        "data-chart-tip",
        `${level} : ${numbers.format(count)} logs\n` +
        `${numbers.format(fraction * 100)} % de la période`
      );
      item.tabIndex = 0;
      const dot = element("span", "", "level-dot");
      dot.style.backgroundColor = colors[level];
      dot.setAttribute("aria-hidden", "true");
      item.append(
        dot,
        element(
          "span",
          `${level} — ${numbers.format(count)} ` +
          `(${numbers.format(fraction * 100)} %)`
        )
      );
      legend.append(item);
    }

    svg.append(
      svgElement("text", {
        x: 80, y: 78, "text-anchor": "middle",
        fill: "#192d47", "font-size": 21, "font-weight": 700,
      }, numbers.format(overview.period_total)),
      svgElement("text", {
        x: 80, y: 100, "text-anchor": "middle",
        fill: "#5d6d82", "font-size": 12,
      }, "logs")
    );
    container.replaceChildren(svg, legend);
  }

  function services(overview) {
    const container = byId("dashboard-services");
    const rows = overview.errors_by_service;

    if (!rows.length) {
      empty(container, "Aucun log ERROR ou CRITICAL sur cette période.");
      return;
    }

    container.replaceChildren();
    const maximum = Math.max(...rows.map((row) => row.error_count));

    for (const row of rows) {
      const item = element("div", null, "service-item");
      item.setAttribute(
        "data-chart-tip",
        `${row.service}\n` +
        `${numbers.format(row.error_count)} logs ERROR ou CRITICAL`
      );
      item.tabIndex = 0;
      const heading = element("div", null, "service-heading");
      heading.append(
        element("span", row.service),
        element("strong", numbers.format(row.error_count))
      );

      const track = element("div", null, "bar-track");
      const bar = element("div", null, "bar-fill");
      bar.style.width = `${row.error_count / maximum * 100}%`;
      track.setAttribute("aria-hidden", "true");
      track.append(bar);
      item.append(heading, track);
      container.append(item);
    }
  }

  function recentEvents(overview) {
    const body = byId("search-body");
    body.replaceChildren();

    if (!overview.recent_events.length) {
      const row = element("tr");
      const cell = element(
        "td", "Aucun événement sur la période sélectionnée."
      );
      cell.colSpan = 5;
      row.append(cell);
      body.append(row);
      return;
    }

    for (const event of overview.recent_events) {
      const row = element("tr");
      row.append(element(
        "td", event.timestamp
          ? dates.format(new Date(event.timestamp)) : "N/D"
      ));

      const levelCell = element("td");
      const badge = element("span", event.level || "N/D", "level-badge");
      badge.style.color = colors[event.level] || "#5d6d82";
      levelCell.append(badge);

      row.append(
        levelCell,
        element("td", event.service || "N/D"),
        element("td", event.message || "—")
      );

      const action = element("td");
      const button = element("button", "Voir", "detail-button");
      button.type = "button";
      button.dataset.logId = event.id;
      button.dataset.logIndex = event.index;
      button.setAttribute(
        "aria-label",
        `Voir le détail de l’événement du service ${event.service || "inconnu"}`
      );
      action.append(button);
      row.append(action);
      body.append(row);
    }
  }

  document.addEventListener("dashboard:loaded", (event) => {
    const data = event.detail;

    byId("card-critical").textContent =
      `dont ${numbers.format(data.cards.critical_logs)} CRITICAL`;

    timeline(data.overview);
    levels(data.overview);
    services(data.overview);
    recentEvents(data.overview);
  });

  const preset = byId("dashboard-preset");
  const form = byId("dashboard-form");

  preset.addEventListener("change", () => {
    if (preset.value === "custom") {
      byId("dashboard-start").focus();
      return;
    }

    if (preset.value === "24h") {
      byId("dashboard-start").value = "";
      byId("dashboard-end").value = "";
    } else {
      const hours = { "1h": 1, "7d": 168, "30d": 720 }[preset.value];
      const end = new Date();
      const start = new Date(end.getTime() - hours * 3600000);
      byId("dashboard-start").value = start.toISOString().slice(0, -1);
      byId("dashboard-end").value = end.toISOString().slice(0, -1);
    }

    form.requestSubmit();
  });

  for (const field of ["start", "end"]) {
    byId(`dashboard-${field}`).addEventListener("input", () => {
      preset.value = "custom";
    });
  }
})();
