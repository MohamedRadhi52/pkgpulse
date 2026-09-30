"use strict";

var LEVELS = { total: "Total", categorie: "Catégories", paquet: "Paquets suivis", autres: "Autres" };
var MODELS = { naif_saisonnier: "Naïf saisonnier", ets: "ETS", lightgbm: "LightGBM" };
var COLORS = { total: "#1f4e79", categorie: "#e08a1e", paquet: "#2e8b57", autres: "#7a7a7a" };
var number = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
var charts = {};

fetch("data.json")
  .then(function (response) { return response.json(); })
  .then(start);

function start(data) {
  document.getElementById("updated").textContent = data.updated;
  var select = document.getElementById("series");
  Object.keys(LEVELS).forEach(function (level) {
    var group = document.createElement("optgroup");
    group.label = LEVELS[level];
    Object.keys(data.series).sort().forEach(function (id) {
      if (data.series[id].level === level) {
        group.appendChild(new Option(id.replace(/^(categorie|paquet):/, ""), id));
      }
    });
    select.appendChild(group);
  });
  select.value = "total";
  select.addEventListener("change", function () { show(data.series[select.value]); });
  show(data.series.total);
  backtestTable(data.backtest);
  monitoringChart(data.monitoring);
}

function show(series) {
  var f = series.forecast;
  document.getElementById("cards").innerHTML = f.ds.map(function (day, i) {
    return "<div class=\"card\"><span>J+" + f.h[i] + ", " + day + "</span><strong>" +
      number.format(f.y_hat[i]) + "</strong><small>entre " + number.format(f.lower[i]) +
      " et " + number.format(f.upper[i]) + "</small></div>";
  }).join("");
  historyChart(series);
  anomaliesTable(series.history);
}

function nextDays(last, count) {
  var days = [];
  for (var i = 1; i <= count; i++) {
    var day = new Date(last + "T00:00:00Z");
    day.setUTCDate(day.getUTCDate() + i);
    days.push(day.toISOString().slice(0, 10));
  }
  return days;
}

function historyChart(series) {
  var h = series.history;
  var f = series.forecast;
  var future = nextDays(h.ds[h.ds.length - 1], 7);
  var empty = future.map(function () { return null; });
  var bars = h.ds.map(function () { return null; }).concat(future.map(function (day) {
    var i = f.ds.indexOf(day);
    return i < 0 ? null : [f.lower[i], f.upper[i]];
  }));
  draw("history", {
    type: "line",
    data: {
      labels: h.ds.concat(future),
      datasets: [
        { type: "line", label: "Réalisé", data: h.y.concat(empty), borderColor: "#1f4e79",
          borderWidth: 2, pointRadius: 0 },
        { type: "line", label: "Prévision rejouée à J+1", data: h.y_hat.concat(empty),
          borderColor: "#e08a1e", borderDash: [4, 3], borderWidth: 1.5, pointRadius: 0 },
        { type: "line", label: "borne basse", data: h.lower.concat(empty), borderWidth: 0,
          pointRadius: 0 },
        { type: "line", label: "Intervalle à 90 %", data: h.upper.concat(empty), borderWidth: 0,
          pointRadius: 0, fill: "-1", backgroundColor: "rgba(224, 138, 30, 0.18)" },
        { type: "line", label: "Anomalie", showLine: false, pointRadius: 5,
          pointBackgroundColor: "#b03a2e", borderColor: "#b03a2e",
          data: h.anomaly.map(function (kind, i) { return kind ? h.y[i] : null; }).concat(empty) },
        { type: "bar", label: "Prévisions J+1 et J+7", data: bars,
          backgroundColor: "rgba(31, 78, 121, 0.4)" }
      ]
    },
    options: {
      locale: "fr-FR",
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { filter: function (item) { return item.text !== "borne basse"; } } } },
      scales: { x: { ticks: { maxTicksLimit: 10 } } }
    }
  });
}

function anomaliesTable(h) {
  var rows = h.ds.map(function (day, i) { return i; }).filter(function (i) { return h.anomaly[i]; });
  var table = document.getElementById("anomalies");
  if (!rows.length) {
    table.innerHTML = "<tr><td>Aucune anomalie sur la période.</td></tr>";
    return;
  }
  table.innerHTML = "<tr><th>Jour</th><th>Type</th><th>Réalisé</th><th>Prévu la veille</th></tr>" +
    rows.reverse().map(function (i) {
      return "<tr><td>" + h.ds[i] + "</td><td>" + h.anomaly[i] + "</td><td>" +
        number.format(h.y[i]) + "</td><td>" + number.format(h.y_hat[i]) + "</td></tr>";
    }).join("");
}

function backtestTable(rows) {
  var best = {};
  rows.forEach(function (row) {
    ["1", "7"].forEach(function (h) {
      var key = row.level + h;
      best[key] = Math.min(best[key] === undefined ? Infinity : best[key], row[h]);
    });
  });
  document.getElementById("backtest").innerHTML =
    "<tr><th>Niveau</th><th>Modèle</th><th>J+1</th><th>J+7</th></tr>" +
    rows.filter(function (row) { return row.level !== "autres"; }).map(function (row) {
      var cells = ["1", "7"].map(function (h) {
        var value = row[h].toFixed(3).replace(".", ",");
        return row[h] === best[row.level + h] ? "<td><strong>" + value + "</strong></td>" : "<td>" + value + "</td>";
      });
      return "<tr><td>" + LEVELS[row.level] + "</td><td>" + MODELS[row.model] + "</td>" + cells.join("") + "</tr>";
    }).join("");
}

function monitoringChart(rows) {
  var watched = rows.filter(function (row) {
    return row.role === "champion" && row.h === 1 && row.mase_7d !== null && row.level !== "autres";
  });
  if (!watched.length) {
    document.getElementById("monitoring").style.display = "none";
    document.getElementById("monitoring-note").textContent =
      "Le monitoring démarre : il faut 7 jours d'erreurs réalisées depuis la mise en production.";
    return;
  }
  var labels = Array.from(new Set(watched.map(function (row) { return row.ds; }))).sort();
  var datasets = [];
  ["paquet", "categorie", "total"].forEach(function (level) {
    var byDay = {};
    watched.filter(function (row) { return row.level === level; }).forEach(function (row) { byDay[row.ds] = row; });
    var any = watched.find(function (row) { return row.level === level; });
    if (!any) return;
    datasets.push({ label: LEVELS[level], borderColor: COLORS[level], pointRadius: 2,
      data: labels.map(function (day) { return byDay[day] ? byDay[day].mase_7d : null; }) });
    datasets.push({ label: "Seuil, " + LEVELS[level].toLowerCase(), borderColor: COLORS[level],
      borderDash: [6, 4], borderWidth: 1, pointRadius: 0,
      data: labels.map(function () { return any.threshold; }) });
  });
  draw("monitoring", { type: "line", data: { labels: labels, datasets: datasets },
    options: { locale: "fr-FR" } });
}

function draw(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}
