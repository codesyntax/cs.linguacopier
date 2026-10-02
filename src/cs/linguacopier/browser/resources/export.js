/*
 * Client-side CSV export for the cs.linguacopier copy report.
 *
 * The export button carries ``data-linguacopier-export``; the table it exports
 * is the ``.linguacopier-report-items`` table inside the nearest
 * ``.linguacopier-report`` container. The downloadable file opens in Excel.
 */
(function () {
  "use strict";

  function csvCell(value) {
    var text = value == null ? "" : String(value);
    // Neutralise spreadsheet formula injection: content such as a page title
    // or an error message must never execute when the file opens in Excel.
    if (/^[=+\-@\t\r]/.test(text)) {
      text = "'" + text;
    }
    if (/[",\r\n]/.test(text)) {
      text = '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
  }

  function tableToCsv(table) {
    return Array.prototype.map
      .call(table.querySelectorAll("tr"), function (row) {
        return Array.prototype.map
          .call(row.children, function (cell) {
            return csvCell(cell.textContent.trim());
          })
          .join(",");
      })
      .join("\r\n");
  }

  function exportTable(button) {
    var report = button.closest(".linguacopier-report");
    if (!report) {
      return;
    }
    var tables = report.querySelectorAll(
      ".linguacopier-report-counts, .linguacopier-report-translations, .linguacopier-report-items"
    );
    if (!tables.length) {
      return;
    }
    var csv = Array.prototype.map.call(tables, tableToCsv).join("\r\n\r\n");
    // Prepend a BOM so Excel opens the UTF-8 file correctly.
    var blob = new Blob(["\ufeff" + csv], {
      type: "text/csv;charset=utf-8;",
    });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "cs.linguacopier-copy-report.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-linguacopier-export]");
    if (button) {
      event.preventDefault();
      exportTable(button);
    }
  });
})();
