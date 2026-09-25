/** Build table cells as DOM nodes: HTML parsing would foster-parent slot markers. */
export function dataTable(caption, headers, rows) {
  const table = document.createElement("table");
  const title = table.createCaption();
  title.textContent = caption;
  const head = table.createTHead().insertRow();
  for (const label of headers) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    head.append(cell);
  }
  const body = table.createTBody();
  for (const values of rows) {
    const row = body.insertRow();
    values.forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      if (index === 0) cell.setAttribute("scope", "row");
      cell.textContent = String(value);
      row.append(cell);
    });
  }
  return table;
}
